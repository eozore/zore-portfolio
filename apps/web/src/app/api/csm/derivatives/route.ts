/**
 * POST /api/csm/derivatives
 *
 * Segunda fase do pacote editorial: thumbnails, copies especializados e
 * derivações omnicanal, a partir de um roteiro já revisado pelo usuário.
 *
 * Assim como /api/csm/package, esta rota deixou de executar o trabalho dentro
 * do request. Ela valida o gate editorial (artigo publicado + roteiro
 * aguardando aprovação), enfileira uma PackageRequestedMsg com phase
 * "derivatives" e devolve 202. Quem executa é o package-job.
 *
 * O gate continua no servidor de propósito: a UI pode esconder o botão, mas
 * não deve ser possível gerar derivações chamando a API direto.
 */

import { NextResponse } from 'next/server';
import { PubSub } from '@google-cloud/pubsub';
import { loadSession, saveDraftToSession } from '@/lib/session';
import { isCsmAuthenticated, csmUnauthorized } from '@/lib/csmAuth';

const PACKAGE_TOPIC = 'content-pipeline.package-requested';
const GCP_PROJECT_ID = process.env.FIREBASE_PROJECT_ID || 'vazfy-417019';

export const maxDuration = 60;

function scriptFromManifest(manifest: unknown): string {
  const segments = (manifest as { youtube?: { segments?: { script?: string }[] } } | null)
    ?.youtube?.segments;
  return segments?.map((s) => s.script ?? '').filter(Boolean).join('\n\n') ?? '';
}

export async function POST(request: Request): Promise<Response> {
  if (!isCsmAuthenticated(request)) return csmUnauthorized();

  let body: { sessionId?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }
  if (!body.sessionId) {
    return NextResponse.json({ error: 'sessionId required' }, { status: 400 });
  }

  const tenantId = request.headers.get('x-tenant-id') || null;
  const session = await loadSession(body.sessionId, tenantId);
  const draft = (session as { draft?: Record<string, unknown> } | null)?.draft;

  if (!draft?.publishedArticleUrl) {
    return NextResponse.json({ error: 'O artigo precisa estar publicado antes das derivações.' }, { status: 409 });
  }
  if (draft.packageStatus !== 'script_ready') {
    return NextResponse.json({ error: 'O roteiro ainda não está aguardando aprovação.' }, { status: 409 });
  }

  const content = typeof draft.generatedContent === 'string' ? draft.generatedContent : '';
  const youtubeScript = typeof draft.youtubeScript === 'string' && draft.youtubeScript.trim()
    ? draft.youtubeScript
    : scriptFromManifest(draft.manifestV2);
  if (!content || !youtubeScript) {
    return NextResponse.json({ error: 'Artigo e roteiro são necessários para gerar derivações.' }, { status: 422 });
  }

  try {
    await saveDraftToSession(body.sessionId, {
      ...draft,
      youtubeScript,
      packageStatus: 'generating',
      workflowStage: 'package_generating',
      packageStage: 'derivatives:enfileirado',
      packageStartedAt: Date.now(),
      packageError: '',
    }, tenantId);

    const pubsub = new PubSub({ projectId: GCP_PROJECT_ID });
    const messageId = await pubsub.topic(PACKAGE_TOPIC).publishMessage({
      data: Buffer.from(JSON.stringify({
        session_id: body.sessionId,
        phase: 'derivatives',
        requested_at: new Date().toISOString(),
        tenant_id: tenantId,
      })),
    });

    console.log(`[csm/derivatives] enfileirado session=${body.sessionId} msg=${messageId}`);
    return NextResponse.json({ queued: true, phase: 'derivatives', messageId }, { status: 202 });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error('[csm/derivatives] enqueue failed:', message);
    // Não deixa a sessão presa em "generating" — senão o spinner nunca acaba.
    await saveDraftToSession(body.sessionId, {
      ...draft,
      packageStatus: 'script_ready',
      workflowStage: 'script_ready',
      packageError: `Não foi possível enfileirar as derivações: ${message}`,
    }, tenantId).catch(() => undefined);
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
