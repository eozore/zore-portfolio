/**
 * useStudio.ts — Estado do fluxo, vindo do grafo.
 *
 * O grafo é a fonte de verdade: a UI não guarda cópia do artigo nem do plano,
 * ela reflete `/graph/state`. Isso resolve o problema que o CSM antigo tinha —
 * `draft` no cliente divergindo do Firestore, e o usuário perdendo trabalho ao
 * recarregar a página.
 *
 * O polling só roda quando há trabalho em curso. Parado num gate, a tela fica
 * quieta: pedir estado a cada 8s enquanto alguém lê um artigo é gastar
 * requisição para receber a mesma resposta.
 */
'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

export type Fase =
  | 'planejamento' | 'artigo' | 'aguardando_aprovacao_artigo'
  | 'video' | 'aguardando_aprovacao_video'
  | 'social' | 'concluido' | 'erro';

export interface ErroNo { no: string; mensagem: string; fatal: boolean }

/** Progresso da produção do vídeo, vindo de /api/csm/pipeline-status. */
export interface Producao {
  projectId?: string | null;
  etapas: { id: string; rotulo: string; status: string; detalhe?: string }[];
  videoPronto: boolean;
  youtubeUrl?: string | null;
  duracaoS?: number | null;
  /** Status do corte vertical: ausente = nunca pedido. */
  corteVertical?: string | null;
  /** Peças já na social_queue para esta sessão. Fonte de verdade do agendamento. */
  naFila: number;
}

/** Resultado de mandar o plano social para a fila de publicação. */
export interface Agendamento {
  enfileirados: number;
  total: number;
  falhas: string[];
}

export interface EstadoStudio {
  fase: Fase;
  aguardando: string[];
  tema?: string;
  pauta?: Record<string, unknown>;
  artigo?: { titulo?: string; markdown?: string; slug?: string; resumo?: string; url?: string };
  video?: {
    titulo?: string;
    manifesto?: Record<string, unknown>;
    slides?: number;
    projectId?: string;
    url?: string;
  };
  planoSocial?: Record<string, unknown>;
  trilha: string[];
  erros: ErroNo[];
}

/** Fases em que o agente está trabalhando — só aí o polling faz sentido. */
const TRABALHANDO: Fase[] = ['planejamento', 'artigo', 'video', 'social'];

const POLL_MS = 6000;

