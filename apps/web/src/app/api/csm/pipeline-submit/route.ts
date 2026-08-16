/**
 * POST /api/csm/pipeline-submit
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

import { NextResponse } from 'next/server';
import { getFirestoreDb } from '@/lib/firebase';
import { PubSub } from '@google-cloud/pubsub';
import { GoogleAuth } from 'google-auth-library';
import { isCsmAuthenticated, csmUnauthorized } from '@/lib/csmAuth';
import { dbPaths } from '@/lib/dbPaths';
import { cmoAgentHeaders } from '@/lib/cmoAgent';
import { loadSession } from '@/lib/session';

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

interface SubmitItem {
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

interface SubmitRequest {
  articleSlug:   string;
  articleTitle:  string;
  youtubeScript?: string;   // Roteiro da Aba 4 (Markdown com cenas)
  sessionId?:    string;
  items:         SubmitItem[];
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
  description?: string;
  tags?:        string[];
  articleUrl?:  string;
  subtitle?:    string;
  category?:    string;
}

/**
 * Monta a descrição do YouTube a partir da pauta.
 *
 * O publisher lia `meta.description` e caía em string vazia porque este
 * documento nunca gravava o campo — o vídeo subiria com descrição em branco e
 * o copy_social de LinkedIn/Threads/Instagram começaria literalmente com "...".
 */
function buildDescription(draft: Record<string, unknown> | undefined): string {
  const pauta = (draft?.pauta ?? {}) as Record<string, unknown>;
  const parts: string[] = [];

  if (typeof pauta.subtitulo === 'string' && pauta.subtitulo.trim()) {
    parts.push(pauta.subtitulo.trim());
  }
  if (typeof pauta.objetivo_aprendizado === 'string' && pauta.objetivo_aprendizado.trim()) {
    parts.push(`Neste vídeo: ${pauta.objetivo_aprendizado.trim()}`);
  }
  const skills = Array.isArray(pauta.hardskills) ? (pauta.hardskills as string[]) : [];
  if (skills.length) {
    parts.push(`O que você vai desenvolver:\n${skills.map((s) => `• ${s}`).join('\n')}`);
  }
  return parts.join('\n\n');
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
    article_url:  meta.articleUrl ?? '',
    subtitle:     meta.subtitle ?? '',
    category:     meta.category ?? 'ia',
    stages: {
      tts:    { status: 'pending' },
      avatar: { status: 'pending' },
      editor: { status: 'pending' },
    },
  });
}

// ── Handler principal ─────────────────────────────────────────────────────────

