import { NextResponse } from 'next/server';
import { getApps, initializeApp, cert } from 'firebase-admin/app';
import { getFirestoreDb } from '@/lib/firebase';
import type { ArticleCategory } from '@/types/article';

type OutputFormat = 'blog' | 'youtube' | 'linkedin';

interface GenerateRequest {
  topic: string;
  context?: string;
  format: OutputFormat;
  category: ArticleCategory;
  language: 'pt-BR' | 'en';
}

import { getVertexAccessToken, getVertexStreamEndpoint } from '@/lib/vertex';
import { dbPaths } from '@/lib/dbPaths';
import { logUsage } from '@/lib/usage';

// ── System prompt builders ────────────────────────────────────────────────────

function buildSystemPrompt(format: OutputFormat, category: ArticleCategory, language: 'pt-BR' | 'en'): string {
  const lang = language === 'pt-BR' ? 'Português Brasileiro' : 'English';
  const categoryMap: Record<ArticleCategory, string> = {
    estatistica: 'Estatística e Probabilidade',
    ml: 'Machine Learning e MLOps',
    ia: 'Inteligência Artificial e LLMs',
  };
  const categoryLabel = categoryMap[category];

  const basePersona = `Você é Victor Zoré, líder técnico sênior em IA Generativa e Machine Learning com formação matemática sólida pela UFSCar.
Sua filosofia de ensino: sempre ensine o PORQUÊ (a teoria matemática, lógica e arquitetural) ANTES do COMO (código ou biblioteca).
Área de expertise: ${categoryLabel}.
Idioma de resposta: ${lang}.
Tom: técnico, rigoroso e direto. Evite generalidades. Prefira profundidade a amplitude.`;

  if (format === 'blog') {
    return `${basePersona}

FORMATO: Artigo de Blog (GitHub Flavored Markdown + LaTeX estritamente no padrão ARTICLE_FORMAT.md)

REGRAS OBRIGATÓRIAS DE ESTRUTURA E FORMATAÇÃO:
1. NÃO inclua H1 (# Título) no corpo — o título principal é renderizado externamente pela página.
2. Comece diretamente com um parágrafo de introdução envolvente (sem nenhum heading).
3. Use ## para seções principais e ### para subseções.
4. Use --- em uma linha isolada para separar todas as seções principais.
5. Fórmulas LaTeX: use $...$ para fórmulas inline e $$...$$ em bloco isolado para equações centralizadas.
   - Regras LaTeX: use \\text{...} para texto, \\left( e \\right) para parênteses escaláveis, \\exp(...) em vez de e^{...}. Evite \\\\ para quebra de linha em equações.
6. Blocos de código: sempre especifique a linguagem após os backticks (\`\`\`python, \`\`\`typescript, \`\`\`bash, \`\`\`sql). Para mostrar outputs/resultados de execução, use blocos sem linguagem (\`\`\`).
7. Tabelas GFM: sempre inclua a linha separadora (|---|---|---|) e use negrito nos cabeçalhos importantes (**Conceito**).
8. Gráficos e Visualizações (Mermaid): Você OBRIGATORIAMENTE deve incluir 1 ou 2 blocos de diagrama Mermaid (\`\`\`mermaid) ilustrando fluxogramas, pipelines de tensores ou arquiteturas de rede descritas no texto.
   - Regra Crítica de Segurança de Sintaxe do Mermaid: NUNCA inclua termos com fórmulas LaTeX (como $...$ ou $$...$$) dentro dos diagramas Mermaid. Todos os rótulos de nós contendo caracteres especiais, acentos, parênteses ou símbolos devem ser colocados entre aspas duplas, por exemplo: id1["Espaço Latente (Z)"] ou subgraph "Otimização de Pesos". Falhar nisso causará um crash no renderizador.
9. Callouts / Destaques: use blockquotes com emojis e negrito exatamente nestes formatos:
   > **⚠️ Atenção:** aviso importante...
   > **💡 Dica:** sugestão prática...
   > **📊 Resultado:** métrica ou conclusão...
10. Estrutura lógica obrigatória: Introdução direta → --- → ## Fundamentação Matemática (o "Porquê" com fórmulas LaTeX e fluxos Mermaid) → --- → ## Implementação Prática Comentada (o "Como" em código) → --- → ## Conclusão / Resumo (Tabela GFM comparativa).
11. Extensão: mínimo de 1000 palavras, máximo de 4000 palavras.

METADADOS (emita estritamente no FINAL do texto gerado, em uma única linha separada prefixada com "META:"):
META: {"title": "Título Sugerido do Artigo (máx 150 chars)", "slug": "slug-sugerido-sem-acentos", "readTime": tempo_estimado_inteiro}`;
  }

  if (format === 'youtube') {
    return `${basePersona}

FORMATO: Roteiro para Vídeo YouTube (script técnico educacional)

ESTRUTURA OBRIGATÓRIA:
1. [GANCHO - 0:00-0:30] Pergunta ou provocação que captura atenção imediata
2. [INTRO - 0:30-1:30] Apresentação do problema e o que o espectador vai aprender
3. [TEORIA - 1:30-X:XX] Fundamentos matemáticos/conceituais explicados de forma visual
4. [CÓDIGO - X:XX-X:XX] Implementação prática comentada
5. [DEMO - X:XX-X:XX] Resultado e análise
6. [CONCLUSÃO + CTA - último 1 min] Resumo e call to action

REGRAS:
- Use [TIMECODE] para cada seção
- Use [B-ROLL: descrição] para indicar imagens/animações sugeridas
- Use [PAUSE] para pausas dramáticas
- Tom conversacional mas técnico — fale diretamente com o espectador ("você")
- Inclua falas completas, não bullet points
- Duração alvo: 15-25 minutos de conteúdo

METADADOS no final:
META: {"title": "título do vídeo sugerido", "slug": "slug-sugerido", "readTime": duração_em_minutos}`;
  }

  // linkedin
  return `${basePersona}

FORMATO: Post LinkedIn (texto profissional de alto engajamento)

REGRAS OBRIGATÓRIAS:
1. Máximo de 1300 caracteres (LinkedIn trunca após 3 linhas sem "ver mais")
2. Primeira linha = GANCHO poderoso (pergunta, afirmação ousada ou número surpreendente)
3. Use emojis estrategicamente — 1-2 por parágrafo no máximo
4. Bullets com • ou números para listas
5. Parágrafos curtos (2-3 linhas máximo cada)
6. Termine com: uma pergunta para engajamento + hashtags relevantes (3-5)
7. Tom: profissional mas humano, baseado em experiência real

METADADOS no final:
META: {"title": "assunto do post", "slug": "assunto-do-post", "readTime": 1}`;
}

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

