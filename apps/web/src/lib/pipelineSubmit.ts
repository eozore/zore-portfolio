/**
 * lib/pipelineSubmit.ts — o submit da produção, sem HTTP.
 *
 * Vive aqui e não no arquivo de rota porque tem DOIS chamadores: a rota
 * `/api/csm/pipeline-submit` e o gate do vídeo em `/api/csm/studio`. O Next.js
 * também recusa exports que não sejam handlers num arquivo de rota.
 *
 * Fluxo original
 *
 * Ponto de entrada central da aprovação de conteúdo.
 *
 * Fluxo completo:
 *
 * 1. YouTube longo (youtubeScript aprovado):
 *    a. Chama cmo_agent /build-manifest → gera manifesto HTML no GCS
 *    b. Cria documento content_projects/{project_id} no Firestore
 *    c. Publica PackageApprovedMsg no Pub/Sub → dispara TTS → Avatar → VideoEditor
 *
 * 2. Itens de texto aprovados (LinkedIn, Threads, Facebook):
 *    Salva em social_queue para publicação posterior pelo scheduler
 *
 * 3. Vídeos curtos aprovados (Shorts, Reels):
 *    Mesmo fluxo do YouTube longo com orientação vertical
 */

import { getFirestoreDb } from './firebase';
import { PubSub } from '@google-cloud/pubsub';
import { GoogleAuth } from 'google-auth-library';
import { dbPaths } from './dbPaths';
import { cmoAgentHeaders } from './cmoAgent';
import { loadSession } from './session';

const GCP_PROJECT_ID      = process.env.FIREBASE_PROJECT_ID || 'vazfy-417019';
const PIPELINE_TOPIC      = 'content-pipeline.package-approved';
const CMO_AGENT_URL       = process.env.CMO_AGENT_URL || 'http://localhost:8090';
const PUBLISHER_URL       = 'https://publisher-immediate-4zffe4l4lq-uc.a.run.app';
const DEFAULT_COST_LIMIT  = 50.0;   // USD — gate de custo por vídeo
const BLOG_BASE_URL       = (process.env.NEXT_PUBLIC_BASE_URL || 'https://eozore.com').replace(/\/$/, '');

// Plataformas de texto — publicação imediata
const TEXT_PLATFORMS = new Set(['linkedin', 'facebook', 'threads', 'youtube_community']);
// Formatos de vídeo — disparam pipeline
const VIDEO_FORMATS  = new Set(['shorts', 'reel', 'video']);

export interface SubmitItem {
  id: string;
  platform: string;
  format: string;
  title: string;
  copy: string;
  scheduledAt: string;
  status: 'aprovado' | 'em_revisao' | 'rejeitado';
  script?: string;
  threadPosts?: string[];
  slides?: { slideNumber: number; heading: string; body: string }[];
  videoUrl?: string;
  imageUrl?: string;
  /** Carrossel: 2+ imagens já renderizadas e no GCS. */
  imageUrls?: string[];
  imageDescription?: string;
}

export interface SubmitRequest {
  articleSlug:   string;
  articleTitle:  string;
  youtubeScript?: string;   // Roteiro achatado — só usado para detectar intenção
  sessionId?:    string;
  items:         SubmitItem[];
  /** Manifesto vindo do grafo do Studio, que o guarda no próprio checkpoint
   *  em vez de no draft da sessão. Tem precedência sobre draft.manifestV2. */
  manifestV2?:   ManifestV2;
  slideHtmls?:   Record<string, string>;
  /** Pauta do grafo. O Studio precisa mandá-la: `loadSession` procura uma
   *  sessão do CSM antigo, que num fluxo nascido no grafo não existe, e a
   *  descrição do YouTube saía VAZIA — o vídeo de 27/08 subiu com duas
   *  linhas (link do artigo e "assine o canal") e nenhum capítulo. */
  pauta?:        Record<string, unknown>;
}

/** Manifesto v2 aprovado — o contrato que vira vídeo, sem reinterpretação. */
export interface ManifestV2 {
  youtube?: { segments?: { id: string; kind?: string; slide?: string | null }[] };
  vertical_cut?: { title?: string; segments?: { id: string; source: string }[] };
  [key: string]: unknown;
}

