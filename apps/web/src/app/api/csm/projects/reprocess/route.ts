/**
 * POST /api/csm/projects/reprocess
 *
 * Retoma a produção de um projeto A PARTIR de um estágio, reaproveitando tudo
 * que já foi feito antes dele.
 *
 * Existe porque não havia caminho nenhum: os jobs são idempotentes por
 * estágio (`if status == "completed": return`), o que está certo — protege
 * contra reentrega do Pub/Sub — mas significava que um projeto travado só
 * saía do lugar reabrindo estágios À MÃO no Firestore. Foi o que aconteceu em
 * 27/08 para refazer um vídeo: três documentos editados na unha.
 *
 * A alternativa que a interface oferecia era aprovar o gate de novo, e isso
 * cria um `projectId` NOVO — refazendo o avatar do zero, a US$4/min. Um botão
 * "tentar de novo" ali seria um botão de gastar US$5.
 *
 * Aqui o `projectId` é o MESMO. Reprocessar da edição reusa os clipes de
 * avatar que já estão no GCS e não custa um centavo de HeyGen.
 */

import { NextResponse } from 'next/server';
import { PubSub } from '@google-cloud/pubsub';
import { getFirestoreDb } from '@/lib/firebase';
import { dbPaths } from '@/lib/dbPaths';
import { isCsmAuthenticated, csmUnauthorized } from '@/lib/csmAuth';
import { requireTenantId } from '@/lib/tenancy';

export const dynamic = 'force-dynamic';

const GCP_PROJECT_ID = process.env.FIREBASE_PROJECT_ID || 'vazfy-417019';

/** Ordem real da pipeline. Reabrir um estágio reabre todos os seguintes. */
const ETAPAS = ['tts', 'avatar', 'editor', 'publisher'] as const;
type Etapa = (typeof ETAPAS)[number];

/**
 * Estágios que gastam dinheiro em API externa.
 *
 * `editor` e `publisher` rodam sobre material já produzido — FFmpeg,
 * Playwright e upload. Reprocessar por ali é de graça, e é o caso comum:
 * vídeo montado errado, capa ruim, descrição incompleta.
 */
const CUSTA_DINHEIRO: Record<Etapa, string | null> = {
  tts:       'ElevenLabs (centavos) e, em cascata, o avatar no HeyGen (~US$4/min)',
  avatar:    'HeyGen, ~US$4 por minuto de avatar gerado',
  editor:    null,
  publisher: null,
};

const TOPICO: Record<Etapa, string> = {
  tts:       'content-pipeline.package-approved',
  avatar:    'content-pipeline.tts-completed',
  editor:    'content-pipeline.avatar-completed',
  publisher: 'content-pipeline.video-ready',
};