export async function POST(request: Request): Promise<Response> {
  if (!isCsmAuthenticated(request)) return csmUnauthorized();

  let body: SubmitRequest;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const { articleSlug, articleTitle, youtubeScript, sessionId, items } = body;
  const tenantId = request.headers.get('x-tenant-id') || null;
  if (!Array.isArray(items)) {
    return NextResponse.json({ error: 'items array required' }, { status: 400 });
  }

  const approved = items.filter((i) => i.status === 'aprovado');
  if (!approved.length && !(youtubeScript && youtubeScript.trim().length > 100)) {
    return NextResponse.json({ error: 'No approved items' }, { status: 400 });
  }

  // Carrega a sessão para montar os metadados editoriais do projeto. A pauta
  // tem subtítulo, objetivo de aprendizado e hardskills — tudo que a descrição
  // do YouTube precisa e que antes ficava em branco.
  const sessionDraft = sessionId
    ? ((await loadSession(sessionId, tenantId)) as { draft?: Record<string, unknown> } | null)?.draft
    : undefined;
  const articleLanguage = (sessionDraft?.language as string) || 'pt-BR';
  const articleUrl =
    (sessionDraft?.publishedArticleUrl as string) ||
    `${BLOG_BASE_URL}/${articleLanguage}/blog/${articleSlug}`;
  const projectCategory = (sessionDraft?.category as string) || 'ia';
  const projectMeta: ProjectMeta = {
    description: buildDescription(sessionDraft),
    tags:        buildTags(sessionDraft, projectCategory),
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
  };

  // ── 1. YouTube longo — gera manifesto e dispara pipeline ─────────────────────
  if (youtubeScript && youtubeScript.trim().length > 100) {
    const projectId = `${articleSlug}-yt-${Date.now()}`;
    try {
      console.log(`[pipeline-submit] Gerando manifesto para ${projectId}...`);

      // a. Chama cmo_agent para construir manifesto e salvar no GCS
      const manifestRes = await fetch(`${CMO_AGENT_URL}/build-manifest`, {
        method:  'POST',
        headers: cmoAgentHeaders(),
        body:    JSON.stringify({
          script:     youtubeScript,
          title:      articleTitle,
          project_id: projectId,
          language:   'pt-BR',
        }),
        signal: AbortSignal.timeout(30_000),
      });

      if (!manifestRes.ok) {
        throw new Error(`build-manifest failed ${manifestRes.status}: ${await manifestRes.text()}`);
      }

      const manifestData = await manifestRes.json();
      const manifestPath = manifestData.manifest_gcs_path as string;
      console.log(`[pipeline-submit] Manifesto criado: ${manifestPath} (${manifestData.avatar_segments} segments, ~$${manifestData.estimated_cost_usd})`);

      // b. Cria documento do projeto no Firestore
      await createProjectDoc(projectId, articleTitle, manifestPath, articleSlug, sessionId, tenantId, projectMeta);

      // c. Publica PackageApprovedMsg no Pub/Sub
      const msg = {
        project_id:        projectId,
        manifest_gcs_path: manifestPath,
        channels_approved: ['youtube', 'youtube_short', 'instagram_reel'],
        approved_at:       new Date().toISOString(),
        cost_limit:        DEFAULT_COST_LIMIT,
      };
      const topic = pubsub.topic(PIPELINE_TOPIC);
      await topic.publishMessage({ data: Buffer.from(JSON.stringify(msg)) });
      results.videoPipelineTriggered++;
      console.log(`[pipeline-submit] Pipeline disparado: ${projectId}`);

    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      results.errors.push(`YouTube pipeline: ${msg}`);
      console.error('[pipeline-submit] YouTube pipeline error:', err);
    }
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

    // ── Vídeo curto (Shorts/Reels): gera manifesto e dispara pipeline ─────────
    if (isVideo && copy.trim().length > 50) {
      const orientation = (format === 'shorts' || format === 'reel') ? 'vertical' : 'horizontal';
      const projectId   = `${articleSlug}-${format}-${item.id.slice(0, 6)}-${Date.now()}`;

      try {
        // Gera manifesto para o roteiro do vídeo curto
        const manifestRes = await fetch(`${CMO_AGENT_URL}/build-manifest`, {
          method:  'POST',
          headers: cmoAgentHeaders(),
          body:    JSON.stringify({
            script:     copy,
            title:      item.title,
            project_id: projectId,
            language:   'pt-BR',
          }),
          signal: AbortSignal.timeout(30_000),
        });

        if (!manifestRes.ok) {
          throw new Error(`build-manifest failed ${manifestRes.status}`);
        }

        const { manifest_gcs_path: manifestPath } = await manifestRes.json();
        await createProjectDoc(projectId, item.title, manifestPath, articleSlug, sessionId, tenantId, projectMeta);

        const msg = {
          project_id:        projectId,
          manifest_gcs_path: manifestPath,
          channels_approved: [orientation === 'vertical' ? 'instagram_reel' : 'youtube'],
          approved_at:       new Date().toISOString(),
          cost_limit:        DEFAULT_COST_LIMIT,
        };
        const topic = pubsub.topic(PIPELINE_TOPIC);
        await topic.publishMessage({ data: Buffer.from(JSON.stringify(msg)) });
        results.videoPipelineTriggered++;
        console.log(`[pipeline-submit] Short/Reel pipeline: ${projectId}`);

      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        results.errors.push(`${item.id} pipeline: ${msg}`);
      }
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

  return NextResponse.json(results, { status: 200 });
}
