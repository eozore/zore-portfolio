/**
 * /api/csm/studio — ponte entre o navegador e o grafo do time de marketing.
 *
 * O cmo-agent não é chamável do browser (roda em outro serviço, com segredo
 * interno). Esta rota é o único caminho: valida a sessão do CSM, resolve o
 * tenant e repassa para /graph/*.
 *
 *   GET  ?sessionId=…            → estado atual do fluxo
 *   POST { action: 'start' }     → inicia com um tema
 *   POST { action: 'approve' }   → decide um gate e retoma o grafo
 *   POST { action: 'agendar' }   → manda o plano social para a fila
 */

import { NextResponse } from 'next/server';
import { isCsmAuthenticated, csmUnauthorized } from '@/lib/csmAuth';
import { cmoAgentHeaders } from '@/lib/cmoAgent';
import { requireTenantId } from '@/lib/tenancy';
import { createArticle, slugExists, slugify } from '@/lib/articles';
import type { ArticleCategory, CreateArticlePayload } from '@/types/article';
import type { Locale } from '@/types/i18n';
import { executarSubmit } from '@/lib/pipelineSubmit';

const CMO_AGENT_URL = process.env.CMO_AGENT_URL || 'http://localhost:8090';
const BLOG_BASE_URL = (process.env.NEXT_PUBLIC_BASE_URL || 'https://eozore.com').replace(/\/$/, '');

/** Enquanto não houver geração de capa, todo artigo do Studio nasce com esta. */
const CAPA_PADRAO = 'https://storage.googleapis.com/eozore-assets/covers/default.jpg';

const CATEGORIAS: ArticleCategory[] = ['estatistica', 'ml', 'ia'];

// O nó do artigo escreve o texto inteiro e pode levar minutos.
export const maxDuration = 300;