/** Resposta do /build-manifest, incluindo o gate do produto. */
interface ManifestBuildResult {
  manifest_gcs_path:   string;
  thumb_frase?:        string | null;
  thumb_apoio?:        string | null;
  youtube_copy?:       YoutubeCopy | null;
  segment_count:       number;
  avatar_segments:     number;
  slide_segments:      number;
  avatar_share?:       number;
  total_duration_s?:   number;
  vertical_cut_count?: number;
  /** Gancho próprio do curto — o `vertical_cut.title` do manifesto. */
  vertical_cut_title?: string | null;
  estimated_cost_usd?: number;
  violations?:         string[];
}

// ── Helper: obtém token OIDC para chamadas internas ao Cloud Run ──────────────

async function getCloudRunToken(audience: string): Promise<string | null> {
  try {
    const auth   = new GoogleAuth();
    const client = await auth.getIdTokenClient(audience);
    const headers = await client.getRequestHeaders();
    return headers.get('authorization')?.replace('Bearer ', '') ?? null;
  } catch {
    return null;
  }
}

// ── Helper: chama /publish-now no publisher-immediate ─────────────────────────

async function publishNow(
  platform:   string,
  format:     string,
  copy:       string,
  title:      string,
  item:       SubmitItem,
  token:      string | null,
): Promise<{ ok: boolean; post_id?: string; error?: string }> {
  const payload = {
    platform,
    format,
    copy,
    title,
    imageUrl:    item.imageUrl    || null,
    videoUrl:    item.videoUrl    || null,
    threadPosts: item.threadPosts || null,
    asset_urls:  item.imageUrl ? [item.imageUrl] : item.videoUrl ? [item.videoUrl] : [],
  };

  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  try {
    const res  = await fetch(`${PUBLISHER_URL}/publish-now`, {
      method: 'POST',
      headers,
      body:   JSON.stringify(payload),
      signal: AbortSignal.timeout(90_000),  // 90s — Threads série pode demorar
    });
    const data = await res.json();
    if (res.ok && data.post_id) return { ok: true, post_id: data.post_id };
    return { ok: false, error: data.detail || data.error || `HTTP ${res.status}` };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) };
  }
}

// ── Helper: cria documento do projeto no Firestore ────────────────────────────

/** Metadados editoriais que o publisher_job lê para montar a publicação. */
interface ProjectMeta {
  /** Canais que este projeto pode publicar. O publisher lê do doc do projeto,
   *  porque a lista se perde na cadeia Pub/Sub (tts → avatar → editor). */
  channelsApproved?: string[];
  description?: string;
  tags?:        string[];
  articleUrl?:  string;
  subtitle?:    string;
  category?:    string;
  /** Frase de capa da thumbnail. A capa NÃO usa o título: com os 63
   *  caracteres do vídeo de 27/08 ela saiu com sete linhas, ilegível em
   *  miniatura. Vem do /build-manifest e pode ser undefined — nesse caso o
   *  gerador cai no título, comportamento anterior. */
  thumbFrase?:  string;
  thumbApoio?:  string;
  /** Gancho PRÓPRIO do Short/Reel, do `vertical_cut.title` do manifesto. */
  shortFrase?:  string;
  /** Slug da série. Decide as hashtags fixas do curto no publisher. */
  serie?:       string;
}

/**
 * Monta a descrição do YouTube na estrutura que o canal já usa.
 *
 * O molde vem dos vídeos escritos à mão (BT71_36ScDc, 9QFbpcYsac8):
 * um parágrafo que nomeia o problema, um que diz a quem interessa, a lista
 * "Você vai aprender", os capítulos com timestamp, links e hashtags.
 *
 * Os capítulos NÃO entram aqui: eles dependem da duração real de cada
 * segmento, que só existe depois da edição. O publisher os insere no
 * marcador CAPITULOS quando lê o timeline.json.
 */
export const MARCADOR_CAPITULOS = '<!--CAPITULOS-->';

/** Parte escrita da descrição, vinda do /build-manifest. */
export interface YoutubeCopy {
  abertura:     string;
  contexto:     string;
  aprendizados: string[];
  hashtags:     string[];
}

