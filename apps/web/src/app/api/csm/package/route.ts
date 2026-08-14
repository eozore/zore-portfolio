/**
 * POST /api/csm/package
 *
 * Sprint 1 — G5 parcial: recebe uma pauta aprovada (PautaConcebida) e
 * dispara em paralelo a geração do artigo (SSE → texto) + derivações
 * (repurpose). Retorna um JSON consolidado com artigo + repurposedData.
 *
 * Autenticação: Firebase Admin ADC (nunca API Key hardcoded).
 */

import { NextResponse } from 'next/server';
import { loadSession, saveDraftToSession } from '@/lib/session';
import { isCsmAuthenticated, csmUnauthorized } from '@/lib/csmAuth';
import { cmoAgentHeaders } from '@/lib/cmoAgent';
import { getEnabledChannelToggles } from '@/lib/channelToggles';
import { filterDerivativesByChannels } from '@/lib/channels';

export interface PautaConcebida {
  titulo: string;
  subtitulo: string;
  tese: string;
  publico: string;
  duracao_alvo: string;
  serie: string;
  objetivo_aprendizado?: string;
  hardskills?: string[];
  tipo_artigo?: 'tecnico' | 'conceitual' | 'estrategico';
  nivel_tecnico?: 'baixo' | 'medio' | 'alto';
}

export interface PackageRequest {
  pauta: PautaConcebida;
  chatTranscript: string;
  category: string;
  language?: 'pt-BR' | 'en';
  sessionId?: string;
  /** Se fornecido, pula a geração do artigo e usa este conteúdo diretamente */
  articleContent?: string;
  /** Mantido explícito para evitar gerar derivações antes da aprovação do roteiro. */
  generateDerivatives?: boolean;
}

export interface PackageResult {
  pauta: PautaConcebida;
  /** Artigo em Markdown (conteúdo gerado pelo agente escritor) */
  articleContent: string;
  suggestedTitle: string;
  suggestedSlug: string;
  estimatedReadTime: number;
  /** Derivações omnicanal já estruturadas */
  repurposedData: unknown | null;
  /** Manifesto v2 com anchors[] (Sprint 3 / G3) — retornado pelo scriptwriter_agent */
  manifestV2?: unknown | null;
  /** Roteiro falado extraído do manifesto, usado pela aprovação e pela pipeline */
  youtubeScript?: string;
  /** HTML do manifesto v2 (deck Playwright-ready para preview) */
  manifestHtml?: string;
  /** Thumbnails HTML 1200×628 (Sprint 2 / G1) */
  thumbnails?: { option_minimal: string; option_provocative: string } | null;
  /** Copies especializados (LinkedIn + Threads) do copy_agent (Sprint 2 / G1) */
  specialistCopies?: { linkedin_posts: unknown[]; threads: unknown[] } | null;
  /** Flag de erro parcial (ex: repurpose falhou mas artigo ok) */
  partialError?: string;
}

// Tempo máximo: 15 minutos (artigo + repurpose + specialists podem levar até 12 min)
export const maxDuration = 900;

function slugify(str: string): string {
  return str
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9\s-]/g, '')
    .trim()
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .slice(0, 100);
}

/**
 * Consume o stream SSE de /api/csm/generate e retorna o texto final limpo.
 * Extrai também o bloco META: {...} para título/slug/readTime.
 */
