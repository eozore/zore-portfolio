import { NextResponse } from 'next/server';
import { getVertexAccessToken, getVertexStreamEndpoint } from '@/lib/vertex';

export const dynamic = 'force-dynamic';
// Allow up to 10 minutes for YouTube script generation via the AGY pipeline
export const maxDuration = 600;

interface YouTubeRequest {
  title: string;
  content: string;
  category: string;
  language?: string;
  sessionId?: string;
}

const FALLBACK_YOUTUBE_INSTRUCTION = `Você é o YouTube Writing Agent do ecossistema éozoré. Sua missão é ler o artigo técnico do blog e escrever o roteiro completo de um vídeo didático aprofundado para o canal do YouTube de Victor Zore.

A persona do autor (Victor Zore):
- Líder Técnico em IA Generativa e Machine Learning. Graduado em Matemática na UFSCar.
- Tom de voz: Rigoroso, direto e professoral. Prioriza explicar o PORQUÊ (a matemática, as equações em LaTeX, intuição e conceitos abstratos) antes de mostrar o COMO (o código). Evite clichês vazios de coachs de internet.

Estrutura Obrigatória do Roteiro (com blocos de fala e dicas de tela):
1. HOOK (Gancho - primeiros 30 segundos): Uma provocação conceitual forte que chama a atenção do público sobre o problema matemático ou arquitetural que resolveremos.
2. TEORIA PROFUNDA (O Porquê): Explicação didática de alto nível sobre a lógica matemática ou algoritmos envolvidos (use equações matemáticas LaTeX quando necessário).
3. PRÁTICA E CÓDIGO (O Como): Explicação da implementação do código.
4. CTA (Call to Action): Chame o público para se inscrever no canal, comentar e ler o artigo de blog completo publicado em eozore.com para acessar as notas detalhadas.

Utilize o formato de marcação Markdown. Coloque indicações visuais/dicas de edição de vídeo em blocos do tipo blockquote, ex:
> [CENA: Victor falando para a câmera com fundo dark desfocado]`;

export async function POST(request: Request): Promise<Response> {
  const projectId = process.env.FIREBASE_PROJECT_ID;
  if (!projectId) {
    return NextResponse.json(
      { error: 'FIREBASE_PROJECT_ID not set' },
      { status: 500 }
    );
  }

  let body: YouTubeRequest;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 });
  }

  const { title, content, category, language = 'pt-BR', sessionId } = body;

  if (!content) {
    return NextResponse.json({ error: 'content is required' }, { status: 400 });
  }

  const resolvedTitle = title || 'Roteiro de Video';

  const cmoAgentUrl = process.env.CMO_AGENT_URL || 'http://localhost:8090';

  try {
    console.log(`[csm/youtube] Proxying to Python service: ${cmoAgentUrl}/youtube`);
    const pythonRes = await fetch(`${cmoAgentUrl}/youtube`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        title: resolvedTitle,
        content,
        category,
        language,
        sessionId,
      }),
      // No AbortSignal — let the YouTube script pipeline complete without timeout
    });

    if (pythonRes.ok && pythonRes.body) {
      console.log('[csm/youtube] Proxying stream from Python agent...');
      return new Response(pythonRes.body, {
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'X-Accel-Buffering': 'no',
        },
      });
    } else {
      console.warn(`[csm/youtube] Python service returned HTTP status ${pythonRes.status}. Fallback direct...`);
    }
  } catch (err) {
    console.warn('[csm/youtube] Python service unreachable/timeout. Fallback direct...', err);
  }

  // ── Vertex AI Fallback Direct Stream ──
  const userPrompt = `Escreva o roteiro completo para o YouTube com base neste artigo:\n\nTÍTULO: ${resolvedTitle}\nCATEGORIA: ${category}\n\nCONTEÚDO DO ARTIGO:\n${content}`;

  const vertexPayload = {
    contents: [
      {
        role: 'user',
        parts: [{ text: userPrompt }],
      },
    ],
    systemInstruction: {
      parts: [{ text: FALLBACK_YOUTUBE_INSTRUCTION }],
    },
    generationConfig: {
      temperature: 0.5,
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
          console.error('[csm/youtube] Vertex AI error:', vertexRes.status, errText);
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
                send({ type: 'content', chunk: text });
              }
            } catch {
              // Ignore parse errors on incomplete chunk lines
            }
          }
        }
        controller.enqueue(encoder.encode('data: [DONE]\n\n'));
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Internal streaming error';
        console.error('[csm/youtube] Error:', err);
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