function buildDescription(
  pauta: Record<string, unknown> | undefined,
  slideHtmls: Record<string, string> = {},
  copy?: YoutubeCopy | null,
): string {
  // Caminho preferido: os blocos escritos pelo modelo. O encadeamento abaixo
  // é o fallback — publica, mas produz frases quebradas quando a tese já é
  // uma oração completa ("Neste vídeo eu explico sem um harness…").
  if (copy?.abertura && copy?.contexto && copy.aprendizados?.length) {
    const blocos = [
      copy.abertura,
      copy.contexto,
      `Você vai aprender:\n\n${copy.aprendizados.map((a) => `✔ ${a};`).join('\n')}`,
      MARCADOR_CAPITULOS,
      '🔗 Meu portfólio: https://www.eozore.com\n' +
      '🔗 Redes sociais:\n' +
      'https://www.linkedin.com/in/victor-zor%C3%A9/\n' +
      'https://github.com/eozore\n' +
      'https://www.instagram.com/eozore.ai/',
    ];
    if (copy.hashtags?.length) {
      blocos.push(copy.hashtags.map((h) => `#${h.replace(/[^a-z0-9]/gi, '').toLowerCase()}`).join(' '));
    }
    return blocos.join('\n\n');
  }

  const p = pauta ?? {};
  const txt = (k: string): string =>
    typeof p[k] === 'string' ? (p[k] as string).trim() : '';

  const partes: string[] = [];

  const tese = txt('tese');
  const sub  = txt('subtitulo');
  if (tese) partes.push(`Neste vídeo eu explico ${primeiraMinuscula(tese)}`);
  else if (sub) partes.push(sub);

  const publico = txt('publico');
  const objetivo = txt('objetivo_aprendizado');
  if (publico && objetivo) {
    partes.push(`Se você é ${primeiraMinuscula(publico)}, o que está em jogo é ${primeiraMinuscula(objetivo)}`);
  } else if (objetivo) {
    partes.push(objetivo);
  }

  // Os títulos dos slides são o que o vídeo REALMENTE cobre — melhor fonte
  // para as promessas do que a lista de tecnologias da pauta.
  const topicos = titulosDosSlides(slideHtmls);
  if (topicos.length) {
    partes.push(`Você vai aprender:\n\n${topicos.map((t) => `✔ ${t};`).join('\n')}`);
  } else {
    const skills = Array.isArray(p.hardskills) ? (p.hardskills as string[]) : [];
    if (skills.length) {
      partes.push(`Você vai aprender:\n\n${skills.map((sk) => `✔ ${sk};`).join('\n')}`);
    }
  }

  partes.push(MARCADOR_CAPITULOS);

  partes.push(
    '🔗 Meu portfólio: https://www.eozore.com\n' +
    '🔗 Redes sociais:\n' +
    'https://www.linkedin.com/in/victor-zor%C3%A9/\n' +
    'https://github.com/eozore\n' +
    'https://www.instagram.com/eozore.ai/',
  );

  const tags = buildTags({ pauta: p }, txt('categoria') || 'ia');
  if (tags.length) {
    partes.push(tags.map((t) => `#${t.replace(/[^a-z0-9à-ú]/gi, '').toLowerCase()}`).join(' '));
  }

  return partes.filter(Boolean).join('\n\n');
}

/** "Pipelines de IA falham" → "pipelines de IA falham" (segue a frase iniciada). */
function primeiraMinuscula(s: string): string {
  if (!s) return s;
  // Só rebaixa se a segunda letra for minúscula: preserva siglas (IA, LLM).
  if (s.length > 1 && s[1] === s[1].toUpperCase() && s[1] !== s[1].toLowerCase()) return s;
  return s[0].toLowerCase() + s.slice(1);
}

/**
 * Título visível de cada slide, na ordem, extraído do HTML do designer.
 *
 * Os slides carregam o que o vídeo cobre de fato. A alternativa era a lista
 * `hardskills` da pauta, que traz nomes de tecnologia ("LangGraph",
 * "Firestore") em vez de promessas — e promessa é o que faz alguém assistir.
 */
export function titulosDosSlides(slideHtmls: Record<string, string>): string[] {
  const vistos = new Set<string>();
  const saida: string[] = [];
  for (const html of Object.values(slideHtmls ?? {})) {
    const m =
      html.match(/class="[^"]*\b(?:main-title|badge-label|card-tag|col-title|eyebrow)\b[^"]*"[^>]*>([^<]{4,90})</i) ??
      html.match(/<h[12][^>]*>([^<]{4,90})</i);
    const bruto = m?.[1]?.replace(/\s+/g, ' ').trim();
    if (!bruto) continue;
    const chave = bruto.toLowerCase();
    if (vistos.has(chave)) continue;
    vistos.add(chave);
    saida.push(bruto);
  }
  return saida.slice(0, 8);
}


