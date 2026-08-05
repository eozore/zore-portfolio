/**
 * POST /api/csm/derivatives
 *
 * Segunda fase do pacote editorial: recebe um roteiro já revisado e gera as
 * derivações omnicanal com base nele. A rota é deliberadamente separada da
 * geração do roteiro para preservar o gate de aprovação do usuário.
 */

import { NextResponse } from 'next/server';
import { loadSession, saveDraftToSession } from '@/lib/session';
import { isCsmAuthenticated, csmUnauthorized } from '@/lib/csmAuth';

export const maxDuration = 600;

function baseUrl(request: Request): string {
  const origin = request.headers.get('origin') ?? request.headers.get('x-forwarded-host');
  if (origin) return origin.startsWith('http') ? origin : `https://${origin}`;
  const host = request.headers.get('host') ?? 'localhost:3000';
  return host.includes('localhost') ? `http://${host}` : `https://${host}`;
}

function scriptFromManifest(manifest: unknown): string {
  const segments = (manifest as { youtube?: { segments?: { script?: string }[] } } | null)?.youtube?.segments;
  return segments?.map((segment) => segment.script ?? '').filter(Boolean).join('\n\n') ?? '';
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
    let specialistCopies: unknown = draft.specialistCopies ?? null;
    let thumbnails: unknown = draft.thumbnails ?? null;
    const cmoAgentUrl = process.env.CMO_AGENT_URL;
    if (cmoAgentUrl) {
      const specialistResponse = await fetch(`${cmoAgentUrl}/package`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(tenantId ? { 'X-Tenant-ID': tenantId } : {}),
        },
        body: JSON.stringify({
          pauta: draft.pauta,
          articleContent: content,
          category: draft.category || 'ml',
          language: draft.language || 'pt-BR',
          sessionId: body.sessionId,
          phase: 'derivatives',
          manifest: draft.manifestV2,
        }),
        signal: AbortSignal.timeout(480_000),
      });
      if (!specialistResponse.ok) {
        throw new Error(`Falha nos agentes especialistas (${specialistResponse.status})`);
      }
      const specialistData = await specialistResponse.json();
      specialistCopies = specialistData.copies ?? specialistCopies;
      thumbnails = specialistData.thumbnails ?? thumbnails;
    }

    const response = await fetch(`${baseUrl(request)}/api/csm/repurpose`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Cookie: request.headers.get('cookie') || '',
      },
      body: JSON.stringify({
        title: draft.suggestedTitle || (draft.pauta as { titulo?: string } | undefined)?.titulo || 'Campanha',
        slug: draft.suggestedSlug || undefined,
        content,
        category: draft.category || 'ml',
        language: draft.language || 'pt-BR',
        youtubeScript,
      }),
      signal: AbortSignal.timeout(540_000),
    });

    const repurposedData = await response.json().catch(() => null);
    if (!response.ok || !repurposedData) {
      return NextResponse.json(
        { error: repurposedData?.error || `Falha nas derivações (${response.status})` },
        { status: 502 },
      );
    }

    await saveDraftToSession(body.sessionId, {
      ...draft,
      youtubeScript,
      specialistCopies,
      thumbnails,
      repurposedData,
      packageStatus: 'ready',
      workflowStage: 'package_ready',
      packageError: '',
    }, tenantId);

    return NextResponse.json({ success: true, repurposedData, youtubeScript });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error('[csm/derivatives] generation failed:', error);
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
