/**
 * POST /api/csm/approve-package
 * Sprint 4 / G5 — Aprovação única do pacote de conteúdo derivado.
 *
 * IMPORTANTE: O artigo já foi publicado no PublishTab ANTES de chegar aqui.
 * Esta rota apenas orquestra a distribuição do pacote derivado:
 *   1. Texto social → POST /api/csm/pipeline-submit (LinkedIn/Threads agendado)
 *   2. Vídeo        → POST /api/csm/pipeline-submit (YouTube/Reels via Pub/Sub)
 *
 * Retorna um ApproveResult consolidado com o status de cada etapa.
 * Erros parciais não bloqueiam as demais etapas.
 *
 * Autenticação: Firebase Admin ADC (nunca API Key hardcoded).
 */

import { NextResponse } from 'next/server';
import { isCsmAuthenticated, csmUnauthorized } from '@/lib/csmAuth';
import { loadSession, saveDraftToSession } from '@/lib/session';

// ── Tipos ─────────────────────────────────────────────────────────────────────

export type StepStatus = 'skipped' | 'ok' | 'error';

export interface StepResult {
  status: StepStatus;
  detail?: string;
}

export interface ApproveResult {
  text:     StepResult;   // LinkedIn, Threads — publicação agendada
  video:    StepResult;   // YouTube, Reels   — pipeline Pub/Sub
  errors:   string[];
  approved_at: string;
}

export interface ApprovePackageRequest {
  /** Itens de texto aprovados (LinkedIn, Threads, Facebook) */
  textItems?: {
    platform:     string;
    format:       string;
    title:        string;
    copy:         string;
    threadPosts?: string[];
    imageUrl?:    string;
    scheduledAt:  string;
    status:       'aprovado';
  }[];
  /** Roteiro YouTube (dispara pipeline TTS → Avatar → VideoEditor) */
  youtubeScript?: string;
  /** Itens de vídeo curto aprovados (Shorts, Reels) */
  videoItems?: {
    id:       string;
    platform: string;
    format:   string;
    title:    string;
    copy:     string;
    script?:  string;
    scheduledAt: string;
    status:   'aprovado';
  }[];
  /** Slug do artigo já publicado — usado como referência */
  articleSlug:  string;
  /** Título do artigo já publicado */
  articleTitle: string;
  sessionId?:   string;
  /** Cabeçalho CSM-Session para auth nas rotas internas */
  csmSession?:  string;
}

export const maxDuration = 120; // 2 min máx para orquestração

// ── Helpers ───────────────────────────────────────────────────────────────────

function baseUrl(req: Request): string {
  const origin = req.headers.get('origin') ?? req.headers.get('x-forwarded-host');
  if (origin) return origin.startsWith('http') ? origin : `https://${origin}`;
  const host = req.headers.get('host') ?? 'localhost:3000';
  return host.includes('localhost') ? `http://${host}` : `https://${host}`;
}

function csmHeaders(session: string, cookie: string): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    Cookie: cookie,
  };
}

// ── Etapa 1 — Enfileira texto social (NÃO publica imediatamente) ─────────────
// A publicação acontece via publisher-scheduled (Cloud Scheduler a cada hora).