export async function POST(request: Request): Promise<Response> {
  if (!isCsmAuthenticated(request)) return csmUnauthorized();

  const tenant = await requireTenantId(request);
  if ('response' in tenant) return tenant.response;

  let body: { projectId?: string; apartirDe?: Etapa; confirmarCusto?: boolean };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'JSON inválido' }, { status: 400 });
  }

  const { projectId, apartirDe, confirmarCusto } = body;
  if (!projectId || !apartirDe || !ETAPAS.includes(apartirDe)) {
    return NextResponse.json(
      { error: `projectId e apartirDe (${ETAPAS.join(', ')}) são obrigatórios` },
      { status: 400 },
    );
  }

  const custo = CUSTA_DINHEIRO[apartirDe];
  if (custo && !confirmarCusto) {
    // Não é um aviso decorativo: sem esta trava, um clique repetido numa tela
    // que parece travada refaz o avatar inteiro.
    return NextResponse.json(
      { error: `Reprocessar a partir de "${apartirDe}" gasta ${custo}.`, exigeConfirmacao: true, custo },
      { status: 409 },
    );
  }

  const db = getFirestoreDb();
  if (!db) return NextResponse.json({ error: 'Firestore indisponível' }, { status: 503 });

  try {
    const ref = db.collection(dbPaths.contentProjects(tenant.tenantId)).doc(projectId);
    const snap = await ref.get();
    if (!snap.exists) {
      return NextResponse.json({ error: 'Projeto não encontrado' }, { status: 404 });
    }
    const proj = snap.data() as Record<string, any>;
    const stages = (proj.stages ?? {}) as Record<string, { status?: string }>;

    // Os estágios ANTERIORES precisam ter terminado: reprocessar a edição de
    // um projeto cujo avatar nunca voltou produziria um vídeo sem o
    // apresentador, em silêncio.
    const idx = ETAPAS.indexOf(apartirDe);
    const faltando = ETAPAS.slice(0, idx).filter((e) => stages[e]?.status !== 'completed');
    if (faltando.length) {
      return NextResponse.json(
        { error: `Faltam etapas anteriores concluídas: ${faltando.join(', ')}` },
        { status: 409 },
      );
    }

    const mensagem = await montarMensagem(apartirDe, projectId, proj);
    if (!mensagem) {
      return NextResponse.json(
        { error: `Não há material gravado para retomar de "${apartirDe}"` },
        { status: 409 },
      );
    }

    // Reabre o alvo e TUDO que vem depois. Reabrir só o alvo deixaria o
    // estágio seguinte marcado como concluído, e o job ignoraria a mensagem
    // — o projeto pareceria reprocessado sem ter sido.
    const patch: Record<string, unknown> = {};
    for (const e of ETAPAS.slice(idx)) {
      if (stages[e]) patch[`stages.${e}.status`] = 'pending';
    }
    // O registro do que já foi publicado NÃO é limpo ao retomar da publicação:
    // o publisher agora ATUALIZA o vídeo no lugar quando já existe um id.
    // Limpá-lo faria um upload novo, e o YouTube ficaria com dois vídeos do
    // mesmo tema — aconteceu em 27/08, e sobraram três.
    //
    // Retomar da EDIÇÃO é outro caso: ela refaz o arquivo, e arquivo novo
    // exige upload novo, porque o YouTube não permite trocar o vídeo de um id
    // existente.
    if (apartirDe !== 'publisher') patch['stages.publisher.platforms'] = {};
    await ref.update(patch);

    await new PubSub({ projectId: GCP_PROJECT_ID })
      .topic(TOPICO[apartirDe])
      .publishMessage({ data: Buffer.from(JSON.stringify(mensagem)) });

    return NextResponse.json({
      ok: true,
      projectId,
      apartirDe,
      reabertos: Object.keys(patch),
      topico: TOPICO[apartirDe],
    });
  } catch (err) {
    console.error('[csm/projects/reprocess] falhou:', err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : String(err) }, { status: 500 },
    );
  }
}

/** Remonta a mensagem que dispara o estágio, a partir do que já está gravado. */
async function montarMensagem(
  etapa: Etapa, projectId: string, proj: Record<string, any>,
): Promise<Record<string, unknown> | null> {
  const bucket = `${GCP_PROJECT_ID}-pipeline-media`;
  const base = `gs://${bucket}/projects/${projectId}`;

  if (etapa === 'tts' || etapa === 'avatar') {
    const manifest = proj.manifest_url || `${base}/manifest.html`;
    if (etapa === 'tts') {
      return {
        project_id: projectId,
        manifest_gcs_path: manifest,
        channels_approved: proj.channels_approved ?? ['youtube'],
        approved_at: new Date().toISOString(),
        cost_limit: 100.0,
      };
    }
    // O avatar é disparado por `tts-completed`, que carrega os áudios.
    const caminhos = proj.stages?.avatar?.slide_audio_paths ?? {};
    return {
      project_id: projectId,
      audio_paths: caminhos,
      heygen_segment_ids: { horizontal: [], vertical: [] },
      slide_audio_segment_ids: proj.stages?.avatar?.slide_audio_segment_ids ?? {},
      heygen_duration_s: 0,
    };
  }

  if (etapa === 'editor') {
    // Os clipes de avatar já estão no GCS: é isto que torna o reprocesso da
    // edição gratuito.
    const segs = (proj.stages?.avatar?.segment_videos?.horizontal ?? []) as
      { seg_id?: string; video_url?: string; status?: string }[];
    const ok = segs.filter((s) => s.status === 'completed' && s.video_url);
    if (!ok.length) return null;
    return {
      project_id: projectId,
      horizontal_video_paths: ok.map((s) => s.video_url),
      vertical_video_paths: [],
      segment_ids: ok.map((s) => s.seg_id),
      vertical_segment_ids: [],
      duration_seconds: 0,
      total_cost_usd: 0,
    };
  }

  // publisher
  return {
    project_id: projectId,
    horizontal_final: `${base}/final_horizontal.mp4`,
    vertical_final: '',
    duration_seconds: 0,
    trigger: 'immediate',
  };
}
