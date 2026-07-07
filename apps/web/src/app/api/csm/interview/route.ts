import { NextResponse } from 'next/server';
import { generateContent } from '@/lib/vertex';
import { getEcosystemMemory, formatMemoryForPrompt } from '@/lib/retrieval';
import { appendMessageToSession } from '@/lib/session';
import { fetchTrendingPapersForCmo } from '@/lib/arxiv';

interface ChatMessage {
  role: 'user' | 'model';
  text: string;
}

interface InterviewRequest {
  messages: ChatMessage[];
  sessionId?: string;
  category?: string;
}

export async function POST(request: Request): Promise<Response> {
  let body: InterviewRequest;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const { messages = [], sessionId, category = 'ml' } = body;

  const cmoAgentUrl = process.env.CMO_AGENT_URL;
  if (cmoAgentUrl) {
    try {
      console.log(`[interview] Forwarding request to Python CMO Agent: ${cmoAgentUrl}/interview`);
      const agentRes = await fetch(`${cmoAgentUrl}/interview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages, sessionId, category }),
      });

      if (agentRes.ok) {
        const data = await agentRes.json();
        if (sessionId) {
          const lastUserMsg = messages[messages.length - 1];
          (async () => {
            if (lastUserMsg?.role === 'user') {
              await appendMessageToSession(sessionId, {
                role: 'user',
                text: lastUserMsg.text,
                timestamp: Date.now(),
              });
            }
            await appendMessageToSession(sessionId, {
              role: 'model',
              text: data.text,
              timestamp: Date.now(),
            });
          })().catch(console.error);
        }
        return NextResponse.json(data);
      } else {
        const errText = await agentRes.text();
        console.error(`[interview] Python Agent error (${agentRes.status}):`, errText);
      }
    } catch (err) {
      console.error('[interview] Failed to connect to Python Agent, falling back to Next.js handler:', err);
    }
  }

  const isFirstTurn = messages.length === 0;

  // Fetch ecosystem memory and, on the first turn, arXiv trending papers in parallel
  const [memory, arxivContext] = await Promise.all([
    getEcosystemMemory(4, 8),
    isFirstTurn ? fetchTrendingPapersForCmo(2) : Promise.resolve(''),
  ]);

  const memText = formatMemoryForPrompt(memory);

  const systemInstruction = `Você é o Diretor de Marketing (CMO AI) e Parceiro de Cocriação Visionária da plataforma éozoré (eozore.com).
Você está em uma reunião executiva privada de concepção criativa 1-on-1 com Victor Zore (CEO e Líder Técnico em GenAI & MLOps, formado em Matemática pela UFSCar).

A FILOSOFIA INEGOCIÁVEL DO CEO:
Ensinar o PORQUÊ (intuição geométrica, álgebra linear em LaTeX, superfície de perda) antes do COMO (código Python ou bibliotecas).

PREFERÊNCIAS E TOM DA PLATAFORMA (Memória Institucional):
- Tom: Sóbrio, analítico, autoridade técnica indiscutível. Nunca seja eufórico ou piegas.
- Blacklist de clichês (NUNCA USE): "No mundo acelerado da IA", "Mergulhe fundo", "Revolucionário", "Desvendando os segredos", "Em constante evolução".
- Público-Alvo: Staff Engineers, Cloud Architects GCP, Tech Leads e Cientistas Sênior.

${memText}

SUA MISSÃO E DINÂMICA DE COCRIAÇÃO PRÓ-ATIVA (INVERSÃO DE PAPEL):
1. NUNCA SEJA UM ENTREVISTADOR PASSIVO: É estritamente proibido fazer perguntas abertas preguiçosas como "Sobre o que você quer falar hoje?" ou "Qual o objetivo desse texto?". O CEO não tem tempo para inventar tudo sozinho.
2. COCRIAÇÃO ATIVA (PITCH DE 3 TESES): Sempre que o CEO trouxer um tema ou palavra (ex: "LoRA", "Agentes", "RAG"), você deve IMEDIATAMENTE colocar na mesa 3 propostas concretas, ousadas e contrárias ao senso comum:
   - [Tese A - Matemática/Geometria]: Focando na álgebra linear oculta.
   - [Tese B - Engenharia/GCP]: Focando em gargalos reais de memória, latência ou custo.
   - [Tese C - Provocação/Mito]: Derrubando o jeito errado que 95% dos tutoriais ensinam.
3. ENTREGUE RASCUNHOS PRONTOS PARA CORTE: No 2º ou 3º turno, apresente proativamente a sugestão de Título SEO, Subtítulo e o esqueleto didático completo (Introdução didática -> Teoria -> Código), pedindo para o CEO apenas CORTAR, EDITAR ou APROVAR a sua proposta.
4. FECHAMENTO MESTRE: Quando o CEO disser "Gostei da tese 2" ou aprovar o esboço, celebre a concepção e emita OBRIGATORIAMENTE a frase exata de liberação do sistema:
"✅ PAUTA CONCEBIDA COM SUCESSO! Temos tudo que o redator técnico precisa. Clique no botão criativo abaixo para acionar a redação."`;

  let prompt = '';

  if (isFirstTurn) {
    const arxivSection = arxivContext
      ? `\n\nINTELIGÊNCIA DE MERCADO (papers publicados nas últimas horas no arXiv):\n${arxivContext}\n\nUse esses papers para propor teses de artigo que conectem teoria de ponta com a prática de engenharia.`
      : '';

    prompt = `A reunião executiva de pauta desta semana acabou de começar.${arxivSection}

Saúde Victor Zore com sobriedade técnica, cite rapidamente 1 tema recente do histórico do blog para dar contexto, e coloque proativamente na mesa 3 teses concretas e ousadas (baseadas nos papers acima ou em tendências que você identificou) para cocriarmos o artigo desta semana.`;
  } else {
    const lastUserMsg = messages[messages.length - 1];

    prompt =
      `TRANSCRIÇÃO DO DIÁLOGO ATÉ AGORA:\n` +
      messages
        .map((m) => `${m.role === 'user' ? 'CEO (Victor)' : 'CMO AI'}: ${m.text}`)
        .join('\n\n') +
      `\n\nResponda como o CMO AI no próximo turno (aplicando cocriação pró-ativa com teses ousadas e esboços prontos para edição do CEO).`;

    // Persist the latest user message to Firestore asynchronously (fire-and-forget)
    if (sessionId && lastUserMsg?.role === 'user') {
      appendMessageToSession(sessionId, {
        role: 'user',
        text: lastUserMsg.text,
        timestamp: Date.now(),
      }).catch(console.error);
    }
  }

  try {
    const responseText = await generateContent({
      prompt,
      systemInstruction,
      temperature: 0.7,
    });

    // Persist the model response to Firestore asynchronously (fire-and-forget)
    if (sessionId) {
      appendMessageToSession(sessionId, {
        role: 'model',
        text: responseText,
        timestamp: Date.now(),
      }).catch(console.error);
    }

    return NextResponse.json({ text: responseText });
  } catch (error: unknown) {
    console.error('[csm/interview] Error:', error);
    const msg = error instanceof Error ? error.message : 'Interview chat failed';
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
