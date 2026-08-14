/**
 * POST /api/csm/calendar/retry
 *
 * Retry de um item com falha no calendário.
 *
 * Dois cenários cobertos:
 *
 * A) social_queue (texto — LinkedIn, Threads, etc.)
 *    → Reseta status=planned, retry_count=0, error_message=null
 *    → O publisher-scheduled vai pegar na próxima rodada
 *
 * B) content_projects (pipeline de vídeo — TTS→Avatar→Editor→Publisher)
 *    → Detecta o stage com falha (tts | avatar | editor | publisher)
 *    → Reseta o stage (e os seguintes) para pending no Firestore
 *    → Republica a mensagem Pub/Sub correta para reiniciar a partir daquele stage,
 *      SEM refazer os stages anteriores já concluídos (cada jornada de produção
 *      é um content_projects/{projectId}; cada stage é um asset independente).
 *
 * Body: { id: string, collection: 'social_queue' | 'content_projects' }
 */

import { NextResponse } from 'next/server';
import { isCsmAuthenticated, csmUnauthorized } from '@/lib/csmAuth';
import { getFirestoreDb } from '@/lib/firebase';
import { dbPaths } from '@/lib/dbPaths';
import { PubSub } from '@google-cloud/pubsub';
import { computeHealth } from '@/lib/pipelineHealth';

const GCP_PROJECT_ID   = process.env.FIREBASE_PROJECT_ID || 'vazfy-417019';
const PIPELINE_TOPICS  = {
  tts:       'content-pipeline.package-approved',
  avatar:    'content-pipeline.tts-completed',
  editor:    'content-pipeline.avatar-completed',
  publisher: 'content-pipeline.video-ready',
} as const;
const STAGE_ORDER = ['tts', 'avatar', 'editor', 'publisher'] as const;
type StageName = (typeof STAGE_ORDER)[number];