async function consumeGenerateStream(
  baseUrl: string,
  body: object,
  cookie: string,
): Promise<{ content: string; title: string; slug: string; readTime: number }> {
  const res = await fetch(`${baseUrl}/api/csm/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Cookie: cookie },
    body: JSON.stringify(body),
  });

  if (!res.ok || !res.body) {
    const errText = await res.text().catch(() => res.statusText);
    throw new Error(`generate stream error ${res.status}: ${errText}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let content = '';
  let title = '';
  let slug = '';
  let readTime = 10;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith('data: ')) continue;
      const jsonStr = trimmed.slice(6).trim();
      if (!jsonStr || jsonStr === '[DONE]') continue;

      try {
        const parsed = JSON.parse(jsonStr);
        if (parsed.type === 'content') {
          content += parsed.chunk ?? '';
        } else if (parsed.type === 'replace') {
          content = parsed.content ?? content;
        } else if (parsed.type === 'meta') {
          title = parsed.title ?? title;
          slug = parsed.slug ?? slug;
          readTime = parsed.readTime ?? readTime;
        } else if (parsed.type === 'error') {
          throw new Error(parsed.message ?? 'generate stream internal error');
        }
      } catch {
        // linha incompleta — ignorar
      }
    }
  }

  // Limpeza final: strip thinking blocks + extrair META inline se não chegou via evento
  content = content.replace(/<think>[\s\S]*?<\/think>/g, '').trim();

  if (!title) {
    const metaMatch = content.match(/META:\s*(\{[^}]+\})/);
    if (metaMatch) {
      try {
        const meta = JSON.parse(metaMatch[1].replace(/,\s*([}\]])/g, '$1'));
        title = meta.title ?? '';
        slug = meta.slug ? slugify(meta.slug) : slugify(title);
        readTime = Number.isInteger(meta.readTime) ? meta.readTime : 10;
      } catch {
        // ignora parse error
      }
    }
  }

  content = content.replace(/\n?META:\s*\{[^}]+\}\s*/g, '').trimEnd();

  if (!title) title = ''; // será preenchido pelo caller com pauta.titulo
  if (!slug) slug = '';

  return { content, title, slug, readTime };
}

