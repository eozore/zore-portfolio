/**
 * GET /api/csm/pipeline-status?sessionId=...
 *
 * Retorna o status atual do pipeline de produção (TTS → HeyGen → VideoEditor → Publisher)
 * lendo diretamente do Firestore (stages gravados pelos jobs Python).
 * Também retorna os itens agendados na fila social.
 */

import { NextResponse } from 'next/server';
import { getFirestoreDb } from '@/lib/firebase';
import { dbPaths } from '@/lib/dbPaths';
import { isCsmAuthenticated, csmUnauthorized } from '@/lib/csmAuth';

export const dynamic = 'force-dynamic';

export async function GET(request: Request): Promise<Response> {
  if (!isCsmAuthenticated(request)) return csmUnauthorized();
  const { searchParams } = new URL(request.url);
  const sessionId = searchParams.get('sessionId');
  const tenantId = request.headers.get('x-tenant-id') || null;

  if (!sessionId) {
    return NextResponse.json({ error: 'sessionId required' }, { status: 400 });
  }

  const db = getFirestoreDb();
  if (!db) {
    return NextResponse.json({ stages: {}, scheduledItems: [] });
  }

  try {
    let stages: Record<string, unknown> = {};
    let projectId: string | null = null;

    // A pipeline grava content_projects/{projectId}; a implementação anterior
    // consultava collections legadas (sessions/projects), portanto nunca
    // mostrava o progresso real no dashboard.
    const projectSnap = await db.collection(dbPaths.contentProjects(tenantId))
      .where('session_id', '==', sessionId)
      .limit(20)
      .get()
      .catch(() => null);
    const latestProject = projectSnap?.docs
      .sort((a, b) => String(b.data().created_at ?? '').localeCompare(String(a.data().created_at ?? '')))[0];
    if (latestProject) {
      projectId = latestProject.id;
      stages = latestProject.data().stages ?? {};
    }

    // Busca itens agendados na social queue para esta sessão
    const queueSnap = await db.collection(dbPaths.socialQueue(tenantId))
      .where('session_id', '==', sessionId)
      .orderBy('scheduled_at', 'asc')
      .limit(20)
      .get()
      .catch(() => null);

    const scheduledItems = queueSnap
      ? queueSnap.docs.map((doc) => {
          const d = doc.data();
          return {
            id:          doc.id,
            platform:    d.platform ?? '',
            format:      d.format ?? '',
            title:       d.title ?? '',
            scheduledAt: d.scheduled_at ?? '',
            status:      d.status ?? 'em_revisao',
          };
        })
      : [];

    // Normaliza stages para o formato esperado pelo frontend
    const normalizedStages: Record<string, { status: string; detail?: string; started_at?: number; completed_at?: number }> = {};

    const stageMap: Record<string, string> = {
      tts:          'tts',
      avatar:       'avatar',
      editor:       'video_editor',
      publisher:    'publisher',
      // Corte vertical: etapa sob demanda, depois da aprovação do vídeo longo.
      vertical_cut: 'vertical_cut',
    };

    for (const [firestoreKey, frontendKey] of Object.entries(stageMap)) {
      const s = (stages as Record<string, Record<string, unknown>>)[firestoreKey];
      if (s) {
        normalizedStages[frontendKey] = {
          status:       String(s.status ?? 'waiting'),
          detail:       s.error_message ? String(s.error_message) : s.detail ? String(s.detail) : undefined,
          started_at:   s.started_at   ? Number(s.started_at)   * 1000 : undefined,
          completed_at: s.completed_at ? Number(s.completed_at) * 1000 : undefined,
        };
      }
    }

    // Adiciona estágio virtual "scheduled" se houver itens na fila
    if (scheduledItems.length > 0) {
      normalizedStages['scheduled'] = {
        status: 'done',
        detail: `${scheduledItems.length} item(s) na fila`,
      };
    }

    // O pacote de conteúdos derivados (vertical, carrosséis, copies) só pode
    // ser gerado depois que o vídeo do YouTube existe e foi publicado — ele é
    // derivado desse vídeo. O frontend precisa desses dois fatos para decidir
    // se habilita o botão, então eles vêm aqui em vez de num fetch extra.
    const projectData    = latestProject?.data() ?? {};
    const editorStage    = (stages as Record<string, Record<string, unknown>>).editor ?? {};
    const publishResults = (projectData.publish_results ?? {}) as Record<string, string>;
    const youtubeVideoId = publishResults.youtube ?? null;

    return NextResponse.json({
      stages:         normalizedStages,
      scheduledItems,
      projectId:      projectId ?? null,
      video: {
        horizontalReady: editorStage.status === 'completed' && Boolean(editorStage.horizontal_url),
        durationSeconds: editorStage.duration_s ? Number(editorStage.duration_s) : null,
        avatarShare:     editorStage.avatar_share ? Number(editorStage.avatar_share) : null,
        youtubeVideoId,
        youtubeUrl:      youtubeVideoId ? `https://youtu.be/${youtubeVideoId}` : null,
        verticalUrl:     (editorStage.vertical_url as string) || null,
      },
    });

  } catch (err) {
    console.error('[pipeline-status] Error:', err);
    return NextResponse.json({ stages: {}, scheduledItems: [], error: String(err) });
  }
}