async function proxy(
  path: string,
  init: RequestInit,
  tenantId: string | null,
): Promise<Response> {
  try {
    const res = await fetch(`${CMO_AGENT_URL}${path}`, {
      ...init,
      headers: cmoAgentHeaders(tenantId),
      signal: AbortSignal.timeout(290_000),
    });
    const body = await res.json().catch(() => ({ detail: 'resposta inválida do agente' }));
    return NextResponse.json(body, { status: res.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    // Timeout aqui não significa que o trabalho morreu: o grafo persiste em
    // checkpoint, então a UI deve reconsultar o estado em vez de recomeçar.
    return NextResponse.json(
      { detail: `Agente indisponível: ${msg}`, retryable: true },
      { status: 504 },
    );
  }
}

/** Lê o estado do grafo. Usado pelas ações que precisam do conteúdo já pronto. */
async function lerEstado(sessionId: string, tenantId: string | null): Promise<any> {
  const res = await fetch(
    `${CMO_AGENT_URL}/graph/state?sessionId=${encodeURIComponent(sessionId)}`,
    { headers: cmoAgentHeaders(tenantId), signal: AbortSignal.timeout(30_000) },
  );
  if (!res.ok) throw new Error(`estado do grafo: HTTP ${res.status}`);
  return res.json();
}

/**
 * Grava o artigo no blog e devolve a URL pública.
 *
 * Nasce como RASCUNHO: o documento existe — e por isso a URL é real, que é o
 * que as peças sociais precisam para resolver `[LINK_ARTIGO]` — mas
 * `getAllArticles` filtra por status='published', então nada aparece no blog
 * até você promover. Mesma lógica do vídeo, que sobe como privado no YouTube.
 *
 * Roda ANTES de aprovar o gate, e uma falha aqui aborta a aprovação. É o
 * oposto do que o gate do vídeo faz, de propósito: produzir vídeo é caro e
 * pode ser retomado depois, enquanto aprovar o artigo sem gravá-lo faria o nó
 * social montar a semana inteira apontando para uma URL que não existe.
 */
async function publicarArtigo(
  sessionId: string,
  tenantId: string | null,
): Promise<{ url: string; slug: string; id: string }> {
  const estado = await lerEstado(sessionId, tenantId);

  // Idempotência: `graph_approve` persiste `artigo_url` ANTES de retomar o
  // grafo, então uma retomada que falhou já deixou a URL no estado. Sem esta
  // guarda, reaprovar gravaria um segundo rascunho com slug '-2'.
  const jaPublicado = String(estado?.artigo?.url || '');
  if (jaPublicado) {
    return {
      url:  jaPublicado,
      slug: String(estado?.artigo?.slug || ''),
      id:   '',
    };
  }

  const titulo   = String(estado?.artigo?.titulo || '').trim();
  const markdown = String(estado?.artigo?.markdown || '');
  if (!titulo || markdown.length < 500) {
    throw new Error('o grafo não tem artigo para publicar');
  }

  const idioma = (estado?.idioma === 'en' ? 'en' : 'pt-BR') as Locale;
  const categoriaBruta = String(estado?.pauta?.categoria || '');
  // A pauta declara a categoria; se o modelo devolver algo fora da lista, o
  // artigo não pode travar aqui — 'ia' é o bloco mais abrangente dos três.
  const categoria: ArticleCategory =
    (CATEGORIAS as string[]).includes(categoriaBruta)
      ? (categoriaBruta as ArticleCategory)
      : 'ia';

  const base = slugify(String(estado?.artigo?.slug || '') || titulo);
  if (!base) throw new Error('não foi possível derivar um slug do título');

  // Slug tomado é conflito real: o blog resolve o post por slug + idioma.
  let slug = base;
  for (let n = 2; n <= 20 && (await slugExists(slug, idioma, tenantId)); n++) {
    const sufixo = `-${n}`;
    slug = `${base.slice(0, 100 - sufixo.length)}${sufixo}`;
  }
  if (await slugExists(slug, idioma, tenantId)) {
    throw new Error(`slug '${base}' e as 19 variações seguintes já existem`);
  }

  const palavras = markdown.split(/\s+/).filter(Boolean).length;
  const payload: CreateArticlePayload = {
    title:       titulo.slice(0, 150),
    slug,
    content:     markdown,
    category:    categoria,
    language:    idioma,
    publishedAt: new Date().toISOString(),
    readTime:    Math.min(120, Math.max(1, Math.round(palavras / 220))),
    coverImage:  CAPA_PADRAO,
  };

  const id = await createArticle(payload, tenantId, 'draft');
  if (!id) throw new Error('Firestore recusou a escrita do artigo');

  return { url: `${BLOG_BASE_URL}/${idioma}/blog/${slug}`, slug, id };
}

/**
 * Dispara a produção do vídeo a partir do estado do grafo.
 *
 * Chama `executarSubmit` EM PROCESSO. Antes isto era um self-fetch para
 * `/api/csm/pipeline-submit` usando `new URL(request.url).origin` como base:
 * dentro do Cloud Run essa origem é o localhost do container, a chamada não
 * passa pelo balanceador e não aparece em log nenhum. Em 24/08 o gate do vídeo
 * foi aprovado, nenhum `content_project` nasceu, `video_project_id` ficou nulo
 * — e a tela mostrou, como se fosse desta semana, o progresso de um projeto de
 * 16/08 que casava pelo mesmo `session_id`.
 *
 * Lança em caso de falha. Quem chama decide — e agora o gate NÃO avança sem
 * produção, porque aprovar o vídeo é exatamente o ato de produzi-lo.
 */
async function dispararProducao(
  sessionId: string,
  tenantId: string | null,
): Promise<{ projectId: string }> {
  const estado = await lerEstado(sessionId, tenantId);

  const manifesto = estado?.video?.manifesto;
  if (!manifesto?.youtube?.segments?.length) {
    throw new Error('o grafo não tem manifesto para produzir');
  }

  // Os HTMLs vêm de um endpoint separado: são ~85KB e o /graph/state os omite.
  // Sem eles o deck sai com placeholders — telas pretas escritas "// yt-02" no
  // lugar das ilustrações. Por isso a ausência é ERRO, não um seguir adiante.
  const r = await fetch(
    `${CMO_AGENT_URL}/graph/slides?sessionId=${encodeURIComponent(sessionId)}`,
    { headers: cmoAgentHeaders(tenantId), signal: AbortSignal.timeout(60_000) },
  );
  if (!r.ok) throw new Error(`não consegui buscar os slides: HTTP ${r.status}`);
  const slides: Record<string, string> = (await r.json()).slides ?? {};
  if (!Object.keys(slides).length) {
    throw new Error('nenhum slide desenhado — o vídeo sairia com telas pretas');
  }

  const resultado = await executarSubmit(
    {
      articleSlug:  estado?.artigo?.slug || sessionId,
      articleTitle: estado?.video?.titulo || estado?.artigo?.titulo || 'Vídeo éozoré',
      sessionId,
      items: [],
      manifestV2: manifesto,
      slideHtmls: slides,
      // Sem a pauta a descrição do YouTube sai VAZIA: quem a monta procura
      // por uma sessão do CSM antigo, que num fluxo do grafo não existe. O
      // vídeo de 27/08 subiu com duas linhas e nenhum capítulo por causa
      // disto.
      pauta: estado?.pauta,
    },
    tenantId,
  );

  if (!resultado.mainProjectId) {
    throw new Error(resultado.errors.join(' · ') || 'a pipeline não foi disparada');
  }
  return { projectId: resultado.mainProjectId };
}


export async function GET(request: Request): Promise<Response> {
  if (!isCsmAuthenticated(request)) return csmUnauthorized();

  const tenant = await requireTenantId(request);
  if ('response' in tenant) return tenant.response;

  const sessionId = new URL(request.url).searchParams.get('sessionId');
  if (!sessionId) {
    return NextResponse.json({ error: 'sessionId obrigatório' }, { status: 400 });
  }
  return proxy(
    `/graph/state?sessionId=${encodeURIComponent(sessionId)}`,
    { method: 'GET' },
    tenant.tenantId,
  );
}

export async function POST(request: Request): Promise<Response> {
  if (!isCsmAuthenticated(request)) return csmUnauthorized();

  const tenant = await requireTenantId(request);
  if ('response' in tenant) return tenant.response;

  let body: Record<string, unknown>;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'JSON inválido' }, { status: 400 });
  }

  const { action, ...rest } = body;
  if (action === 'start') {
    return proxy('/graph/start', { method: 'POST', body: JSON.stringify(rest) }, tenant.tenantId);
  }
  if (action === 'approve') {
    // Aprovar o ARTIGO é o que o grava no blog. Acontece antes da retomada do
    // grafo para que a URL entre no estado junto com a aprovação — o nó social
    // roda logo depois e monta as peças com o link já resolvido.
    let artigoUrl: string | undefined;
    let publicacao: { ok: boolean; url?: string; slug?: string; erro?: string } | undefined;
    if (rest.gate === 'artigo' && rest.decisao === 'aprovado') {
      try {
        const pub = await publicarArtigo(String(rest.sessionId), tenant.tenantId);
        artigoUrl  = pub.url;
        publicacao = { ok: true, url: pub.url, slug: pub.slug };
      } catch (err) {
        // Gate NÃO avança: reaprovar depois de corrigir custa um clique,
        // enquanto seguir sem artigo gravado produz uma semana de posts
        // apontando para o vazio.
        return NextResponse.json(
          {
            detail: `Não consegui gravar o artigo no blog: ${
              err instanceof Error ? err.message : String(err)
            }`,
            publicacao: { ok: false, erro: err instanceof Error ? err.message : String(err) },
          },
          { status: 502 },
        );
      }
    }

    // Aprovar o VÍDEO é o ato de produzi-lo. Roda ANTES da retomada, pelo
    // mesmo motivo do artigo: assim o `videoProjectId` entra no estado junto
    // com a aprovação, e a tela passa a acompanhar ESTE projeto em vez de
    // procurar por `session_id` — que em 24/08 casou com um projeto de outra
    // semana e exibiu o vídeo errado como se fosse o novo.
    //
    // Falhar aqui ABORTA a aprovação, de propósito. A versão anterior seguia
    // adiante devolvendo `{ok:false, erro}`, a interface descartava o campo, e
    // o resultado era um pacote "concluído" sem vídeo nenhum.
    let videoProjectId: string | undefined;
    if (rest.gate === 'video' && rest.decisao === 'aprovado') {
      try {
        videoProjectId = (await dispararProducao(
          String(rest.sessionId), tenant.tenantId,
        )).projectId;
      } catch (err) {
        const motivo = err instanceof Error ? err.message : String(err);
        return NextResponse.json(
          {
            detail: `Não consegui iniciar a produção do vídeo: ${motivo}`,
            producao: { ok: false, erro: motivo },
          },
          { status: 502 },
        );
      }
    }

    const res  = await proxy(
      '/graph/approve',
      {
        method: 'POST',
        body: JSON.stringify({
          ...rest,
          ...(artigoUrl ? { artigoUrl } : {}),
          ...(videoProjectId ? { videoProjectId } : {}),
        }),
      },
      tenant.tenantId,
    );
    const data = await res.clone().json().catch(() => ({}));
    if (publicacao || videoProjectId) {
      return NextResponse.json(
        {
          ...data,
          ...(publicacao ? { publicacao } : {}),
          ...(videoProjectId ? { producao: { ok: true, projectId: videoProjectId } } : {}),
        },
        { status: res.status },
      );
    }
    return res;
  }
  if (action === 'agendar') {
    // Renderiza as imagens de carrossel e stories antes de gravar, então
    // demora mais que uma chamada de leitura — daí o proxy com o timeout
    // longo em vez de um fetch direto.
    return proxy(
      '/graph/social/enqueue',
      { method: 'POST', body: JSON.stringify({ sessionId: rest.sessionId }) },
      tenant.tenantId,
    );
  }
  return NextResponse.json(
    { error: "action deve ser 'start', 'approve' ou 'agendar'" },
    { status: 400 },
  );
}