export async function POST(request: Request): Promise<Response> {
  if (!isCsmAuthenticated(request)) return csmUnauthorized();

  let body: PackageRequest;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const {
    pauta, chatTranscript, category, language = 'pt-BR', sessionId,
    articleContent: prebuiltArticle, generateDerivatives = false,
  } = body;

  if (!pauta?.titulo || pauta.titulo.trim().length < 5) {
    return NextResponse.json(
      { error: 'pauta.titulo is required (min 5 chars)' },
      { status: 400 }
    );
  }

  // Monta contexto rico para o gerador de artigo
  const context = `=== PAUTA APROVADA PELO CMO ===
Título: ${pauta.titulo}
Subtítulo: ${pauta.subtitulo}
Tese escolhida: ${pauta.tese}
Público-alvo: ${pauta.publico}
Duração alvo (vídeo): ${pauta.duracao_alvo}
Série: ${pauta.serie}
tipo_artigo: ${pauta.tipo_artigo ?? 'tecnico'}
Nível Técnico: ${pauta.nivel_tecnico ?? 'medio'}
Objetivo de aprendizado: ${pauta.objetivo_aprendizado ?? ''}
Hardskills: ${(pauta.hardskills ?? []).join(', ')}

=== TRANSCRIÇÃO DA REUNIÃO CEO × CMO ===
${chatTranscript}`.trim();

  // Base URL para chamadas internas (API route para API route via fetch)
  const baseUrl = process.env.NEXTAUTH_URL ||
    (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : 'http://localhost:3000');
  const cookie = request.headers.get('cookie') || '';

  // ── Disparo paralelo: artigo + repurpose (repurpose recebe placeholder no início) ──
  const generatePayload = {
    topic: pauta.titulo,
    context,
    format: 'blog',
    category,
    language,
    sessionId,
  };

  let articleContent = '';
  let suggestedTitle = pauta.titulo;
  let suggestedSlug = slugify(pauta.titulo);
  let estimatedReadTime = 10;
  let repurposedData: unknown = null;
  let partialError: string | undefined;

  if (prebuiltArticle && prebuiltArticle.trim().length > 100) {
    // Artigo já foi gerado e publicado — usa diretamente, pula geração
    articleContent    = prebuiltArticle;
    suggestedTitle    = pauta.titulo;
    suggestedSlug     = slugify(pauta.titulo);
    estimatedReadTime = Math.max(1, Math.round(prebuiltArticle.trim().split(/\s+/).length / 200));
    console.log('[csm/package] Usando artigo pré-gerado — pulando etapa de geração.');
  } else {
    try {
      const articleResult = await consumeGenerateStream(baseUrl, generatePayload, cookie);
      articleContent    = articleResult.content;
      suggestedTitle    = articleResult.title || pauta.titulo;
      suggestedSlug     = articleResult.slug  || slugify(pauta.titulo);
      estimatedReadTime = articleResult.readTime;
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'article generation failed';
      console.error('[csm/package] Article generation error:', msg);
      if (sessionId) {
        try {
          const tenantId = request.headers.get('x-tenant-id') || null;
          const session = await loadSession(sessionId, tenantId);
          const currentDraft = (session as { draft?: Record<string, unknown> } | null)?.draft ?? {};
          await saveDraftToSession(sessionId, {
            ...currentDraft,
            packageStatus: 'error',
            workflowStage: 'error',
            packageError: msg,
          }, tenantId);
        } catch (persistError) {
          console.error('[csm/package] failed to persist article error', persistError);
        }
      }
      return NextResponse.json({ error: `Falha na geração do artigo: ${msg}` }, { status: 500 });
    }
  }

  // Etapa 2: roteiro principal e artefatos especialistas.
  // As derivações sociais só podem ser criadas depois que o roteiro existe.
  // Chamada ao endpoint /package do CMO Agent Python (Sprint 2/3)
  let manifestV2: unknown = null;
  let manifestHtml = '';
  let thumbnails: { option_minimal: string; option_provocative: string } | null = null;
  let specialistCopies: { linkedin_posts: unknown[]; threads: unknown[] } | null = null;
  let generatedYoutubeScript = '';

  const cmoAgentUrl = process.env.CMO_AGENT_URL;
  if (cmoAgentUrl && articleContent) {
    try {
      const specialistRes = await fetch(`${cmoAgentUrl}/package`, {
        method: 'POST',
        headers: { ...cmoAgentHeaders(), Cookie: cookie },
        body: JSON.stringify({
          pauta: {
            titulo:               pauta.titulo,
            subtitulo:            pauta.subtitulo,
            tese:                 pauta.tese,
            publico:              pauta.publico,
            duracao_alvo:         pauta.duracao_alvo,
            serie:                pauta.serie,
            objetivo_aprendizado: pauta.objetivo_aprendizado ?? '',
            hardskills:           pauta.hardskills ?? [],
            tipo_artigo:          pauta.tipo_artigo ?? 'tecnico',
            nivel_tecnico:        pauta.nivel_tecnico ?? 'medio',
          },
          articleContent,
          category,
          language,
          sessionId,
          phase: 'script',
        }),
        signal: AbortSignal.timeout(480_000),  // 8 min — scriptwriter+thumbnail+copy em paralelo
      });

      if (specialistRes.ok) {
        const spData = await specialistRes.json();
        manifestV2       = spData.manifest      ?? null;
        manifestHtml     = spData.manifestHtml  ?? '';
        thumbnails       = spData.thumbnails    ?? null;
        specialistCopies = spData.copies        ?? null;
        if (spData.partialErrors?.length) {
          partialError = (partialError ? partialError + ' | ' : '') +
            `specialist: ${spData.partialErrors.join('; ')}`;
        }
        console.log('[csm/package] Specialist agents completed (manifest+thumbnails+copies)');
      } else {
        const errText = await specialistRes.text().catch(() => specialistRes.statusText);
        partialError = (partialError ? partialError + ' | ' : '') +
          `specialist-agents (${specialistRes.status}): ${errText.slice(0, 200)}`;
        console.warn('[csm/package] Specialist agents partial error:', partialError);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'specialist agents timeout';
      partialError = (partialError ? partialError + ' | ' : '') + `specialist-agents: ${msg}`;
      console.warn('[csm/package] Specialist agents failed (non-fatal):', msg);
    }
  }

  // Etapa 3: derivações omnicanal baseadas no artigo e no roteiro gerado.
  // Esta etapa só roda depois que o usuário aprova o roteiro na ReviewTab.
  const manifest = manifestV2 as { youtube?: { segments?: { script?: string }[] } } | null;
  generatedYoutubeScript = manifest?.youtube?.segments
    ?.map((segment) => segment.script ?? '')
    .filter(Boolean)
    .join('\n\n') ?? '';

  if (generateDerivatives) try {
    const repurposeRes = await fetch(`${baseUrl}/api/csm/repurpose`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Cookie: cookie },
      body: JSON.stringify({
        title: suggestedTitle,
        slug: suggestedSlug,
        content: articleContent,
        category,
        language,
        youtubeScript: generatedYoutubeScript,
      }),
      signal: AbortSignal.timeout(480_000),
    });

    if (repurposeRes.ok) {
      repurposedData = await repurposeRes.json();
    } else {
      const errText = await repurposeRes.text().catch(() => repurposeRes.statusText);
      partialError = `Derivações falharam (${repurposeRes.status}): ${errText.slice(0, 200)}`;
      console.warn('[csm/package] Repurpose partial error:', partialError);
    }
  } catch (err) {
    partialError = err instanceof Error ? err.message : 'repurpose timeout or network error';
    console.warn('[csm/package] Repurpose partial error:', partialError);
  }

  // Remove das derivações qualquer canal que o usuário tenha desligado em
  // Configurações → Canais & Formatos, antes de expor o resultado ou persistir.
  const tenantIdForChannels = request.headers.get('x-tenant-id') || null;
  const channelToggles = await getEnabledChannelToggles(tenantIdForChannels);
  const filteredRepurposedData = repurposedData && typeof repurposedData === 'object'
    ? filterDerivativesByChannels(repurposedData as Record<string, unknown>, channelToggles)
    : repurposedData;
  const filteredSpecialistCopies = specialistCopies && typeof specialistCopies === 'object'
    ? filterDerivativesByChannels(specialistCopies as Record<string, unknown>, channelToggles)
    : specialistCopies;

  const result: PackageResult = {
    pauta,
    articleContent,
    suggestedTitle,
    suggestedSlug,
    estimatedReadTime,
    repurposedData: filteredRepurposedData,
    manifestV2,
    youtubeScript: generatedYoutubeScript,
    manifestHtml,
    thumbnails,
    specialistCopies: filteredSpecialistCopies as PackageResult['specialistCopies'],
    ...(partialError ? { partialError } : {}),
  };

  // O pacote é assíncrono em relação à publicação do artigo. Persistir o
  // resultado aqui é obrigatório para que a aba de revisão sobreviva a
  // reloads e a uma troca de instância do Cloud Run.
  if (sessionId) {
    try {
      const tenantId = tenantIdForChannels;
      const session = await loadSession(sessionId, tenantId);
      const currentDraft = (session as { draft?: Record<string, unknown> } | null)?.draft ?? {};
      await saveDraftToSession(sessionId, {
        ...currentDraft,
        generatedContent: articleContent,
        suggestedTitle,
        suggestedSlug,
        estimatedReadTime,
        manifestV2,
        youtubeScript: generatedYoutubeScript,
        manifestHtml,
        thumbnails,
        specialistCopies: filteredSpecialistCopies,
        repurposedData: filteredRepurposedData,
        packageStatus: generatedYoutubeScript ? (generateDerivatives ? 'ready' : 'script_ready') : 'error',
        workflowStage: generatedYoutubeScript ? (generateDerivatives ? 'package_ready' : 'script_ready') : 'error',
        packageError: partialError ?? '',
      }, tenantId);
    } catch (err) {
      console.error('[csm/package] failed to persist package state', err);
    }
  }

  return NextResponse.json(result);
}
