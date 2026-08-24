/**
 * POST /api/csm/derive-vertical
 *
 * Produz a peça vertical (Reel + Short) A PARTIR do vídeo do YouTube.
 *
 * É o passo que o dono do canal aciona depois de assistir ao vídeo longo e
 * tornar público — não antes. A peça é um recorte do que já existe:
 *
 *   • trechos de avatar → crop central 9:16 dos clipes já gerados
 *   • trechos de ilustração → HTML vertical com o MESMO áudio TTS
 *
 * Zero chamadas ao HeyGen, zero ao ElevenLabs. Antes desta rota, cada Reel e
 * cada Short era um `content_project` novo, com roteiro, voz, avatar e edição
 * próprios — três peças curtas custavam três produções completas e não tinham
 * relação nenhuma com o vídeo publicado.
 *
 * O gate fica no servidor: a UI esconde o botão, mas chamar a API direto
 * também precisa respeitar "o vídeo longo existe e está pronto".
 */

import { NextResponse } from 'next/server';
import { PubSub } from '@google-cloud/pubsub';
import { getFirestoreDb } from '@/lib/firebase';
import { dbPaths } from '@/lib/dbPaths';
import { isCsmAuthenticated, csmUnauthorized } from '@/lib/csmAuth';

const VERTICAL_CUT_TOPIC = 'content-pipeline.vertical-cut';
const GCP_PROJECT_ID     = process.env.FIREBASE_PROJECT_ID || 'vazfy-417019';

/** Reel e Short são o MESMO arquivo em duas plataformas. */
const VERTICAL_CHANNELS = ['instagram_reel', 'youtube_short'];

export const maxDuration = 60;

interface DeriveRequest {
  projectId: string;
  /** Sobrescreve os canais de destino. Vazio = só gera, não publica. */
  channels?: string[];
}

export async function POST(request: Request): Promise<Response> {
  if (!isCsmAuthenticated(request)) return csmUnauthorized();

  let body: DeriveRequest;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }
  if (!body.projectId) {
    return NextResponse.json({ error: 'projectId required' }, { status: 400 });
  }

  const tenantId = request.headers.get('x-tenant-id') || null;
  const db = getFirestoreDb();
  if (!db) {
    return NextResponse.json({ error: 'Firestore indisponível' }, { status: 503 });
  }

  const ref  = db.collection(dbPaths.contentProjects(tenantId)).doc(body.projectId);
  const snap = await ref.get();
  if (!snap.exists) {
    return NextResponse.json({ error: `Projeto ${body.projectId} não existe` }, { status: 404 });
  }

  const project = snap.data() ?? {};
  const stages  = (project.stages ?? {}) as Record<string, Record<string, unknown>>;
  const editor  = stages.editor ?? {};

  if (editor.status !== 'completed' || !editor.horizontal_url) {
    return NextResponse.json(
      {
        error: 'O vídeo do YouTube ainda não está pronto. ' +
               'A peça vertical é derivada dele, então não há o que cortar.',
        editorStatus: editor.status ?? 'pending',
      },
      { status: 409 },
    );
  }
  if (!editor.clips_prefix) {
    return NextResponse.json(
      {
        error: 'Este vídeo foi montado por uma versão anterior do editor, que não ' +
               'guardava os clipes por segmento. Reprocesse a etapa de edição antes de cortar.',
      },
      { status: 409 },
    );
  }

  const verticalStage = stages.vertical_cut ?? {};
  if (verticalStage.status === 'running') {
    return NextResponse.json(
      { status: 'running', message: 'O corte vertical já está sendo produzido.' },
      { status: 202 },
    );
  }

  const channels = body.channels ?? VERTICAL_CHANNELS;

  try {
    const pubsub = new PubSub({ projectId: GCP_PROJECT_ID });
    await pubsub.topic(VERTICAL_CUT_TOPIC).publishMessage({
      data: Buffer.from(JSON.stringify({
        project_id:   body.projectId,
        channels,
        requested_at: new Date().toISOString(),
      })),
    });

    await ref.update({
      'stages.vertical_cut.status':       'queued',
      'stages.vertical_cut.requested_at': new Date().toISOString(),
      'stages.vertical_cut.channels':     channels,
      updated_at: new Date().toISOString(),
    });

    return NextResponse.json({ status: 'queued', projectId: body.projectId, channels }, { status: 202 });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error('[derive-vertical] Falha ao enfileirar:', err);
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
