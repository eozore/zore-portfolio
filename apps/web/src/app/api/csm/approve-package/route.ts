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
import { getEnabledChannelToggles } from '@/lib/channelToggles';
import { isChannelEnabled, type ChannelToggles } from '@/lib/channels';
import { planWeek, summarizePlan, PLAN_HORIZON_DAYS } from '@/lib/contentPlanner';

/** Mapeia (platform, format) dos itens aprovados para o id de canal em lib/channels.ts. */
function channelIdForItem(platform: string, format: string): string | null {
  const key = `${platform}:${format}`;
  const map: Record<string, string> = {
    'linkedin:text': 'linkedin_text',
    'linkedin:image': 'linkedin_text',
    'threads:thread': 'threads_posts',
    'facebook:text': 'facebook_post',
    'facebook:image': 'facebook_post',
    'x:text': 'x_post',
    'instagram:reel': 'instagram_reels',
    'instagram:short': 'youtube_shorts',
    'instagram:carousel': 'instagram_carousel',
    'instagram:story': 'instagram_stories',
    'instagram:image': 'instagram_feed',
  };
  return map[key] ?? null;
}

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
  /** Ids de canal ignorados no servidor por estarem desligados em Configurações. */
  blockedChannels?: string[];
  /** Calendário da semana: o que sai em cada dia e horário. */
  plan?: {
    day: number;
    date: string;
    items: { platform: string; format: string; title: string; scheduledAt: string }[];
  }[];
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
  /** Carrossel, stories e posts de imagem — já com imagem renderizada.
   *  Antes eram gerados e descartados: nunca chegavam à publicação. */
  mediaItems?: {
    id:        string;
    platform:  string;
    format:    string;
    title:     string;
    copy:      string;
    imageUrl?:  string;
    imageUrls?: string[];
    scheduledAt: string;
    status:    'aprovado';
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
): Promise<StepResult & { plan?: ApproveResult['plan'] }> {
  if (!textItems.length) return { status: 'skipped' };

  try {
    // Distribui a campanha ao longo de 7 dias em vez de enfileirar tudo com o
    // mesmo horário (o publisher roda de hora em hora e despejaria a campanha
    // inteira na primeira execução). O vídeo do YouTube é a âncora e sai antes,
    // por isso nada social é agendado para o dia 0.
    const scheduledItems = planWeek(textItems);
    const plan = summarizePlan(scheduledItems).map((d) => ({
      day: d.day,
      date: d.date,
      items: d.items.map((i) => ({
        platform: i.platform,
        format: i.format,
        title: String((i as { title?: string }).title ?? ''),
        scheduledAt: i.scheduledAt,
      })),
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
      detail: `${queued} item(s) distribuído(s) ao longo de ${PLAN_HORIZON_DAYS} dias${errors.length ? ` · ${errors.length} erro(s)` : ''}`,
      plan,
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
    textItems: rawTextItems = [], videoItems: rawVideoItems = [], mediaItems: rawMediaItems = [],
    youtubeScript, articleSlug, articleTitle,
    sessionId, csmSession = 'authenticated',
  } = body;

  if (!articleSlug) {
    return NextResponse.json({ error: 'articleSlug required' }, { status: 400 });
  }

  // Defesa em profundidade: mesmo que o client tente aprovar um item de canal
  // desligado (bug de UI, chamada direta à API), o servidor nunca enfileira.
  const tenantIdForChannels = request.headers.get('x-tenant-id') || null;
  const channelToggles: ChannelToggles = await getEnabledChannelToggles(tenantIdForChannels);
  const blockedChannels = new Set<string>();
  const keepEnabled = <T extends { platform: string; format: string }>(items: T[]): T[] =>
    items.filter((item) => {
      const channelId = channelIdForItem(item.platform, item.format);
      if (channelId && !isChannelEnabled(channelToggles, channelId)) {
        blockedChannels.add(channelId);
        return false;
      }
      return true;
    });

  const textItems = keepEnabled(rawTextItems);
  const videoItems = keepEnabled(rawVideoItems);
  const mediaItems = keepEnabled(rawMediaItems);

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
  // Media e texto compartilham a fila social e o mesmo planejamento semanal —
  // o publisher-scheduled trata ambos, e o contentPlanner intercala por
  // plataforma, então enfileirar juntos distribui melhor a campanha.
  const queueItems = [...textItems, ...mediaItems];
  const textResult = queueItems.length
    ? await enqueueText(base, queueItems, articleSlug, articleTitle, sessionId, csmSession, cookie)
    : { status: 'skipped' as const };

  const errors = [textResult, videoResult]
    .filter((r) => r.status === 'error')
    .map((r) => r.detail ?? 'unknown error');

  const result: ApproveResult = {
    text:        textResult,
    video:       videoResult,
    errors,
    approved_at: new Date().toISOString(),
    ...(blockedChannels.size ? { blockedChannels: [...blockedChannels] } : {}),
    ...(('plan' in textResult && textResult.plan) ? { plan: textResult.plan } : {}),
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
