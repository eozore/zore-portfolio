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
 * B) content_projects (pipeline de vídeo — TTS→Avatar→Editor)
 *    → Detecta o stage com falha (tts | avatar | editor)
 *    → Reseta o stage para pending no Firestore
 *    → Republica a mensagem Pub/Sub correta para reiniciar a partir daquele stage
 *
 * Body: { id: string, collection: 'social_queue' | 'content_projects' }
 */

import { NextResponse } from 'next/server';
import { isCsmAuthenticated, csmUnauthorized } from '@/lib/csmAuth';
import { getFirestoreDb } from '@/lib/firebase';
import { dbPaths } from '@/lib/dbPaths';
import { PubSub } from '@google-cloud/pubsub';

const GCP_PROJECT_ID   = process.env.FIREBASE_PROJECT_ID || 'vazfy-417019';
const PIPELINE_TOPICS  = {
  tts:    'content-pipeline.package-approved',
  avatar: 'content-pipeline.tts-completed',
  editor: 'content-pipeline.avatar-completed',
} as const;

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

  // Encontra o stage com falha — na ordem TTS → Avatar → Editor
  const failedStage = (['tts', 'avatar', 'editor'] as const).find(
    (s) => stages[s]?.status === 'error'
  );

  if (!failedStage) {
    return NextResponse.json({
      error: 'Nenhum stage com erro encontrado. Verifique o status do projeto.',
      stages: Object.fromEntries(Object.entries(stages).map(([k, v]: [string, any]) => [k, v?.status])),
    }, { status: 400 });
  }

  // Reseta o stage com falha e todos os stages seguintes para pending
  const stageOrder = ['tts', 'avatar', 'editor'] as const;
  const failIdx    = stageOrder.indexOf(failedStage);
  const updateData: Record<string, unknown> = { updated_at: now };

  stageOrder.slice(failIdx).forEach((s) => {
    updateData[`stages.${s}.status`]        = 'pending';
    updateData[`stages.${s}.error_message`] = null;
    updateData[`stages.${s}.error_type`]    = null;
    updateData[`stages.${s}.started_at`]    = null;
    updateData[`stages.${s}.completed_at`]  = null;
  });
  updateData['status'] = 'generating_media';

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
  } else {
    // editor: reinicia com os vídeos do avatar
    pubsubMessage = {
      project_id:            id,
      horizontal_video_path: stages.avatar?.lipsync_jobs?.horizontal?.video_url ?? '',
      vertical_video_path:   stages.avatar?.lipsync_jobs?.vertical?.video_url   ?? '',
      duration_seconds:      0,
      total_cost_usd:        stages.avatar?.cost_real ?? 0,
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
