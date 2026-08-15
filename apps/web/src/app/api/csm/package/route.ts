/**
 * POST /api/csm/package
 *
 * Enfileira a geração do pacote editorial e devolve 202 imediatamente.
 *
 * Antes, esta rota fazia todo o trabalho dentro do próprio request: gerava o
 * artigo (SSE), chamava o cmo-agent para roteiro/slides/thumbnails/copies, e
 * só então respondia — de 4 a 8 minutos com o navegador segurando o fetch.
 * Três coisas matavam isso na prática: o timeout de 600s do serviço frontend
 * no Cloud Run, o usuário fechar a aba, e a reciclagem de instância. Como o
 * estado só era persistido quando a promise resolvia, uma morte no meio não
 * deixava nada para retomar.
 *
 * Agora a rota apenas garante que a sessão tem artigo + pauta, publica uma
 * PackageRequestedMsg no Pub/Sub e sai. O package-job (Cloud Run Job, 1h de
 * task-timeout) executa e grava checkpoints na sessão a cada etapa; o polling
 * que o ReviewTab já fazia passa a mostrar progresso real.
 */

import { NextResponse } from 'next/server';
import { PubSub } from '@google-cloud/pubsub';
import { loadSession, saveDraftToSession } from '@/lib/session';
import { isCsmAuthenticated, csmUnauthorized } from '@/lib/csmAuth';

const PACKAGE_TOPIC = 'content-pipeline.package-requested';
const GCP_PROJECT_ID = process.env.FIREBASE_PROJECT_ID || 'vazfy-417019';

export interface PautaConcebida {
  titulo: string;
  subtitulo: string;
  tese: string;
  publico: string;
  duracao_alvo: string;
  serie: string;
  objetivo_aprendizado?: string;
  hardskills?: string[];
  tipo_artigo?: 'tecnico' | 'conceitual' | 'estrategico';
  nivel_tecnico?: 'baixo' | 'medio' | 'alto';
}

export interface PackageRequest {
  pauta?: PautaConcebida;
  chatTranscript?: string;
  category?: string;
  language?: 'pt-BR' | 'en';
  sessionId?: string;
  /** Artigo já publicado; a geração de artigo não passa mais por aqui. */
  articleContent?: string;
  /** "script" (padrão) ou "derivatives". */
  phase?: 'script' | 'derivatives';
}

export interface PackageQueuedResult {
  queued: true;
  phase: 'script' | 'derivatives';
  messageId: string;
  sessionId: string;
}

// A rota agora só enfileira — segundos, não minutos.
export const maxDuration = 60;

function slugify(str: string): string {
  return str
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9\s-]/g, '')
    .trim()
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .slice(0, 100);
}

export async function POST(request: Request): Promise<Response> {
  if (!isCsmAuthenticated(request)) return csmUnauthorized();

  let body: PackageRequest;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const { pauta, category, language = 'pt-BR', sessionId, articleContent, phase = 'script' } = body;
  const tenantId = request.headers.get('x-tenant-id') || null;

  if (!sessionId) {
    return NextResponse.json({ error: 'sessionId é obrigatório' }, { status: 400 });
  }
  if (phase !== 'script' && phase !== 'derivatives') {
    return NextResponse.json({ error: `phase inválida: ${phase}` }, { status: 400 });
  }

  // O job lê tudo da sessão no Firestore, então o que veio no corpo precisa
  // estar persistido ANTES de publicar a mensagem — senão o job corre contra
  // um autosave do cliente que ainda não aconteceu.
  const session = await loadSession(sessionId, tenantId);
  const currentDraft = (session as { draft?: Record<string, unknown> } | null)?.draft ?? {};

  const resolvedPauta = pauta ?? (currentDraft.pauta as PautaConcebida | undefined);
  const resolvedArticle =
    (articleContent && articleContent.trim().length > 100)
      ? articleContent
      : (currentDraft.generatedContent as string | undefined) ?? '';

  if (!resolvedPauta?.titulo || resolvedPauta.titulo.trim().length < 5) {
    return NextResponse.json({ error: 'pauta.titulo é obrigatório (mín. 5 caracteres)' }, { status: 400 });
  }
  if (resolvedArticle.trim().length < 100) {
    return NextResponse.json(
      { error: 'O artigo precisa estar gerado antes de montar o pacote.' },
      { status: 422 },
    );
  }
  if (phase === 'derivatives' && !currentDraft.manifestV2) {
    return NextResponse.json(
      { error: 'O roteiro precisa existir antes de gerar as derivações.' },
      { status: 409 },
    );
  }

  try {
    await saveDraftToSession(sessionId, {
      ...currentDraft,
      pauta: resolvedPauta,
      generatedContent: resolvedArticle,
      category: category ?? currentDraft.category ?? 'ml',
      language,
      suggestedTitle: currentDraft.suggestedTitle || resolvedPauta.titulo,
      suggestedSlug: currentDraft.suggestedSlug || slugify(resolvedPauta.titulo),
      packageStatus: 'generating',
      workflowStage: 'package_generating',
      packageStage: `${phase}:enfileirado`,
      packageStartedAt: Date.now(),
      packageError: '',
    }, tenantId);
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'falha ao persistir a sessão';
    console.error('[csm/package] persist failed:', msg);
    return NextResponse.json({ error: `Não foi possível salvar a sessão: ${msg}` }, { status: 500 });
  }

  try {
    const pubsub = new PubSub({ projectId: GCP_PROJECT_ID });
    const messageId = await pubsub.topic(PACKAGE_TOPIC).publishMessage({
      data: Buffer.from(JSON.stringify({
        session_id: sessionId,
        phase,
        requested_at: new Date().toISOString(),
        tenant_id: tenantId,
      })),
    });

    console.log(`[csm/package] enfileirado session=${sessionId} phase=${phase} msg=${messageId}`);
    const result: PackageQueuedResult = { queued: true, phase, messageId, sessionId };
    return NextResponse.json(result, { status: 202 });
  } catch (err) {
    // Se o enfileiramento falhar, a sessão não pode ficar presa em "generating"
    // — senão a UI mostra um spinner que nunca termina.
    const msg = err instanceof Error ? err.message : 'falha ao publicar no Pub/Sub';
    console.error('[csm/package] publish failed:', msg);
    await saveDraftToSession(sessionId, {
      ...currentDraft,
      packageStatus: 'error',
      workflowStage: 'error',
      packageError: `Não foi possível enfileirar a geração: ${msg}`,
    }, tenantId).catch(() => undefined);
    return NextResponse.json({ error: `Falha ao enfileirar: ${msg}` }, { status: 502 });
  }
}
