import { NextResponse } from 'next/server';
import { generateContent } from '@/lib/vertex';
import { getEcosystemMemory, formatMemoryForPrompt } from '@/lib/retrieval';

interface RepurposeRequest {
  title: string;
  slug?: string;
  content: string;
  category: string;
  language?: 'pt-BR' | 'en';
}

function cleanAndRepairJson(str: string): string {
  let cleaned = str.trim();
  if (cleaned.startsWith('```')) {
    cleaned = cleaned.replace(/^```(?:json)?\n?/i, '').replace(/\n?```$/m, '');
  }
  cleaned = cleaned.trim();
  cleaned = cleaned.replace(/,\s*([}\]])/g, '$1');
  return cleaned;
}

// Allow up to 10 minutes for the Distribution Agent structured output pipeline
export const maxDuration = 600;

export async function POST(request: Request): Promise<Response> {
  let body: RepurposeRequest;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const { title, slug, content, category, youtubeScript, language = 'pt-BR' } = body;
  if (!content) {
    return NextResponse.json({ error: 'Content is required' }, { status: 400 });
  }

  const resolvedTitle = title || 'Campanha de Midias';
  const resolvedSlug = slug || 'campanha';

  // ── Python Microservice Proxy Bridge with local direct Vertex AI fallback ──
  const cmoAgentUrl = process.env.CMO_AGENT_URL || 'http://localhost:8090';
  try {
    console.log(`[csm/repurpose] Attempting to proxy campaign derivation to Python service: ${cmoAgentUrl}/repurpose`);
    const pythonRes = await fetch(`${cmoAgentUrl}/repurpose`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        title: resolvedTitle,
        slug: resolvedSlug,
        content,
        category,
        youtubeScript,
        language,
      }),
      signal: AbortSignal.timeout(240000), // Repurposing is structured and can take longer
    });

    if (pythonRes.ok) {
      const data = await pythonRes.json();
      console.log('[csm/repurpose] Successfully received campaign structured data from Python microservice');
      return NextResponse.json(data);
    } else {
      console.warn(`[csm/repurpose] Python service returned HTTP status ${pythonRes.status}. Falling back to direct Vertex AI.`);
    }
  } catch (err) {
    console.warn('[csm/repurpose] Python agent service unreachable or timed out. Falling back to direct Vertex AI.', err);
  }

  // 1. Fetch Ecosystem Historical Memory
  const memory = await getEcosystemMemory(5, 10);
  const memoryContext = formatMemoryForPrompt(memory);

  const systemInstruction = `Você é o Arquiteto Sênior de Marketing e Criação de Conteúdo da plataforma educacional éozoré (Victor Zore).
Sua missão é atuar como uma agência pessoal completa de marketing, consumindo o artigo de blog recém-escrito e orquestrando o histórico prévio para derivar uma campanha omnicanal imersiva de uma semana inteira.

A persona do autor (Victor Zore):
- Líder Técnico em IA Generativa e ML, formado em Matemática na UFSCar.
- Tom de voz: Técnico, rigoroso, avesso a teorias genéricas de gestão e focado em ensinar o PORQUÊ (a matemática, lógica e intuição geométrica) antes do COMO (o código).

${memoryContext}

REGRAS DE MARKETING MULTI-STAGE:
1. GERAR VALOR REAL: Cada postagem (LinkedIn, Reels, Shorts, Carrosséis ou Stories) deve entregar conhecimento prático e real para o leitor (ex: um insight conceitual, uma fórmula rápida, uma provocação matemática).
2. CTA DIRETO E CLARO: No fechamento de cada peça, insira obrigatoriamente um Call-to-Action (CTA) conciso e natural direcionando o público a assistir ao vídeo de deep dive completo do YouTube publicado no início da semana.

REGRAS DE QUANTIDADE OBRIGATÓRIAS:
1. "linkedinPosts": Exatamente 2 opções focadas em divulgar o artigo e canalizar público para o YouTube.
2. "youtubeShorts": 2 a 3 roteiros rápidos verticais para Shorts de YouTube.
3. "reelsScripts": 3 a 4 roteiros de Reels para Instagram.
4. "carousels": 2 a 3 posts de carrossel slide-a-slide.
5. "imagePosts": 2 a 3 posts de Texto + Imagem para feeds sociais (contendo descrição detalhada do design da imagem de acompanhamento).
6. "storiesIdeas": 10 a 12 sugestões de Stories sequenciais.

Todos os itens gerados DEVEM receber a propriedade inicial "status": "em_revisao".`;

  const prompt = `ARTIGO DE BASE PARA A CAMPANHA:
TÍTULO: ${resolvedTitle}
SLUG: ${resolvedSlug}
CATEGORIA: ${category}
IDIOMA: ${language}

ROTEIRO DE VÍDEO DO YOUTUBE APROVADO:
${youtubeScript || 'Não fornecido (crie as chamadas focadas na pauta técnica geral)'}

CONTEÚDO DO ARTIGO:
${content.slice(0, 18000)}

Gere o plano editorial completo no schema JSON solicitado.`;

  const responseSchema = {
    type: 'OBJECT',
    properties: {
      linkedinPosts: {
        type: 'ARRAY',
        description: 'Exatamente 2 posts de LinkedIn de divulgação.',
        items: {
          type: 'OBJECT',
          properties: {
            id: { type: 'STRING' },
            hook: { type: 'STRING', description: 'Gancho inicial provocativo.' },
            copy: { type: 'STRING', description: 'Corpo completo do post.' },
            status: { type: 'STRING', description: 'Default: em_revisao' },
          },
          required: ['id', 'hook', 'copy', 'status'],
        },
      },

      youtubeShorts: {
        type: 'ARRAY',
        description: '2 a 3 roteiros para Shorts de YouTube.',
        items: {
          type: 'OBJECT',
          properties: {
            id: { type: 'STRING' },
            title: { type: 'STRING' },
            hook3s: { type: 'STRING', description: 'Fala rápida dos primeiros 3 segundos.' },
            script: { type: 'STRING', description: 'Roteiro falado completo para Shorts (30-60s).' },
            status: { type: 'STRING' },
          },
          required: ['id', 'title', 'hook3s', 'script', 'status'],
        },
      },
      reelsScripts: {
        type: 'ARRAY',
        description: '3 a 4 roteiros de Reels.',
        items: {
          type: 'OBJECT',
          properties: {
            id: { type: 'STRING' },
            title: { type: 'STRING' },
            hook3s: { type: 'STRING', description: 'Fala impactante dos primeiros 3 segundos.' },
            visualCue: { type: 'STRING', description: 'Sugestão visual na tela.' },
            script: { type: 'STRING', description: 'Roteiro falado completo (30-60 segundos).' },
            status: { type: 'STRING' },
          },
          required: ['id', 'title', 'hook3s', 'visualCue', 'script', 'status'],
        },
      },
      carousels: {
        type: 'ARRAY',
        description: '2 a 3 carrosseis para Instagram/Threads.',
        items: {
          type: 'OBJECT',
          properties: {
            id: { type: 'STRING' },
            title: { type: 'STRING' },
            caption: { type: 'STRING', description: 'Legenda do carrossel.' },
            status: { type: 'STRING' },
            slides: {
              type: 'ARRAY',
              items: {
                type: 'OBJECT',
                properties: {
                  slideNumber: { type: 'INTEGER' },
                  heading: { type: 'STRING' },
                  body: { type: 'STRING' },
                },
                required: ['slideNumber', 'heading', 'body'],
              },
            },
          },
          required: ['id', 'title', 'caption', 'slides', 'status'],
        },
      },
      imagePosts: {
        type: 'ARRAY',
        description: '2 a 3 posts de imagem e texto para feeds.',
        items: {
          type: 'OBJECT',
          properties: {
            id: { type: 'STRING' },
            title: { type: 'STRING' },
            imageDescription: { type: 'STRING', description: 'Descrição detalhada do design da imagem de acompanhamento.' },
            copy: { type: 'STRING', description: 'Texto que acompanha a imagem.' },
            status: { type: 'STRING' },
          },
          required: ['id', 'title', 'imageDescription', 'copy', 'status'],
        },
      },
      storiesIdeas: {
        type: 'ARRAY',
        description: '10 a 12 sugestões de Stories.',
        items: {
          type: 'OBJECT',
          properties: {
            id: { type: 'STRING' },
            day: { type: 'STRING' },
            angle: { type: 'STRING' },
            copy: { type: 'STRING' },
            interactiveElement: { type: 'STRING' },
            status: { type: 'STRING' },
          },
          required: ['id', 'day', 'angle', 'copy', 'status'],
        },
      },
    },
    required: ['linkedinPosts', 'youtubeShorts', 'reelsScripts', 'carousels', 'imagePosts', 'storiesIdeas'],
  };

  try {
    const resultJson = await generateContent({
      prompt,
      systemInstruction,
      responseSchema,
      temperature: 0.35,
    });

    let parsed: any;
    try {
      parsed = JSON.parse(resultJson);
    } catch (parseErr) {
      console.warn('[csm/repurpose] Strict JSON parse failed. Attempting dirty repair...', parseErr);
      const repaired = cleanAndRepairJson(resultJson);
      parsed = JSON.parse(repaired);
    }
    return NextResponse.json(parsed);
  } catch (error: unknown) {
    console.error('[csm/repurpose v2] Error:', error);
    const msg = error instanceof Error ? error.message : 'Repurpose generation failed';
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