export function useStudio(sessionId: string) {
  const [estado, setEstado]   = useState<EstadoStudio | null>(null);
  const [erro, setErro]       = useState<string>('');
  const [ocupado, setOcupado] = useState(false);
  const [carregando, setCarregando] = useState(true);
  const [producao, setProducao] = useState<Producao | null>(null);
  /** 'draft' | 'published' | null — status do artigo no blog. */
  const [statusArtigo, setStatusArtigo] = useState<string | null>(null);
  const [agendamento, setAgendamento] = useState<Agendamento | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const buscar = useCallback(async (silencioso = false) => {
    if (!sessionId) return;
    if (!silencioso) setCarregando(true);
    try {
      const res = await fetch(`/api/csm/studio?sessionId=${encodeURIComponent(sessionId)}`);
      if (res.status === 404) { setEstado(null); return; }   // ainda não começou
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.error || `HTTP ${res.status}`);
      setEstado(data as EstadoStudio);
      setErro('');

      // A produção do vídeo roda FORA do grafo (Cloud Run Jobs encadeados por
      // Pub/Sub). O grafo segue para o plano social enquanto TTS, avatar e
      // edição acontecem — então o progresso vem de outra rota.
      try {
        // Pelo id do projeto quando o grafo já o tem. A busca por sessão é o
        // fallback, e ela é traiçoeira: um session_id reaproveitado casa com
        // projetos de semanas anteriores e a tela mostra o vídeo errado como
        // se fosse o desta rodada — foi o que aconteceu em 24/08.
        // O sessionId vai SEMPRE, mesmo quando há projectId: é por ele que o
        // pipeline-status consulta a social_queue. Mandar só o projectId
        // deixava `scheduledItems` vazio, `naFila` em 0, e o botão "Agendar a
        // semana" nunca virava o selo "N na fila" — sem feedback nenhum e com
        // risco de agendar a mesma semana duas vezes.
        //
        // O projectId continua tendo precedência para achar o PROJETO; ele é
        // que evita casar com um vídeo de outra semana por session_id.
        const projetoDoGrafo = (data as EstadoStudio)?.video?.projectId;
        const alvo = [
          projetoDoGrafo ? `projectId=${encodeURIComponent(projetoDoGrafo)}` : '',
          `sessionId=${encodeURIComponent(sessionId)}`,
        ].filter(Boolean).join('&');
        const pr = await fetch(`/api/csm/pipeline-status?${alvo}`);
        if (pr.ok) {
          const pd = await pr.json();
          // As chaves têm que ser as MESMAS que os jobs gravam em
          // content_projects.stages. O backend escreve `editor`; aqui estava
          // `video_editor`, então a etapa era filtrada fora e a Edição nunca
          // aparecia. Pior: o polling abaixo só continua enquanto alguma
          // etapa DESTA lista estiver ativa — com `editor` de fora, a tela
          // congelava justamente quando a edição começava.
          //
          // `publisher` É escrito, por caminho de campo
          // (publisher_job/job.py:679 grava `stages.publisher.status`), e não
          // por `update_stage` — foi por isso que um grep por `update_stage(`
          // não o encontrou e ele chegou a sair desta lista.
          const ROTULOS: Record<string, string> = {
            tts: 'Voz', avatar: 'Avatar', editor: 'Edição',
            publisher: 'Publicação', vertical_cut: 'Corte vertical',
          };
          const etapas = Object.entries(pd.stages ?? {})
            .filter(([id]) => id in ROTULOS)
            .map(([id, v]) => ({
              id, rotulo: ROTULOS[id],
              status: String((v as Record<string, unknown>).status ?? 'waiting'),
              detalhe: (v as Record<string, unknown>).detail as string | undefined,
            }));
          setProducao({
            projectId: pd.projectId,
            etapas,
            videoPronto: Boolean(pd.video?.horizontalReady),
            youtubeUrl: pd.video?.youtubeUrl,
            duracaoS: pd.video?.durationSeconds,
            corteVertical: (pd.stages?.vertical_cut as { status?: string } | undefined)?.status
              ?? null,
            naFila: Array.isArray(pd.scheduledItems) ? pd.scheduledItems.length : 0,
          });
        }
      } catch { /* produção é informação extra; o fluxo não depende dela */ }

      // Status do artigo no blog. O grafo guarda a URL, não se o post está
      // visível — e sem isso a tela não sabe se ainda falta publicar.
      const slugArtigo = (data as EstadoStudio)?.artigo?.slug;
      if (slugArtigo) {
        try {
          const ar = await fetch(
            `/api/csm/article-publish?slug=${encodeURIComponent(slugArtigo)}`,
          );
          if (ar.ok) setStatusArtigo((await ar.json()).status ?? null);
        } catch { /* idem */ }
      }
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    } finally {
      setCarregando(false);
    }
  }, [sessionId]);

  // Polling condicional: só enquanto um nó está rodando.
  //
  // A condição olha as etapas, não `videoPronto`: o corte vertical roda DEPOIS
  // que o vídeo longo ficou pronto, e amarrar o polling a `!videoPronto`
  // congelava a tela justamente enquanto o Reel era produzido.
  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    const produzindo = producao !== null &&
      producao.etapas.some((e) => ['running', 'pending_callback', 'queued'].includes(e.status));
    if (!estado || (!TRABALHANDO.includes(estado.fase) && !produzindo)) return;
    timer.current = setTimeout(() => void buscar(true), POLL_MS);
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [estado, producao, buscar]);

  useEffect(() => { void buscar(); }, [buscar]);

  const iniciar = useCallback(async (tema: string, contexto: string) => {
    setOcupado(true); setErro('');
    try {
      const res = await fetch('/api/csm/studio', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'start', sessionId, tema, contexto }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      await buscar(true);
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    } finally {
      setOcupado(false);
    }
  }, [sessionId, buscar]);

  const decidir = useCallback(async (
    gate: 'artigo' | 'video',
    decisao: 'aprovado' | 'ajustar' | 'rejeitado',
    comentario = '',
  ) => {
    setOcupado(true); setErro('');
    try {
      const res = await fetch('/api/csm/studio', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'approve', sessionId, gate, decisao, comentario }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      await buscar(true);
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    } finally {
      setOcupado(false);
    }
  }, [sessionId, buscar]);

  /**
   * Manda o plano social para a fila de publicação.
   *
   * Renderiza carrossel e stories em PNG antes de gravar, então é lento —
   * dezenas de segundos para uma semana inteira. `ocupado` segura o botão.
   */
  const agendar = useCallback(async () => {
    setOcupado(true); setErro('');
    try {
      const res = await fetch('/api/csm/studio', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'agendar', sessionId }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.error || `HTTP ${res.status}`);
      setAgendamento(data as Agendamento);
      await buscar(true);
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    } finally {
      setOcupado(false);
    }
  }, [sessionId, buscar]);

  /**
   * Pede o Reel/Short recortado do vídeo longo já publicado.
   *
   * O gate real fica no servidor (o vídeo tem que existir e ter clipes por
   * segmento); aqui o botão só evita o clique óbvio sem projeto.
   */
  /**
   * Promove o artigo de rascunho para publicado.
   *
   * O gate do artigo grava como rascunho de propósito — a URL passa a existir
   * para as peças sociais, mas o post não aparece no blog. Esta é a outra
   * metade dessa decisão, que faltava: sem ela o artigo ficava preso e a
   * semana de posts apontava para uma página invisível ao visitante.
   */
  const publicarArtigo = useCallback(async () => {
    const slug = estado?.artigo?.slug;
    if (!slug) return;
    setOcupado(true); setErro('');
    try {
      const res = await fetch('/api/csm/article-publish', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slug }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      setStatusArtigo('published');
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    } finally {
      setOcupado(false);
    }
  }, [estado]);

  const derivarVertical = useCallback(async () => {
    const projectId = producao?.projectId;
    if (!projectId) return;
    setOcupado(true); setErro('');
    try {
      const res = await fetch('/api/csm/derive-vertical', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ projectId }),
      });
      const data = await res.json();
      if (!res.ok && res.status !== 202) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }
      await buscar(true);
    } catch (e) {
      setErro(e instanceof Error ? e.message : String(e));
    } finally {
      setOcupado(false);
    }
  }, [producao, buscar]);

  return { estado, producao, agendamento, statusArtigo, erro, ocupado, carregando,
           iniciar, decidir, agendar, derivarVertical, publicarArtigo,
           recarregar: () => buscar(true) };
}