// ── Route Handler ─────────────────────────────────────────────────────────────

/**
 * POST /api/csm/generate
 *
 * Uses Vertex AI (Gemini) with Application Default Credentials —
 * the same credentials already used by Firebase Admin.
 * No GEMINI_API_KEY needed.
 *
 * Local: gcloud auth application-default login
 * Cloud Run: automatic via service account
 *
 * Returns Server-Sent Events (SSE):
 *   data: {"type": "content", "chunk": "..."}
 *   data: {"type": "replace", "content": "..."}   ← final clean content
 *   data: {"type": "meta", "title": "...", "slug": "...", "readTime": N}
 *   data: {"type": "error", "message": "..."}
 *   data: [DONE]
 */
// Allow up to 10 minutes for the multi-agent pipeline (Critic → Research → Writing)
export const maxDuration = 600;

export async function POST(request: Request): Promise<Response> {
  const projectId = process.env.FIREBASE_PROJECT_ID;
  if (!projectId) {
    return NextResponse.json(
      { error: 'FIREBASE_PROJECT_ID not set — required for Vertex AI' },
      { status: 500 }
    );
  }

  let body: GenerateRequest;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 });
  }

  const { topic, context, format, category, language, sessionId } = body;
  const tenantId = request.headers.get('x-tenant-id') || null;

  if (!topic || topic.trim().length < 10) {
    return NextResponse.json({ error: 'topic must be at least 10 characters' }, { status: 400 });
  }

  // ── Python Microservice Proxy Bridge with local direct Vertex AI fallback ──
  const cmoAgentUrl = process.env.CMO_AGENT_URL || 'http://localhost:8090';
  try {
    console.log(`[csm/generate] Attempting to proxy generation to Python service: ${cmoAgentUrl}/generate`);
    const pythonRes = await fetch(`${cmoAgentUrl}/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Tenant-ID': tenantId || '',
      },
      body: JSON.stringify({
        topic,
        context,
        format,
        category,
        language,
        sessionId,
      }),
      // No AbortSignal here — the multi-agent pipeline (Critic → Research → Writing)
      // can take 3-8 minutes. We let the stream flow until the Python agent finishes.
    });

    if (pythonRes.ok && pythonRes.body) {
      console.log('[csm/generate] Successfully connected to Python microservice. Proxying stream...');
      return new Response(pythonRes.body, {
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'X-Accel-Buffering': 'no',
        },
      });
    } else {
      console.warn(`[csm/generate] Python service returned HTTP status ${pythonRes.status}. Falling back to direct Vertex AI.`);
    }
  } catch (err) {
    console.warn('[csm/generate] Python agent service unreachable or timed out. Falling back to direct Vertex AI.', err);
  }

  const systemPrompt = buildSystemPrompt(format, category, language);
  const userMessage = context
    ? `Tópico: ${topic}\n\nContexto adicional: ${context}`
    : `Tópico: ${topic}`;

  const vertexPayload = {
    contents: [
      {
        role: 'user',
        parts: [{ text: userMessage }],
      },
    ],
    systemInstruction: {
      parts: [{ text: systemPrompt }],
    },
    generationConfig: {
      temperature: 0.7,
      topP: 0.9,
      maxOutputTokens: 8192,
    },
  };

  const stream = new ReadableStream({
    async start(controller) {
      const encoder = new TextEncoder();

      const send = (data: object) => {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`));
      };

      try {
        const accessToken = await getVertexAccessToken();

        const vertexRes = await fetch(getVertexStreamEndpoint(projectId), {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify(vertexPayload),
        });

        if (!vertexRes.ok) {
          const errText = await vertexRes.text();
          console.error('[csm/generate] Vertex AI error:', vertexRes.status, errText);
          send({ type: 'error', message: `Vertex AI error: ${vertexRes.status}` });
          controller.enqueue(encoder.encode('data: [DONE]\n\n'));
          controller.close();
          return;
        }

        if (!vertexRes.body) {
          send({ type: 'error', message: 'No response body from Vertex AI' });
          controller.enqueue(encoder.encode('data: [DONE]\n\n'));
          controller.close();
          return;
        }

        const reader = vertexRes.body.getReader();
        const dec = new TextDecoder();
        let buffer = '';
        let fullText = '';
        let promptTokens = 0;
        let candidatesTokens = 0;
        const startTime = Date.now();

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += dec.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith('data: ')) continue;
            const jsonStr = trimmed.slice(6).trim();
            if (!jsonStr || jsonStr === '[DONE]') continue;

            try {
              const parsed = JSON.parse(jsonStr);
              const text = parsed?.candidates?.[0]?.content?.parts?.[0]?.text;
              if (text) {
                fullText += text;
                send({ type: 'content', chunk: text });
              }
              const usage = parsed?.usageMetadata;
              if (usage) {
                promptTokens = usage.promptTokenCount || promptTokens;
                candidatesTokens = usage.candidatesTokenCount || candidatesTokens;
              }
            } catch {
              // Skip unparseable lines
            }
          }
        }

        // Parse META from the tail of the generated content
        const metaMatch = fullText.match(/META:\s*(\{[^}]+\})\s*$/m);
        if (metaMatch) {
          try {
            const cleanedMeta = metaMatch[1].replace(/,\s*([}\]])/g, '$1');
            const meta = JSON.parse(cleanedMeta);
            const suggestedTitle = meta.title || topic.slice(0, 150);
            const suggestedSlug = meta.slug ? slugify(meta.slug) : slugify(suggestedTitle);
            const readTime = Number.isInteger(meta.readTime) ? meta.readTime : 10;

            send({ type: 'meta', title: suggestedTitle, slug: suggestedSlug, readTime });

            // Send clean content (without the META line)
            const cleanedContent = fullText.replace(/\n?META:\s*\{[^}]+\}\s*$/m, '').trimEnd();
            send({ type: 'replace', content: cleanedContent });
          } catch {
            // META parsing failed — no problem
          }
        }

        if (promptTokens > 0) {
          const duration = Date.now() - startTime;
          logUsage(
            tenantId,
            'article_generation',
            'gemini-1.5-flash',
            promptTokens,
            candidatesTokens,
            duration
          ).catch((err) => console.error('[csm/generate] Usage log fail:', err));
        }

        controller.enqueue(encoder.encode('data: [DONE]\n\n'));
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Internal streaming error';
        console.error('[csm/generate] Error:', err);
        send({ type: 'error', message });
        controller.enqueue(encoder.encode('data: [DONE]\n\n'));
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'X-Accel-Buffering': 'no',
    },
  });
}
