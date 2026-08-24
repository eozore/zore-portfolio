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
 * Falha aqui NÃO derruba a aprovação: o grafo já avançou para o plano social,
 * e o conteúdo aprovado continua válido. O erro volta no campo `producao`
 * para a tela mostrar — perder a aprovação por causa de uma falha de
 * infraestrutura seria pior que produzir o vídeo mais tarde.
 */
async function dispararProducao(
  request: Request,
  sessionId: string,
  tenantId: string | null,
): Promise<{ ok: boolean; projectId?: string; erro?: string }> {
  try {
    const estado = await lerEstado(sessionId, tenantId);

    const manifesto = estado?.video?.manifesto;
    if (!manifesto?.youtube?.segments?.length) {
      return { ok: false, erro: 'o grafo não tem manifesto para produzir' };
    }

    // Os HTMLs vêm de um endpoint separado: são ~85KB e o /graph/state os
    // omite. Sem eles o deck sai com placeholders — telas pretas escritas
    // "// yt-02" no lugar das ilustrações.
    let slides: Record<string, string> = {};
    try {
      const r = await fetch(
        `${CMO_AGENT_URL}/graph/slides?sessionId=${encodeURIComponent(sessionId)}`,
        { headers: cmoAgentHeaders(tenantId), signal: AbortSignal.timeout(60_000) },
      );
      if (r.ok) slides = (await r.json()).slides ?? {};
    } catch {
      // Sem slides o gate do /build-manifest recusa e nomeia os que faltam.
    }

    const base = new URL(request.url).origin;
    const submitRes = await fetch(`${base}/api/csm/pipeline-submit`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        cookie: request.headers.get('cookie') ?? '',
        ...(tenantId ? { 'x-tenant-id': tenantId } : {}),
      },
      body: JSON.stringify({
        articleSlug:  estado?.artigo?.slug || sessionId,
        articleTitle: estado?.video?.titulo || estado?.artigo?.titulo || 'Vídeo éozoré',
        sessionId,
        items: [],
        manifestV2: manifesto,
        slideHtmls: slides,
      }),
      signal: AbortSignal.timeout(120_000),
    });
    const submit = await submitRes.json().catch(() => ({}));
    if (submit.mainProjectId) return { ok: true, projectId: submit.mainProjectId };
    return { ok: false, erro: (submit.errors ?? []).join(' · ') || 'pipeline não disparou' };
  } catch (err) {
    return { ok: false, erro: err instanceof Error ? err.message : String(err) };
  }
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

    const res  = await proxy(
      '/graph/approve',
      { method: 'POST', body: JSON.stringify({ ...rest, ...(artigoUrl ? { artigoUrl } : {}) }) },
      tenant.tenantId,
    );
    const data = await res.clone().json().catch(() => ({}));
    if (publicacao) {
      return NextResponse.json({ ...data, publicacao }, { status: res.status });
    }

    // Aprovar o vídeo é o que DISPARA a produção. Até aqui o gate só
    // destravava o nó seguinte do grafo — o roteiro era aprovado e nenhum
    // vídeo era feito.
    //
    // Reusa o pipeline-submit em vez de republicar a lógica: ele já sobe o
    // manifesto ao GCS, roda o gate do produto, cria o content_project e
    // publica no Pub/Sub. E como ele grava `session_id` no projeto, o
    // /api/csm/pipeline-status encontra o progresso pela mesma sessão.
    if (res.ok && rest.gate === 'video' && rest.decisao === 'aprovado') {
      const disparo = await dispararProducao(
        request, String(rest.sessionId), tenant.tenantId,
      );
      return NextResponse.json({ ...data, producao: disparo }, { status: res.status });
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