// ── Derivações que a UI usa para decidir o que mostrar ───────────────────────

export type StatusPasso = 'pendente' | 'fazendo' | 'seu_turno' | 'feito' | 'erro';

export interface Passo {
  id: 'tema' | 'artigo' | 'video' | 'social';
  rotulo: string;
  status: StatusPasso;
}

/**
 * Traduz a fase do grafo nos quatro passos da jornada.
 *
 * `seu_turno` é o estado mais importante da interface: é o único em que a
 * plataforma está parada esperando uma pessoa. Ele precisa ser visualmente
 * distinto de "fazendo" — confundir os dois faz o usuário esperar por algo
 * que nunca vai acontecer sozinho.
 */
export function passosDaJornada(estado: EstadoStudio | null): Passo[] {
  const fase = estado?.fase;
  const temErroFatal = (estado?.erros || []).some((e) => e.fatal);

  const passo = (
    id: Passo['id'], rotulo: string, feitoApos: Fase[], fazendoEm: Fase[], gateEm?: Fase,
  ): Passo => {
    if (!fase) return { id, rotulo, status: 'pendente' };
    if (temErroFatal && fazendoEm.includes(fase)) return { id, rotulo, status: 'erro' };
    if (gateEm && fase === gateEm) return { id, rotulo, status: 'seu_turno' };
    if (fazendoEm.includes(fase)) return { id, rotulo, status: 'fazendo' };
    if (feitoApos.includes(fase)) return { id, rotulo, status: 'feito' };
    return { id, rotulo, status: 'pendente' };
  };

  const depoisDoTema: Fase[] = [
    'artigo', 'aguardando_aprovacao_artigo', 'video',
    'aguardando_aprovacao_video', 'social', 'concluido',
  ];
  const depoisDoArtigo: Fase[] = ['video', 'aguardando_aprovacao_video', 'social', 'concluido'];
  const depoisDoVideo: Fase[]  = ['social', 'concluido'];

  return [
    passo('tema',   'Tema',   depoisDoTema,   ['planejamento']),
    passo('artigo', 'Artigo', depoisDoArtigo, ['artigo'], 'aguardando_aprovacao_artigo'),
    passo('video',  'Vídeo',  depoisDoVideo,  ['video'],  'aguardando_aprovacao_video'),
    passo('social', 'Social', ['concluido'],  ['social']),
  ];
}

/** A frase única que responde "o que está acontecendo agora". */
export function resumoDaFase(estado: EstadoStudio | null): { titulo: string; sub: string } {
  if (!estado) {
    return {
      titulo: 'Vamos começar',
      sub: 'Diga o tema da semana. O time cuida do artigo, do vídeo e das redes.',
    };
  }
  switch (estado.fase) {
    case 'planejamento':
      return { titulo: 'Fechando a pauta', sub: 'Definindo título, tese e o ângulo do vídeo.' };
    case 'artigo':
      return { titulo: 'Escrevendo o artigo', sub: 'Pesquisando e redigindo. Isso leva alguns minutos.' };
    case 'aguardando_aprovacao_artigo':
      return { titulo: 'Sua vez: revise o artigo', sub: 'Nada avança até você decidir.' };
    case 'video':
      return { titulo: 'Montando o vídeo', sub: 'Roteiro segmentado e ilustrações.' };
    case 'aguardando_aprovacao_video':
      return { titulo: 'Sua vez: revise o vídeo', sub: 'Confira o roteiro e as ilustrações antes de produzir.' };
    case 'social':
      return { titulo: 'Planejando as redes', sub: 'Montando as peças que levam ao vídeo.' };
    case 'concluido':
      return { titulo: 'Pacote pronto', sub: 'Revise o que vai ao ar e publique.' };
    case 'erro':
      return { titulo: 'Algo travou', sub: 'Veja o motivo abaixo.' };
  }
}
