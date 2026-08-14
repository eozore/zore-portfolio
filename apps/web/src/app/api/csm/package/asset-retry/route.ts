/**
 * POST /api/csm/package/asset-retry
 *
 * Reexecuta UM asset do pacote editorial (thumbnails ou copies) sem tocar nos
 * demais — o roteiro/manifesto/slides já aprovados permanecem intocados. Usado
 * pela ReviewTab quando um pedaço específico falhou na geração (ex: thumbnail
 * agent deu timeout mas o roteiro e os copies saíram certos).
 *
 * Body: { sessionId: string, asset: 'thumbnails' | 'copies' }
 */

import { NextResponse } from 'next/server';
import { loadSession, saveDraftToSession } from '@/lib/session';
import { isCsmAuthenticated, csmUnauthorized } from '@/lib/csmAuth';
import { cmoAgentUrl, cmoAgentHeaders } from '@/lib/cmoAgent';
import { getEnabledChannelToggles } from '@/lib/channelToggles';
import { isChannelEnabled } from '@/lib/channels';

export const maxDuration = 180;

type Asset = 'thumbnails' | 'copies';

export async function POST(request: Request): Promise<Response> {
  if (!isCsmAuthenticated(request)) return csmUnauthorized();

  let body: { sessionId?: string; asset?: Asset };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const { sessionId, asset } = body;
  if (!sessionId || (asset !== 'thumbnails' && asset !== 'copies')) {
    return NextResponse.json({ error: 'sessionId and asset ("thumbnails" | "copies") required' }, { status: 400 });
  }

  const tenantId = request.headers.get('x-tenant-id') || null;
  const session = await loadSession(sessionId, tenantId);
  const draft = (session as { draft?: Record<string, unknown> } | null)?.draft;
  if (!draft) {
    return NextResponse.json({ error: 'Sessão não encontrada' }, { status: 404 });
  }
  if (!draft.pauta || !draft.generatedContent) {
    return NextResponse.json({ error: 'Pacote ainda não tem pauta/artigo suficientes para retry.' }, { status: 409 });
  }

  if (asset === 'thumbnails') {
    const toggles = await getEnabledChannelToggles(tenantId);
    if (!isChannelEnabled(toggles, 'youtube_video')) {
      return NextResponse.json({ error: 'Canal de YouTube está desligado em Configurações.' }, { status: 409 });
    }
  }

  try {
    const res = await fetch(`${cmoAgentUrl()}/package`, {
      method: 'POST',
      headers: cmoAgentHeaders(tenantId),
      body: JSON.stringify({
        pauta: draft.pauta,
        articleContent: draft.generatedContent,
        category: draft.category || 'ml',
        language: draft.language || 'pt-BR',
        sessionId,
        phase: asset,
        manifest: draft.manifestV2 ?? null,
      }),
      signal: AbortSignal.timeout(150_000),
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      return NextResponse.json({ error: data.error || `HTTP ${res.status}` }, { status: 502 });
    }

    const patch: Record<string, unknown> =
      asset === 'thumbnails' ? { thumbnails: data.thumbnails ?? null } : { specialistCopies: data.copies ?? null };

    const nextDraft = { ...draft, ...patch };
    await saveDraftToSession(sessionId, nextDraft, tenantId);

    return NextResponse.json({ success: true, ...patch, partialErrors: data.partialErrors ?? [] });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
