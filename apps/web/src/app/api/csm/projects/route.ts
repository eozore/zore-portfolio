/**
 * GET /api/csm/projects
 *
 * A biblioteca do Studio: um item por ciclo, com o estado de CADA entregável.
 *
 * Existe porque o Studio foi desenhado como um fluxo por vez. O id da sessão
 * vivia no `localStorage` e "Começar outro tema" o sobrescrevia — o ciclo
 * anterior continuava inteiro no Firestore e ficava inalcançável. E como a
 * produção é assíncrona (o vídeo leva de 20 a 40 minutos, o artigo já está no
 * ar, a semana já está agendada), não havia tela que respondesse "o que está
 * acontecendo agora, em tudo?".
 *
 * Os quatro entregáveis são independentes e cada um tem estado próprio. Não é
 * uma barra de progresso: é uma matriz.
 */

import { NextResponse } from 'next/server';
import { getFirestoreDb } from '@/lib/firebase';
import { dbPaths } from '@/lib/dbPaths';
import { isCsmAuthenticated, csmUnauthorized } from '@/lib/csmAuth';
import { requireTenantId } from '@/lib/tenancy';

export const dynamic = 'force-dynamic';

/** Estado de um entregável. `na` = o ciclo ainda não chegou nele. */
export type EstadoEntregavel = 'na' | 'pendente' | 'produzindo' | 'pronto' | 'erro';

export interface ProjetoResumo {
  sessionId:  string;
  tema:       string;
  criadoEm:   string;
  atualizadoEm: string;
  fase:       string;
  projectId:  string | null;
  artigo:   { estado: EstadoEntregavel; status?: string; slug?: string; url?: string };
  video:    { estado: EstadoEntregavel; etapa?: string; youtubeUrl?: string; erro?: string };
  social:   { estado: EstadoEntregavel; agendadas: number; publicadas: number; falhas: number };
  vertical: { estado: EstadoEntregavel };
}

/** Ordem em que os estágios da pipeline acontecem, para achar onde parou. */
const ORDEM_ETAPAS = ['tts', 'avatar', 'editor', 'publisher'] as const;
const ROTULO_ETAPA: Record<string, string> = {
  tts: 'Voz', avatar: 'Avatar', editor: 'Edição', publisher: 'Publicação',
};

function estadoDoVideo(stages: Record<string, { status?: string; error_message?: string }>):
  { estado: EstadoEntregavel; etapa?: string; erro?: string } {
  if (!stages || !Object.keys(stages).length) return { estado: 'na' };

  for (const nome of ORDEM_ETAPAS) {
    const st = stages[nome]?.status;
    if (st === 'error') {
      return { estado: 'erro', etapa: ROTULO_ETAPA[nome], erro: stages[nome]?.error_message };
    }
    // `pending_callback` é o HeyGen renderizando: trabalho em curso, não parada.
    if (st && st !== 'completed') {
      return { estado: 'produzindo', etapa: ROTULO_ETAPA[nome] };
    }
    if (!st) return { estado: 'pendente', etapa: ROTULO_ETAPA[nome] };
  }
  return { estado: 'pronto' };
}

export async function GET(request: Request): Promise<Response> {
  if (!isCsmAuthenticated(request)) return csmUnauthorized();

  const tenant = await requireTenantId(request);
  if ('response' in tenant) return tenant.response;
  const tenantId = tenant.tenantId;

  const db = getFirestoreDb();
  if (!db) return NextResponse.json({ projetos: [] });

  const limite = Number(new URL(request.url).searchParams.get('limite') ?? 30);

  try {
    // As quatro fontes são lidas em paralelo e juntadas em memória. Uma query
    // por projeto tornaria a home O(n) em ida e volta ao Firestore.
    const [sessoesSnap, projetosSnap, artigosSnap, filaSnap] = await Promise.all([
      db.collection(dbPaths.studioSessions(tenantId))
        .orderBy('atualizado_em', 'desc').limit(limite).get(),
      db.collection(dbPaths.contentProjects(tenantId)).limit(200).get(),
      db.collection(dbPaths.articles(tenantId)).limit(200).get(),
      db.collection(dbPaths.socialQueue(tenantId)).limit(500).get(),
    ]);

    const projetosPorSessao = new Map<string, FirebaseFirestore.DocumentData>();
    for (const d of projetosSnap.docs) {
      const dados = d.data();
      const sid = dados.session_id;
      if (!sid) continue;
      // Mais recente vence: reaprovar cria um projectId novo para a mesma
      // sessão, e o que interessa na lista é a produção corrente.
      const atual = projetosPorSessao.get(sid);
      if (!atual || String(dados.created_at ?? '') > String(atual.created_at ?? '')) {
        projetosPorSessao.set(sid, { ...dados, __id: d.id });
      }
    }

    const artigoPorSlug = new Map<string, FirebaseFirestore.DocumentData>();
    for (const d of artigosSnap.docs) {
      const dados = d.data();
      if (dados.slug) artigoPorSlug.set(dados.slug, dados);
    }

    const filaPorSessao = new Map<string, { agendadas: number; publicadas: number; falhas: number }>();
    for (const d of filaSnap.docs) {
      const dados = d.data();
      const sid = dados.session_id;
      if (!sid) continue;
      const acc = filaPorSessao.get(sid) ?? { agendadas: 0, publicadas: 0, falhas: 0 };
      if (dados.status === 'published') acc.publicadas += 1;
      else if (dados.status === 'failed') acc.falhas += 1;
      else acc.agendadas += 1;
      filaPorSessao.set(sid, acc);
    }

    const projetos: ProjetoResumo[] = sessoesSnap.docs.map((doc) => {
      const s = doc.data();
      const sessionId = doc.id;
      const proj = projetosPorSessao.get(sessionId);
      const artigo = s.artigo_slug ? artigoPorSlug.get(s.artigo_slug) : undefined;
      const fila = filaPorSessao.get(sessionId);

      const vid = estadoDoVideo((proj?.stages ?? {}) as Record<string, { status?: string }>);
      const youtubeUrl = proj?.stages?.publisher?.platforms?.youtube
        ? `https://youtu.be/${proj.stages.publisher.platforms.youtube}`
        : undefined;

      return {
        sessionId,
        tema:         s.tema ?? '(sem tema)',
        criadoEm:     s.criado_em ?? s.atualizado_em ?? '',
        atualizadoEm: s.atualizado_em ?? '',
        fase:         s.fase ?? '',
        projectId:    (proj?.__id as string) ?? s.video_project_id ?? null,
        artigo: artigo
          ? { estado: artigo.status === 'published' ? 'pronto' : 'pendente',
              status: artigo.status, slug: s.artigo_slug, url: s.artigo_url }
          : { estado: 'na' },
        video: { ...vid, youtubeUrl },
        social: fila
          ? { estado: fila.publicadas > 0 ? 'pronto' : 'pendente', ...fila }
          : { estado: 'na', agendadas: 0, publicadas: 0, falhas: 0 },
        vertical: {
          estado: proj?.stages?.vertical_cut?.status === 'completed' ? 'pronto'
                : proj?.stages?.vertical_cut?.status ? 'produzindo' : 'na',
        },
      };
    });

    return NextResponse.json({ projetos });
  } catch (err) {
    console.error('[csm/projects] falhou:', err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : String(err) }, { status: 500 },
    );
  }
}