/** Tags do YouTube derivadas da pauta, em vez das três genéricas do fallback. */
function buildTags(draft: Record<string, unknown> | undefined, category: string): string[] {
  const pauta = (draft?.pauta ?? {}) as Record<string, unknown>;
  const skills = Array.isArray(pauta.hardskills) ? (pauta.hardskills as string[]) : [];
  const fromSkills = skills
    .flatMap((s) => s.toLowerCase().split(/[\s,/]+/))
    .filter((w) => w.length >= 4 && !['para', 'como', 'onde', 'sobre', 'entre'].includes(w));
  const serie = typeof pauta.serie === 'string' ? pauta.serie.replace(/-/g, ' ') : '';
  // YouTube ignora tags além de ~500 chars no total; 15 é folgado e seguro.
  return [...new Set([category, ...(serie ? [serie] : []), ...fromSkills, 'eozore'])].slice(0, 15);
}

async function createProjectDoc(
  projectId:    string,
  title:        string,
  manifestPath: string,
  articleSlug:  string,
  sessionId:    string | undefined,
  tenantId:     string | null,
  meta:         ProjectMeta = {},
): Promise<void> {
  const db = getFirestoreDb();
  if (!db) return;

  const now = new Date().toISOString();
  await db.collection(dbPaths.contentProjects(tenantId)).doc(projectId).set({
    project_id:   projectId,
    title,
    manifest_url: manifestPath,
    article_slug: articleSlug,
    session_id:   sessionId || null,
    status:       'generating_media',
    created_at:   now,
    updated_at:   now,
    // Campos consumidos por publisher_job.publish_video_ready(). Sem eles o
    // vídeo subia sem descrição, com tags genéricas e link para o índice do
    // blog em vez do artigo.
    description:  meta.description ?? '',
    tags:         meta.tags ?? [],
    thumb_frase:  meta.thumbFrase ?? '',
    thumb_apoio:  meta.thumbApoio ?? '',
    // Sem estes dois o Short cai no título do vídeo LONGO e em três hashtags
    // genéricas — que foi como saíram os de 31/08.
    short_frase:  meta.shortFrase ?? '',
    serie:        meta.serie ?? '',
    article_url:  meta.articleUrl ?? '',
    subtitle:     meta.subtitle ?? '',
    category:     meta.category ?? 'ia',
    channels_approved: meta.channelsApproved ?? [],
    stages: {
      tts:    { status: 'pending' },
      avatar: { status: 'pending' },
      editor: { status: 'pending' },
    },
  });
}

// ── Handler principal ─────────────────────────────────────────────────────────

/** O que o submit devolve, para o chamador em processo e para a rota. */
export interface SubmitResults {
  totalApproved:          number;
  videoPipelineTriggered: number;
  textPublished:          number;
  errors:                 string[];
  publishedItems:         { platform: string; post_id: string }[];
  /** Projeto do vídeo longo. É dele que o pacote é derivado depois. */
  mainProjectId:          string;
  /** Itens de vídeo curto adiados até o vídeo do YouTube existir. */
  videoItemsDeferred:     number;
}

/** Erro de entrada do submit — vira HTTP 400 na rota, exceção no uso direto. */
export class SubmitInvalidoError extends Error {}

/**
 * Executa o submit. Separado do handler HTTP de propósito.
 *
 * O Studio precisa disparar a produção a partir de OUTRA rota do servidor. A
 * versão anterior fazia isso com um self-fetch HTTP: resolvia a própria origem
 * com `new URL(request.url).origin` e repassava o cookie. Dentro do Cloud Run
 * essa origem é o localhost do container — a chamada não passa pelo
 * balanceador, não aparece em log nenhum, e qualquer falha virava um objeto de
 * erro que a interface descartava. Resultado observado em 24/08: o gate do
 * vídeo foi aprovado, `video_project_id` ficou nulo, nenhum `content_project`
 * foi criado e a tela mostrou o progresso de um projeto de outra semana.
 *
 * Chamar isto direto elimina a origem, o cookie, a reautenticação e a
 * invisibilidade de uma vez.
 */