export async function POST(request: Request): Promise<Response> {
  if (!isCsmAuthenticated(request)) return csmUnauthorized();
  const db = getFirestoreDb();
  if (!db) return NextResponse.json({ error: 'Firestore unavailable' }, { status: 500 });

  let body: { id: string; collection: 'social_queue' | 'content_projects' };
  try { body = await request.json(); }
  catch { return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 }); }

  const { id, collection } = body;
  if (!id || !collection) {
    return NextResponse.json({ error: 'id and collection required' }, { status: 400 });
  }

  const tenantId = request.headers.get('x-tenant-id') || null;
  const collectionPath = collection === 'social_queue'
    ? dbPaths.socialQueue(tenantId)
    : dbPaths.contentProjects(tenantId);
  const ref  = db.collection(collectionPath).doc(id);
  const snap = await ref.get();
  if (!snap.exists) {
    return NextResponse.json({ error: `Document ${id} not found` }, { status: 404 });
  }

  const data = snap.data()!;
  const now  = new Date().toISOString();

  // ── A: Texto social (social_queue) ───────────────────────────────────────
  if (collection === 'social_queue') {
    if (data.status === 'published') {
      return NextResponse.json({ error: 'Item já publicado — retry não permitido' }, { status: 409 });
    }
    await ref.update({
      status:        'planned',
      retry_count:   0,
      attempts:      0,
      error_message: null,
      error:         null,
      errorCode:     null,
      updated_at:    now,
      updatedAt:     now,
    });
    return NextResponse.json({ success: true, message: 'Item resetado para planned. Será publicado na próxima rodada do scheduler.' });
  }

  // ── B: Pipeline de vídeo (content_projects) ───────────────────────────────
  const stages = data.stages ?? {};

  // Encontra o stage travado — erro explícito OU rodando/pendente há mais
  // tempo do que o esperado (Job morto por OOM, mensagem Pub/Sub perdida etc.
  // nunca gravam error_message, então "error" sozinho não pega tudo).
  const failedStage: StageName | undefined = STAGE_ORDER.find((s) => {
    const stageData = stages[s];
    if (stageData?.status === 'error') return true;
    const startedAtMs = stageData?.started_at ? stageData.started_at * 1000 : undefined;
    return computeHealth(stageData?.status, startedAtMs, s) === 'stuck';
  });

  if (!failedStage) {
    return NextResponse.json({
      error: 'Nenhum stage travado ou com erro encontrado. Verifique o status do projeto.',
      stages: Object.fromEntries(Object.entries(stages).map(([k, v]: [string, any]) => [k, v?.status])),
    }, { status: 400 });
  }

  // Reseta o stage com falha e todos os stages seguintes para pending.
  // Stages já concluídos ANTES dele não são tocados — é o que garante que o
  // retry reprocesse só o asset quebrado, não a jornada inteira.
  const failIdx      = STAGE_ORDER.indexOf(failedStage);
  const updateData: Record<string, unknown> = { updated_at: now };

  STAGE_ORDER.slice(failIdx).forEach((s) => {
    updateData[`stages.${s}.status`]        = 'pending';
    updateData[`stages.${s}.error_message`] = null;
    updateData[`stages.${s}.error_type`]    = null;
    updateData[`stages.${s}.started_at`]    = null;
    updateData[`stages.${s}.completed_at`]  = null;
  });
  updateData['status'] = failedStage === 'publisher' ? 'awaiting_publication' : 'generating_media';

  await ref.update(updateData);

  // Monta a mensagem Pub/Sub para o stage correto
  const topic  = PIPELINE_TOPICS[failedStage];
  const pubsub = new PubSub({ projectId: GCP_PROJECT_ID });

  let pubsubMessage: Record<string, unknown>;

  if (failedStage === 'tts') {
    pubsubMessage = {
      project_id:        id,
      manifest_gcs_path: data.manifest_url,
      channels_approved: data.channels_approved ?? ['youtube', 'youtube_short', 'instagram_reel'],
      approved_at:       now,
      cost_limit:        data.cost_limit ?? 50.0,
    };
  } else if (failedStage === 'avatar') {
    // Para reiniciar o avatar, precisamos dos caminhos de áudio do TTS
    // Eles ficam salvos no stage tts do projeto se o TTS completou
    const audioPathsH = stages.tts?.audio_paths?.horizontal ?? [];
    const audioPathsV = stages.tts?.audio_paths?.vertical   ?? [];
    pubsubMessage = {
      project_id:     id,
      audio_paths:    { horizontal: audioPathsH, vertical: audioPathsV },
      total_cost_usd: stages.tts?.cost_real ?? 0,
      segment_count:  stages.tts?.segment_count ?? 0,
    };
  } else if (failedStage === 'editor') {
    // editor: reinicia com os vídeos por segmento do avatar (contrato atual —
    // AvatarCompletedMsg em agents/pipeline/shared/models.py). O avatar_job
    // grava cada segmento em stages.avatar.segment_videos.{horizontal,vertical}
    // como {seg_id, status, video_url} — só os segmentos "completed" entram
    // na lista final, na mesma lógica usada pelo heygen_callback ao publicar
    // o avatar_completed original.
    const segmentVideos = stages.avatar?.segment_videos ?? {};
    const hSegs = (segmentVideos.horizontal ?? []) as { seg_id: string; status: string; video_url?: string }[];
    const vSegs = (segmentVideos.vertical   ?? []) as { seg_id: string; status: string; video_url?: string }[];
    const completed = (segs: typeof hSegs) => segs.filter((s) => s.status === 'completed' && s.video_url);
    const hPaths = completed(hSegs).map((s) => s.video_url);
    const vPaths = completed(vSegs).map((s) => s.video_url);
    if (!hPaths.length && !vPaths.length) {
      return NextResponse.json({
        error: 'Stage "avatar" não tem segment_videos completos no Firestore. Retente o stage "avatar" primeiro.',
      }, { status: 409 });
    }
    pubsubMessage = {
      project_id:             id,
      horizontal_video_paths: hPaths,
      vertical_video_paths:   vPaths,
      segment_ids:            completed(hSegs).map((s) => s.seg_id),
      vertical_segment_ids:   completed(vSegs).map((s) => s.seg_id),
      duration_seconds:       0,
      total_cost_usd:         stages.avatar?.cost_real ?? 0,
    };
  } else {
    // publisher: reinicia com o vídeo final já montado pelo editor
    const horizontalUrl = stages.editor?.horizontal_url ?? '';
    const verticalUrl   = stages.editor?.vertical_url   ?? '';
    if (!horizontalUrl && !verticalUrl) {
      return NextResponse.json({
        error: 'Stage "editor" não tem vídeo final gravado no Firestore. Retente o stage "editor" primeiro.',
      }, { status: 409 });
    }
    pubsubMessage = {
      project_id:        id,
      horizontal_final:  horizontalUrl,
      vertical_final:    verticalUrl,
      duration_seconds:  0,
      trigger:           data.publish_trigger ?? 'scheduled',
    };
  }

  try {
    await pubsub.topic(topic).publishMessage({
      data: Buffer.from(JSON.stringify(pubsubMessage)),
    });
  } catch (err) {
    // Reverte o Firestore se Pub/Sub falhar
    const revertData: Record<string, unknown> = { updated_at: now };
    revertData[`stages.${failedStage}.status`] = 'error';
    await ref.update(revertData).catch(() => {});
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: `Firestore resetado, mas Pub/Sub falhou: ${msg}` }, { status: 502 });
  }

  return NextResponse.json({
    success: true,
    message: `Pipeline reiniciado a partir do stage "${failedStage}". Mensagem publicada no tópico ${topic}.`,
    retried_stage: failedStage,
    project_id:    id,
  });
}