async function enqueueText(
  base: string,
  textItems: NonNullable<ApprovePackageRequest['textItems']>,
  articleSlug: string,
  articleTitle: string,
  sessionId: string | undefined,
  session: string,
  cookie: string,
): Promise<StepResult> {
  if (!textItems.length) return { status: 'skipped' };

  try {
    // O vídeo longo precisa ter prioridade. Mesmo que o usuário tenha
    // escolhido uma data anterior, libera as peças sociais somente depois
    // de uma janela mínima para a publicação do YouTube.
    const socialReleaseAt = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();
    const scheduledItems = textItems.map((item) => ({
      ...item,
      scheduledAt: item.scheduledAt > socialReleaseAt ? item.scheduledAt : socialReleaseAt,
    }));

    const res = await fetch(`${base}/api/csm/pipeline-submit`, {
      method: 'POST',
      headers: csmHeaders(session, cookie),
      body: JSON.stringify({
        articleSlug,
        articleTitle,
        sessionId,
        items: scheduledItems,
      }),
      signal: AbortSignal.timeout(30_000),
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) return { status: 'error', detail: data.error ?? `HTTP ${res.status}` };

    const queued = data.results?.textPublished ?? 0;
    const errors = (data.results?.errors ?? []) as string[];
    return {
      status: errors.length && !queued ? 'error' : 'ok',
      detail: `${queued} item(s) agendado(s) na social_queue${errors.length ? ` · ${errors.length} erro(s)` : ''}`,
    };
  } catch (err) {
    return { status: 'error', detail: err instanceof Error ? err.message : String(err) };
  }
}

// ── Etapa 2 — Pipeline de vídeo ───────────────────────────────────────────────

async function triggerVideoPipeline(
  base: string,
  youtubeScript: string | undefined,
  videoItems: NonNullable<ApprovePackageRequest['videoItems']>,
  articleSlug: string,
  articleTitle: string,
  sessionId: string | undefined,
  session: string,
  cookie: string,
): Promise<StepResult> {
  const hasYT    = youtubeScript && youtubeScript.trim().length > 100;
  const hasVideo = videoItems.length > 0;
  if (!hasYT && !hasVideo) return { status: 'skipped' };

  try {
    const res = await fetch(`${base}/api/csm/pipeline-submit`, {
      method: 'POST',
      headers: csmHeaders(session, cookie),
      body: JSON.stringify({
        articleSlug,
        articleTitle,
        sessionId,
        youtubeScript: hasYT ? youtubeScript : undefined,
        items: videoItems,
      }),
      signal: AbortSignal.timeout(60_000),
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) return { status: 'error', detail: data.error ?? `HTTP ${res.status}` };

    const triggered = data.results?.videoPipelineTriggered ?? 0;
    return { status: 'ok', detail: `${triggered} pipeline(s) disparado(s)` };
  } catch (err) {
    return { status: 'error', detail: err instanceof Error ? err.message : String(err) };
  }
}

// ── Handler ───────────────────────────────────────────────────────────────────

export async function POST(request: Request): Promise<Response> {
  if (!isCsmAuthenticated(request)) return csmUnauthorized();

  let body: ApprovePackageRequest;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const {
    textItems = [], videoItems = [],
    youtubeScript, articleSlug, articleTitle,
    sessionId, csmSession = 'authenticated',
  } = body;

  if (!articleSlug) {
    return NextResponse.json({ error: 'articleSlug required' }, { status: 400 });
  }

  // O gate editorial também é validado no servidor. A UI pode esconder abas,
  // mas não deve ser possível aprovar derivações sem artigo publicado e sem
  // um pacote persistido pronto para revisão.
  if (sessionId) {
    const tenantId = request.headers.get('x-tenant-id') || null;
    const session = await loadSession(sessionId, tenantId);
    const draft = (session as { draft?: Record<string, unknown> } | null)?.draft;
    if (!draft?.publishedArticleUrl) {
      return NextResponse.json({ error: 'O artigo precisa estar publicado antes da aprovação.' }, { status: 409 });
    }
    if (draft.packageStatus !== 'ready' || (!draft.manifestV2 && !draft.repurposedData)) {
      return NextResponse.json({ error: 'O pacote ainda não está pronto para revisão.' }, { status: 409 });
    }
  }

  const base = baseUrl(request);
  const cookie = request.headers.get('cookie') || '';

  // O vídeo é disparado primeiro. Só depois de aceito pela pipeline social
  // entra na fila, com uma janela mínima de 24h para manter a ordem editorial.
  const videoResult = (youtubeScript || videoItems.length)
    ? await triggerVideoPipeline(base, youtubeScript, videoItems, articleSlug, articleTitle, sessionId, csmSession, cookie)
    : { status: 'skipped' as const };
  const textResult = textItems.length
    ? await enqueueText(base, textItems, articleSlug, articleTitle, sessionId, csmSession, cookie)
    : { status: 'skipped' as const };

  const errors = [textResult, videoResult]
    .filter((r) => r.status === 'error')
    .map((r) => r.detail ?? 'unknown error');

  const result: ApproveResult = {
    text:        textResult,
    video:       videoResult,
    errors,
    approved_at: new Date().toISOString(),
  };

  // 207 Multi-Status se houver erros parciais, 200 se tudo ok ou skipped
  const status = errors.length > 0 ? 207 : 200;

  if (status === 200 && sessionId) {
    try {
      const tenantId = request.headers.get('x-tenant-id') || null;
      const session = await loadSession(sessionId, tenantId);
      const currentDraft = (session as { draft?: Record<string, unknown> } | null)?.draft ?? {};
      await saveDraftToSession(sessionId, {
        ...currentDraft,
        workflowStage: 'approved',
        packageApprovedAt: result.approved_at,
      }, tenantId);
    } catch (err) {
      console.error('[approve-package] failed to persist approval state', err);
    }
  }

  return NextResponse.json(result, { status });
}