export async function executarSubmit(
  body: SubmitRequest,
  tenantId: string | null,
): Promise<SubmitResults> {
  const { articleSlug, articleTitle, youtubeScript, sessionId, items } = body;

  if (!Array.isArray(items)) {
    throw new SubmitInvalidoError('items array required');
  }

  const approved = items.filter((i) => i.status === 'aprovado');
  // A guarda precede o caminho do manifesto e recusava a chamada do Studio
  // antes de olhar para ele: o grafo manda `items: []` e nenhum
  // `youtubeScript` — o roteiro dele é o manifesto estruturado.
  const temManifesto = Boolean(body.manifestV2?.youtube?.segments?.length);
  if (!approved.length && !temManifesto &&
      !(youtubeScript && youtubeScript.trim().length > 100)) {
    throw new SubmitInvalidoError('No approved items');
  }

  // Carrega a sessão para montar os metadados editoriais do projeto. A pauta
  // tem subtítulo, objetivo de aprendizado e hardskills — tudo que a descrição
  // do YouTube precisa e que antes ficava em branco.
  const sessionDraft = sessionId
    ? ((await loadSession(sessionId, tenantId)) as { draft?: Record<string, unknown> } | null)?.draft
    : undefined;
  // O manifesto v2 e os slides desenhados vivem no doc de artefatos da sessão
  // (campos pesados); loadSession já os recompõe dentro do draft.
  // O corpo tem precedência: o Studio manda o manifesto que ACABOU de ser
  // aprovado no gate, e ele é a verdade — o draft da sessão pode estar
  // desatualizado ou nem existir num fluxo que nasceu no grafo.
  const manifestV2 = (body.manifestV2 ?? sessionDraft?.manifestV2 ?? null) as ManifestV2 | null;
  const slideHtmls = (body.slideHtmls ?? sessionDraft?.slideHtmls ?? {}) as Record<string, string>;
  const articleLanguage = (sessionDraft?.language as string) || 'pt-BR';
  const articleUrl =
    (sessionDraft?.publishedArticleUrl as string) ||
    `${BLOG_BASE_URL}/${articleLanguage}/blog/${articleSlug}`;
  const projectCategory = (sessionDraft?.category as string) || 'ia';
  // A pauta do CORPO tem precedência: é a do grafo, e num fluxo do Studio o
  // `sessionDraft` não existe.
  const pautaEfetiva =
    (body.pauta as Record<string, unknown> | undefined) ??
    ((sessionDraft?.pauta ?? {}) as Record<string, unknown>);
  const projectMeta: ProjectMeta = {
    // Recalculada após o /build-manifest, que devolve os blocos escritos.
    description: buildDescription(pautaEfetiva, slideHtmls),
    tags:        buildTags({ pauta: pautaEfetiva }, projectCategory),
    articleUrl,
    subtitle:    ((sessionDraft?.pauta ?? {}) as Record<string, unknown>).subtitulo as string | undefined,
    category:    projectCategory,
  };

  // Token OIDC para publisher-immediate (Cloud Run autenticado)
  const publisherToken = await getCloudRunToken(PUBLISHER_URL);

  const pubsub = new PubSub({ projectId: GCP_PROJECT_ID });

  const results = {
    totalApproved:           approved.length,
    videoPipelineTriggered:  0,
    textPublished:           0,
    errors:                  [] as string[],
    publishedItems:          [] as { platform: string; post_id: string }[],
    /** Projeto do vídeo longo. É dele que o pacote é derivado depois. */
    mainProjectId:           '' as string,
    /** Itens de vídeo curto adiados até o vídeo do YouTube existir. */
    videoItemsDeferred:      0,
  };

  // ── 1. YouTube longo — gera manifesto e dispara pipeline ─────────────────────
  //
  // O manifesto v2 aprovado é enviado INTEIRO. A versão anterior mandava
  // `youtubeScript` — a concatenação das falas em texto puro — e deixava o
  // cmo_agent reconstruir a estrutura por parsing de Markdown. Como o texto
  // não tinha marcadores de seção, os 8 segmentos com 7 ilustrações viravam
  // 1 segmento sem ilustração nenhuma, e o vídeo saía 163s de avatar puro.
  if (manifestV2 && Array.isArray(manifestV2.youtube?.segments) && manifestV2.youtube.segments.length > 1) {
    const projectId = `${articleSlug}-yt-${Date.now()}`;
    try {
      console.log(`[pipeline-submit] Enviando manifesto aprovado para ${projectId}...`);

      const manifestRes = await fetch(`${CMO_AGENT_URL}/build-manifest`, {
        method:  'POST',
        // Propaga o tenantId JÁ VERIFICADO por requireTenantId() acima — sem
        // isto o cmo_agent sempre via o tenant default, mesmo quando esta
        // rota já sabia (com certeza) que a chamada era de outro tenant.
        headers: cmoAgentHeaders(tenantId),
        body:    JSON.stringify({
          manifest:    manifestV2,
          slide_htmls: slideHtmls,
          title:       articleTitle,
          project_id:  projectId,
          language:    (sessionDraft?.language as string) || 'pt-BR',
          // A pauta viaja junto só para a frase de capa da thumbnail ter tese
          // e público. Sem ela a frase sai genérica.
          pauta:       pautaEfetiva,
        }),
        signal: AbortSignal.timeout(60_000),
      });

      if (!manifestRes.ok) {
        throw new Error(`build-manifest failed ${manifestRes.status}: ${await manifestRes.text()}`);
      }

      const manifestData = await manifestRes.json() as ManifestBuildResult;

      // Gate do produto. Falhar aqui custa zero; falhar depois custa uma
      // geração inteira de HeyGen. Um manifesto que chegou colapsado ou sem
      // ilustração não vira vídeo — a pipeline nem é disparada.
      const violations = manifestData.violations ?? [];
      if (violations.length) {
        throw new Error(
          `manifesto recusado antes de gastar crédito — ${violations.join('; ')}`,
        );
      }

      const manifestPath = manifestData.manifest_gcs_path;
      console.log(
        `[pipeline-submit] Manifesto OK: ${manifestPath} — ${manifestData.segment_count} segmentos ` +
        `(${manifestData.avatar_segments} avatar / ${manifestData.slide_segments} ilustração), ` +
        `${Math.round((manifestData.avatar_share ?? 0) * 100)}% de avatar, ` +
        `~${manifestData.total_duration_s}s, ~$${manifestData.estimated_cost_usd}`,
      );

      // O projeto principal publica UM canal: o vídeo longo do YouTube, como
      // privado. Vertical, carrossel e copies não saem daqui — são derivados
      // depois, a partir deste vídeo, quando o dono do canal liberar o pacote.
      const mainChannels = ['youtube'];

      await createProjectDoc(projectId, articleTitle, manifestPath, articleSlug, sessionId, tenantId,
                             {
                               ...projectMeta,
                               channelsApproved: mainChannels,
                               // Só chega aqui: a frase nasce no /build-manifest,
                               // depois de projectMeta já ter sido montado.
                               shortFrase: manifestData.vertical_cut_title ?? undefined,
                               serie: typeof pautaEfetiva?.serie === 'string'
                                 ? pautaEfetiva.serie : undefined,
                               thumbFrase: manifestData.thumb_frase ?? undefined,
                               thumbApoio: manifestData.thumb_apoio ?? undefined,
                               description: buildDescription(
                                 pautaEfetiva, slideHtmls, manifestData.youtube_copy,
                               ),
                             });

      const msg = {
        project_id:        projectId,
        manifest_gcs_path: manifestPath,
        channels_approved: mainChannels,
        approved_at:       new Date().toISOString(),
        cost_limit:        DEFAULT_COST_LIMIT,
      };
      const topic = pubsub.topic(PIPELINE_TOPIC);
      await topic.publishMessage({ data: Buffer.from(JSON.stringify(msg)) });
      results.videoPipelineTriggered++;
      results.mainProjectId = projectId;
      console.log(`[pipeline-submit] Pipeline disparado: ${projectId}`);

    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      results.errors.push(`YouTube pipeline: ${msg}`);
      console.error('[pipeline-submit] YouTube pipeline error:', err);
    }
  } else if (youtubeScript && youtubeScript.trim().length > 100) {
    // Sem manifesto estruturado não há vídeo. Antes esta situação disparava a
    // pipeline mesmo assim, com o roteiro achatado — e o resultado era um
    // vídeo caro e errado que só aparecia no fim.
    results.errors.push(
      'YouTube pipeline: sessão sem manifesto v2 estruturado (draft.manifestV2). ' +
      'Gere o pacote novamente na aba Pacote antes de aprovar.',
    );
  }

  // ── 2. Processa cada item aprovado ─────────────────────────────────────────
  for (const item of approved) {
    const platform = item.platform;
    const format   = item.format;
    const isVideo  = VIDEO_FORMATS.has(format);
    const copy     = item.copy || item.script || '';

    // ── Texto: salva na social_queue (status=planned), NÃO publica imediatamente ──
    // O publisher-scheduled (Cloud Scheduler a cada hora) publica no scheduled_at.
    if (!isVideo && copy.trim().length > 0) {
      const db = getFirestoreDb();
      if (db) {
        try {
          await db.collection(dbPaths.socialQueue(tenantId)).add({
            platform,
            format,
            title:            item.title,
            copy,
            scheduled_at:     item.scheduledAt || new Date().toISOString(),
            status:           'planned',
            article_slug:     articleSlug,
            article_title:    articleTitle,
            // URL real do artigo publicado, para o publisher trocar
            // [LINK_ARTIGO] no momento da publicação. Guardada aqui porque na
            // hora de publicar (D+1..D+7) a sessão pode já ter sido reiniciada.
            article_url:      articleUrl,
            language:         articleLanguage,
            thread_posts:     item.threadPosts || null,
            image_url:        item.imageUrl    || null,
            video_url:        item.videoUrl    || null,
            // Carrossel publica N imagens numa chamada só, então asset_urls
            // precisa levar todas — pegar só a primeira transformaria o
            // carrossel num post de imagem única, silenciosamente.
            asset_urls:       (item.imageUrls && item.imageUrls.length)
                                ? item.imageUrls
                                : item.imageUrl ? [item.imageUrl]
                                : item.videoUrl ? [item.videoUrl] : [],
            session_id:       sessionId || null,
            retry_count:      0,
            error_message:    null,
            published_at:     null,
            platform_post_id: null,
            created_at:       new Date().toISOString(),
            updated_at:       new Date().toISOString(),
          });
          results.textPublished++;
          console.log(`[pipeline-submit] 📅 ${platform} agendado → ${item.scheduledAt}`);
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err);
          results.errors.push(`${platform}/${item.id} queue: ${msg}`);
        }
      }
      continue;
    }

    // ── Vídeo curto (Shorts/Reels): NÃO é uma produção nova ───────────────────
    //
    // Reel e Short são o mesmo arquivo: um recorte do vídeo do YouTube. O
    // avatar sai de um crop 9:16 do clipe horizontal já gerado, a fala é o
    // mesmo áudio TTS, e só a ilustração é redesenhada em 9:16.
    //
    // Antes, cada peça curta era um `content_project` independente com TTS,
    // avatar e edição próprios: três Reels = três produções completas, com o
    // dobro de chamadas ao HeyGen pela mesma fala. Pior, o roteiro do curto
    // não tinha relação nenhuma com o vídeo longo.
    //
    // Agora o corte só existe depois que o vídeo do YouTube existe e foi
    // aprovado — é o /api/csm/derive-vertical que o produz.
    if (isVideo) {
      results.videoItemsDeferred++;
      console.log(
        `[pipeline-submit] ${item.id} (${format}) adiado — será derivado do vídeo do YouTube.`,
      );
      continue;
    }

    // ── Itens restantes (carrosseis, stories, imagens): salva na fila ─────────
    const db = getFirestoreDb();
    if (db) {
      try {
        await db.collection('publish_queue').add({
          platform,
          format,
          title:           item.title,
          copy,
          scheduledAt:     item.scheduledAt,
          status:          'pending',
          slides:          item.slides    || null,
          imageUrl:        item.imageUrl  || null,
          videoUrl:        item.videoUrl  || null,
          imageDescription: item.imageDescription || null,
          sessionId:       sessionId || null,
          articleSlug,
          articleTitle,
          attempts:        0,
          error:           null,
          errorCode:       null,
          createdAt:       new Date().toISOString(),
          updatedAt:       new Date().toISOString(),
        });
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        results.errors.push(`${item.id} queue: ${msg}`);
      }
    }
  }

  return results;
}
