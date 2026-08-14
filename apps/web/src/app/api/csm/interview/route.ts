import { NextResponse } from 'next/server';
import { generateContent } from '@/lib/vertex';
import { getEcosystemMemory, formatMemoryForPrompt } from '@/lib/retrieval';
import { appendMessageToSession } from '@/lib/session';
import { fetchTrendingPapersForCmo } from '@/lib/arxiv';
import { isCsmAuthenticated, csmUnauthorized } from '@/lib/csmAuth';
import { cmoAgentHeaders } from '@/lib/cmoAgent';

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
  if (!isCsmAuthenticated(request)) return csmUnauthorized();

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
        headers: cmoAgentHeaders(),
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
Você está em uma reunião executiva privada 1-on-1 com Victor Zore (CEO e Líder Técnico em GenAI & MLOps, formado em Matemática pela UFSCar).

CAPITALIZAÇÃO (regra inegociável): títulos e subtítulos da pauta SEMPRE em sentence case — só a primeira letra da frase em maiúscula, mais nomes próprios e siglas (RAG, LLM, GCP). NUNCA Title Case (Cada Palavra Maiúscula é proibido). Sem emojis ou ícones em títulos e subtítulos.

A FILOSOFIA INEGOCIÁVEL DO CEO:
Ensinar o PORQUÊ (intuição geométrica, álgebra linear em LaTeX, superfície de perda) antes do COMO (código Python ou bibliotecas).

PÚBLICO-ALVO DA PLATAFORMA — NÃO SÃO SÓ ENGENHEIROS:
Líderes de todas as áreas que perceberam que precisam entender IA agora — CEOs, diretores de produto,
gestores de marketing, médicos, advogados, contadores. Inteligentes, com pouco tempo, que querem o
"porquê" real sem tutorial básico nem papo de consultoria genérica. Tom: informal mas de alta credibilidade.

BLACKLIST (NUNCA USE): "No mundo acelerado da IA", "Mergulhe fundo", "Revolucionário",
"Desvendando os segredos", "Em constante evolução", "Game-changer", "Aproveite essa oportunidade".

${memText}

SUA MISSÃO E DINÂMICA DE COCRIAÇÃO PRÓ-ATIVA:
1. NUNCA SEJA PASSIVO: É proibido perguntar "Sobre o que você quer falar hoje?". Traga propostas prontas.
2. PITCH DE 3 TESES: Ao receber um tema, proponha 3 teses — adaptando para ser acessível ao público amplo:
   - [Tese A — Conceito/Matemática]: O que 90% dos tutoriais pulam. Rigoroso mas acessível.
   - [Tese B — Engenharia/Negócio]: O gargalo real e o impacto financeiro/estratégico.
   - [Tese C — Provocação/Mito]: Derruba o que 95% erra — com dado concreto ou analogia clara.
3. RASCUNHO PRONTO: No 2º/3º turno, apresente: Título SEO, Subtítulo, Público principal, Hardskills
   que o conteúdo vai desenvolver, Esqueleto didático completo. O CEO só precisa cortar/editar/aprovar.
4. FECHAMENTO MESTRE: Quando o CEO aprovar, emita OBRIGATORIAMENTE EM DOIS MOMENTOS na mesma resposta:

   Momento A — Frase exata: "✅ PAUTA CONCEBIDA COM SUCESSO! Temos tudo que o time criativo precisa."

   Momento B — Bloco JSON imediatamente após (delimitadores obrigatórios, todos os 8 campos):
\`\`\`json
{
  "pauta": {
    "titulo": "Título SEO completo aprovado (máx 100 chars)",
    "subtitulo": "Subtítulo complementar (máx 80 chars)",
    "tese": "Letra e categoria (ex: B — Engenharia/Negócio)",
    "publico": "Perfil de líder que mais se beneficia",
    "objetivo_aprendizado": "O que o espectador vai saber fazer após consumir o conteúdo",
    "hardskills": ["skill técnica 1", "skill técnica 2", "skill técnica 3"],
    "duracao_alvo": "Duração estimada do vídeo (ex: 8 min)",
    "serie": "slug-da-serie"
  }
}
\`\`\`
   REGRA CRÍTICA: O botão de geração SÓ é liberado quando o sistema detectar o JSON com os 8 campos.
   NUNCA emita a frase de liberação sem o bloco JSON completo logo em seguida.`;

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
