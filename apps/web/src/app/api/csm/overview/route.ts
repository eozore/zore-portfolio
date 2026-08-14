/**
 * GET /api/csm/overview
 *
 * Painel único com TODOS os projetos em andamento — pacotes editoriais
 * (csm_sessions) e pipelines de vídeo (content_projects) — cada um com um
 * status computado e uma flag de "travado" quando uma etapa assíncrona passa
 * do tempo esperado sem concluir nem falhar.
 *
 * Existe porque hoje um projeto só é visível se você estiver EXATAMENTE
 * naquela sessão do navegador — um content_project com TTS travado há dias
 * fica invisível para sempre a menos que você abra a sessão específica que o
 * originou. Isso junta tudo num lugar só.
 */

import { NextResponse } from 'next/server';
import { getFirestoreDb } from '@/lib/firebase';
import { dbPaths } from '@/lib/dbPaths';
import { isCsmAuthenticated, csmUnauthorized } from '@/lib/csmAuth';
import { computeHealth, elapsedLabel, type HealthStatus } from '@/lib/pipelineHealth';

export const dynamic = 'force-dynamic';

interface OverviewItem {
  id: string;
  kind: 'pacote' | 'video';
  title: string;
  status: HealthStatus;
  statusLabel: string;
  detail: string;
  updatedAt: number;
  updatedLabel: string;
  sessionId?: string;
  href?: string;
}

const PACKAGE_STATUS_LABEL: Record<string, string> = {
  idle: 'Aguardando publicação do artigo',
  generating: 'Gerando pacote (roteiro/thumbnails/copies)',
  script_ready: 'Roteiro pronto — aguardando aprovação',
  ready: 'Pacote pronto para revisão',
  error: 'Falha na geração do pacote',
};

const STAGE_LABEL: Record<string, string> = {
  tts: 'Síntese de voz',
  avatar: 'Avatar HeyGen',
  editor: 'Edição de vídeo',
  publisher: 'Publicação',
};

export async function GET(request: Request): Promise<Response> {
  if (!isCsmAuthenticated(request)) return csmUnauthorized();
  const tenantId = request.headers.get('x-tenant-id') || null;
  const db = getFirestoreDb();
  if (!db) return NextResponse.json({ items: [] });

  const now = Date.now();
  const items: OverviewItem[] = [];

  try {
    // ── Pacotes editoriais (csm_sessions) ──────────────────────────────────
    const sessionsSnap = await db.collection(dbPaths.sessions(tenantId))
      .orderBy('updatedAt', 'desc')
      .limit(40)
      .get()
      .catch(() => null);

    for (const doc of sessionsSnap?.docs ?? []) {
      const data = doc.data();
      const draft = data.draft ?? {};
      const pauta = draft.pauta ?? {};
      const title: string = pauta.titulo || draft.suggestedTitle || draft.topic || '';
      if (!title) continue; // sessão vazia (nunca saiu do "idea") — não é um projeto ainda

      const rawStatus: string = draft.packageStatus ?? 'idle';
      const startedAt: number | undefined = draft.packageStartedAt;
      const health = rawStatus === 'generating'
        ? computeHealth('running', startedAt, 'package', now)
        : rawStatus === 'error' ? 'error'
        : (rawStatus === 'ready' || rawStatus === 'script_ready') ? 'done'
        : 'idle';

      items.push({
        id: doc.id,
        kind: 'pacote',
        title,
        status: health,
        statusLabel: PACKAGE_STATUS_LABEL[rawStatus] ?? rawStatus,
        detail: draft.packageError || (draft.publishedArticleUrl ? `Artigo: ${draft.publishedArticleUrl}` : ''),
        updatedAt: data.updatedAt ?? 0,
        updatedLabel: elapsedLabel(data.updatedAt, now),
        sessionId: doc.id,
      });
    }
  } catch (err) {
    console.error('[overview] sessions query failed:', err);
  }

  try {
    // ── Pipelines de vídeo (content_projects) ──────────────────────────────
    const projectsSnap = await db.collection(dbPaths.contentProjects(tenantId))
      .orderBy('created_at', 'desc')
      .limit(40)
      .get()
      .catch(() => null);

    for (const doc of projectsSnap?.docs ?? []) {
      const data = doc.data();
      const stages: Record<string, { status?: string; started_at?: number; completed_at?: number }> = data.stages ?? {};
      const stageOrder = ['tts', 'avatar', 'editor', 'publisher'];

      // Acha a primeira etapa que não terminou — é ela que define o status do projeto.
      let currentStage: string | null = null;
      for (const s of stageOrder) {
        const st = stages[s]?.status;
        if (st && st !== 'completed' && st !== 'published') { currentStage = s; break; }
      }

      let health: HealthStatus = 'done';
      let detail = 'Todas as etapas concluídas';
      if (currentStage) {
        const stageData = stages[currentStage];
        const startedAtMs = stageData?.started_at ? stageData.started_at * 1000 : undefined;
        health = computeHealth(stageData?.status, startedAtMs, currentStage, now);
        detail = `${STAGE_LABEL[currentStage] ?? currentStage}${health === 'stuck' ? ` — sem atualização ${elapsedLabel(startedAtMs, now)}` : ''}`;
      }

      const updatedAtMs = (data.updated_at ? Date.parse(data.updated_at) : null)
        ?? (stages[currentStage ?? '']?.started_at ? stages[currentStage!]!.started_at! * 1000 : now);

      items.push({
        id: doc.id,
        kind: 'video',
        title: data.title || doc.id,
        status: health,
        statusLabel: currentStage ? `Etapa: ${STAGE_LABEL[currentStage] ?? currentStage}` : 'Publicado',
        detail,
        updatedAt: updatedAtMs,
        updatedLabel: elapsedLabel(updatedAtMs, now),
        sessionId: data.session_id,
      });
    }
  } catch (err) {
    console.error('[overview] content_projects query failed:', err);
  }

  items.sort((a, b) => b.updatedAt - a.updatedAt);
  const stuckCount = items.filter((i) => i.status === 'stuck').length;
  const errorCount = items.filter((i) => i.status === 'error').length;

  return NextResponse.json({ items, stuckCount, errorCount });
}
