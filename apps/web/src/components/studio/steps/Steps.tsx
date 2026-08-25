/**
 * Steps.tsx — As quatro telas da jornada.
 *
 * Uma regra de layout acima de tudo: em cada momento existe UMA ação
 * possível, e ela está visível sem rolar. O CSM antigo espalhava a decisão
 * em abas travadas com cadeado, e o usuário precisava adivinhar qual delas
 * queria alguma coisa dele.
 */
'use client';

import { useState } from 'react';
import {
  Badge, Button, Card, Empty, Eyebrow, Notice, SectionTitle, Working, cx,
} from '../ui/primitives';
import { Markdown } from '../ui/Markdown';
import {
  CarrosselPreview, LinkedInPreview, StoryPreview, ThreadsPreview,
  YouTubeCommunityPreview,
} from '../previews/SocialPreviews';
import type { Agendamento, EstadoStudio, Producao } from '../useStudio';

// ── 1. Tema ──────────────────────────────────────────────────────────────────

export function PassoTema({
  onIniciar, ocupado,
}: { onIniciar: (tema: string, contexto: string) => void; ocupado: boolean }) {
  const [tema, setTema] = useState('');
  const [contexto, setContexto] = useState('');
  const podeIniciar = tema.trim().length >= 8;

  return (
    <Card>
      <Eyebrow>passo 1 de 4</Eyebrow>
      <SectionTitle hint="Descreva o assunto como você explicaria para um colega. O time fecha a pauta, escreve o artigo, monta o vídeo e planeja as redes — pausando duas vezes para você aprovar.">
        Qual é o tema desta semana?
      </SectionTitle>

      <textarea
        value={tema}
        onChange={(e) => setTema(e.target.value)}
        rows={3}
        placeholder="Ex: por que testes A/B continuam necessários mesmo com IA generativa"
        className="w-full resize-none rounded-xl border border-black/10 p-3.5 text-[14px] leading-relaxed text-[#1e1e1e] placeholder:text-[#a8a8a8] focus:border-[#e67e22]/50 focus:outline-none"
      />

      <details className="mt-3 group">
        <summary className="cursor-pointer list-none text-[13px] font-medium text-[#6b6b6b] hover:text-[#1e1e1e]">
          + Contexto adicional (opcional)
        </summary>
        <textarea
          value={contexto}
          onChange={(e) => setContexto(e.target.value)}
          rows={3}
          placeholder="Dados que você quer citar, um ângulo específico, algo a evitar…"
          className="mt-2 w-full resize-none rounded-xl border border-black/10 p-3.5 text-[13px] leading-relaxed focus:border-[#e67e22]/50 focus:outline-none"
        />
      </details>

      <div className="mt-5 flex items-center gap-3">
        <Button onClick={() => onIniciar(tema, contexto)} disabled={!podeIniciar} loading={ocupado}>
          {ocupado ? 'Começando…' : 'Começar'}
        </Button>
        {!podeIniciar && tema.length > 0 && (
          <span className="text-[12px] text-[#8a8a8a]">Descreva um pouco mais o tema.</span>
        )}
      </div>
    </Card>
  );
}

// ── Gate: o componente mais importante da interface ──────────────────────────

function Gate({
  titulo, aviso, onDecidir, ocupado, children,
}: {
  titulo: string;
  aviso: string;
  onDecidir: (d: 'aprovado' | 'ajustar' | 'rejeitado', c: string) => void;
  ocupado: boolean;
  children: React.ReactNode;
}) {
  const [modo, setModo] = useState<null | 'ajustar' | 'rejeitar'>(null);
  const [comentario, setComentario] = useState('');

  return (
    <div className="space-y-4">
      {children}

      {/* Barra de decisão fixa no rodapé: a ação não pode depender de rolar
          até o fim de um artigo de 7.000 caracteres. */}
      <div className="sticky bottom-0 -mx-1 rounded-2xl border border-[#e67e22]/30 bg-white/95 p-5 shadow-lg backdrop-blur">
        <p className="text-[14px] font-bold text-[#1e1e1e]">{titulo}</p>
        <p className="mt-1 text-[13px] text-[#6b6b6b]">{aviso}</p>

        {modo && (
          <textarea
            value={comentario}
            onChange={(e) => setComentario(e.target.value)}
            rows={2}
            autoFocus
            placeholder={modo === 'ajustar'
              ? 'O que precisa mudar? O agente refaz com essa crítica — e ela também entra na memória dele.'
              : 'Por que está descartando? Fica registrado para as próximas gerações.'}
            className="mt-3 w-full resize-none rounded-lg border border-black/10 p-3 text-[13px] focus:border-[#e67e22]/50 focus:outline-none"
          />
        )}

        <div className="mt-4 flex flex-wrap gap-2">
          {!modo && (
            <>
              <Button onClick={() => onDecidir('aprovado', '')} loading={ocupado}>
                Aprovar e seguir
              </Button>
              <Button variant="secondary" onClick={() => setModo('ajustar')}>
                Pedir ajuste
              </Button>
              <Button variant="ghost" onClick={() => setModo('rejeitar')}>
                Descartar
              </Button>
            </>
          )}
          {modo && (
            <>
              <Button
                variant={modo === 'rejeitar' ? 'danger' : 'primary'}
                loading={ocupado}
                disabled={comentario.trim().length < 4}
                onClick={() => onDecidir(modo === 'ajustar' ? 'ajustar' : 'rejeitado', comentario)}
              >
                {modo === 'ajustar' ? 'Refazer com esta crítica' : 'Confirmar descarte'}
              </Button>
              <Button variant="ghost" onClick={() => { setModo(null); setComentario(''); }}>
                Voltar
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── 2. Artigo ────────────────────────────────────────────────────────────────

export function PassoArtigo({
  estado, onDecidir, ocupado,
}: {
  estado: EstadoStudio;
  onDecidir: (d: 'aprovado' | 'ajustar' | 'rejeitado', c: string) => void;
  ocupado: boolean;
}) {
  const md = estado.artigo?.markdown || '';
  const palavras = md.split(/\s+/).filter(Boolean).length;

  return (
    <Gate
      titulo="Aprovar este artigo?"
      aviso="Aprovar libera a produção do vídeo, que é a etapa que consome crédito."
      onDecidir={onDecidir}
      ocupado={ocupado}
    >
      <Card>
        <Eyebrow>passo 2 de 4 · artigo</Eyebrow>
        <h2 className="text-xl font-bold leading-tight tracking-tight text-[#1e1e1e]">
          {estado.artigo?.titulo}
        </h2>
        {!!estado.artigo?.resumo && (
          <p className="mt-2 text-[13.5px] leading-relaxed text-[#4a4a4a]">
            {estado.artigo.resumo}
          </p>
        )}

        {/* Metadados como metadados. Antes vinham dentro do corpo do artigo,
            em frontmatter YAML que o renderizador cuspia como um parágrafo
            com os nomes dos campos no meio da prosa. */}
        <dl className="mt-4 flex flex-wrap gap-x-6 gap-y-2 border-t border-black/[0.06] pt-4">
          {[
            ['Extensão', `${palavras} palavras`],
            ['Leitura', `~${Math.max(1, Math.round(palavras / 220))} min`],
            ['Endereço', estado.artigo?.slug ? `/${estado.artigo.slug}` : '—'],
          ].map(([rotulo, valor]) => (
            <div key={rotulo}>
              <dt className="font-mono text-[9.5px] uppercase tracking-[0.14em] text-[#a8a8a8]">
                {rotulo}
              </dt>
              <dd className="mt-0.5 text-[13px] font-medium text-[#1e1e1e]">{valor}</dd>
            </div>
          ))}
        </dl>
      </Card>

      <Card>
        <article className="max-w-[68ch]">
          <Markdown>{md}</Markdown>
        </article>
      </Card>
    </Gate>
  );
}

// ── 3. Vídeo ─────────────────────────────────────────────────────────────────

export function PassoVideo({
  estado, onDecidir, ocupado,
}: {
  estado: EstadoStudio;
  onDecidir: (d: 'aprovado' | 'ajustar' | 'rejeitado', c: string) => void;
  ocupado: boolean;
}) {
  const manifesto = (estado.video?.manifesto || {}) as Record<string, any>;
  const segmentos: Record<string, any>[] = manifesto?.youtube?.segments || [];
  const avatar = segmentos.filter((s) => (s.kind || (s.slide ? 'slide' : 'avatar')) === 'avatar');
  const durTotal = segmentos.reduce((a, s) => a + (s.min_duration_s || 0), 0);
  const durAvatar = avatar.reduce((a, s) => a + (s.min_duration_s || 0), 0);
  const share = durTotal ? Math.round((durAvatar / durTotal) * 100) : 0;

  // O corte vertical (Reel/Short) é derivado deste mesmo vídeo — aponta para
  // segmentos daqui, não tem roteiro próprio. Fica invisível se a tela só
  // mostra manifesto.youtube; é o mesmo manifesto que já carrega os dois.
  const corteVertical: Record<string, any>[] = manifesto?.vertical_cut?.segments || [];
  const durVertical = corteVertical.reduce((a, s) => {
    const origem = segmentos.find((seg) => seg.id === s.source);
    return a + (origem?.min_duration_s || 0);
  }, 0);

  return (
    <Gate
      titulo="Aprovar este roteiro?"
      aviso="Aprovar dispara a produção: voz, avatar e edição. É aqui que o crédito é gasto."
      onDecidir={onDecidir}
      ocupado={ocupado}
    >
      <Card>
        <Eyebrow>passo 3 de 4 · vídeo</Eyebrow>
        <h2 className="text-lg font-bold tracking-tight text-[#1e1e1e]">{estado.video?.titulo}</h2>
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            ['Duração', `${Math.round(durTotal / 60)} min`],
            ['Segmentos', String(segmentos.length)],
            ['Avatar', `${share}%`],
            ['Ilustrações', String(estado.video?.slides ?? 0)],
          ].map(([r, v]) => (
            <div key={r} className="rounded-xl bg-black/[0.03] px-3 py-2.5">
              <p className="font-mono text-[10px] uppercase tracking-wider text-[#8a8a8a]">{r}</p>
              <p className="mt-0.5 text-[15px] font-bold text-[#1e1e1e]">{v}</p>
            </div>
          ))}
        </div>
        {share > 40 && (
          <div className="mt-3">
            <Notice tone="wait" title={`${share}% de avatar é acima do alvo de 20%`}>
              O avatar é cobrado por segundo; a ilustração é praticamente grátis.
              Pedir ajuste aqui reduz o custo da produção.
            </Notice>
          </div>
        )}
      </Card>

      <Card>
        <SectionTitle hint="Alternância entre o apresentador e as ilustrações, na ordem em que aparece no vídeo.">
          Roteiro segmentado
        </SectionTitle>
        <div className="space-y-2">
          {segmentos.map((s, i) => {
            const ehAvatar = (s.kind || (s.slide ? 'slide' : 'avatar')) === 'avatar';
            return (
              <div key={s.id || i} className={cx(
                'rounded-xl border p-3.5',
                ehAvatar ? 'border-[#e67e22]/25 bg-[#e67e22]/[0.04]' : 'border-black/[0.08] bg-white',
              )}>
                <div className="flex items-center gap-2">
                  <Badge tone={ehAvatar ? 'active' : 'neutral'}>
                    {ehAvatar ? 'Apresentador' : 'Ilustração'}
                  </Badge>
                  <span className="font-mono text-[10px] text-[#a8a8a8]">
                    {s.beat} · {Math.round(s.min_duration_s || 0)}s
                  </span>
                </div>
                <p className="mt-2 text-[13px] leading-relaxed text-[#2b2b2b]">{s.script}</p>
              </div>
            );
          })}
        </div>
      </Card>

      {corteVertical.length > 0 && (
        <Card>
          <SectionTitle hint="Reel e Short saem deste mesmo vídeo — mesma fala, recortada em 9:16. Não é gravado de novo.">
            Corte vertical · {Math.round(durVertical)}s
          </SectionTitle>
          <div className="flex flex-wrap gap-2">
            {corteVertical.map((s, i) => {
              const origem = segmentos.find((seg) => seg.id === s.source);
              const ehAvatar = s.kind === 'avatar';
              return (
                <div key={s.id || i} className={cx(
                  'flex items-center gap-2 rounded-lg border px-3 py-2',
                  ehAvatar ? 'border-[#e67e22]/25 bg-[#e67e22]/[0.04]' : 'border-black/[0.08] bg-white',
                )}>
                  <Badge tone={ehAvatar ? 'active' : 'neutral'}>
                    {ehAvatar ? 'recorte do apresentador' : 'ilustração vertical'}
                  </Badge>
                  <span className="text-[12px] text-[#4a4a4a]">
                    de {s.source} · {Math.round(origem?.min_duration_s || 0)}s
                  </span>
                </div>
              );
            })}
          </div>
        </Card>
      )}
    </Gate>
  );
}

// ── Artigo no blog ───────────────────────────────────────────────────────────

/**
 * Promoção do artigo de rascunho para publicado.
 *
 * O gate do artigo grava como RASCUNHO: a URL existe (as peças sociais
 * dependem dela para resolver [LINK_ARTIGO]), mas o post não aparece no blog.
 * Faltava a outra metade — não havia tela nenhuma para publicar de fato, e o
 * artigo ficava preso enquanto a semana de posts apontava para uma página que
 * o visitante não via.
 */
export function CartaoArtigo({
  estado, status, onPublicar, ocupado,
}: {
  estado: EstadoStudio;
  status: string | null;
  onPublicar: () => void;
  ocupado: boolean;
}) {
  const url = estado.artigo?.url;
  if (!url) return null;
  const publicado = status === 'published';

  return (
    <Card>
      <Eyebrow>artigo</Eyebrow>
      <SectionTitle hint={publicado
        ? 'No ar. É para cá que as peças da semana apontam.'
        : 'Rascunho: o endereço está reservado e responde 404 até você publicar. '
          + 'As peças sociais já apontam para ele, então publique antes do primeiro post sair.'}>
        {estado.artigo?.titulo || 'Artigo'}
      </SectionTitle>

      {/* Enquanto é rascunho a URL responde 404 para o visitante — o link
          seria uma promessa falsa. Mostra o endereço como texto e diz quando
          ele passa a valer. */}
      {publicado ? (
        <a href={url} target="_blank" rel="noopener noreferrer"
          className="inline-block text-[13px] text-[#e67e22] underline underline-offset-2">
          {url}
        </a>
      ) : (
        <p className="break-all font-mono text-[12px] text-[#8a8a8a]">{url}</p>
      )}

      <div className="mt-4 flex items-center gap-3 border-t border-black/[0.06] pt-4">
        {publicado ? (
          <Badge tone="done">publicado</Badge>
        ) : (
          <>
            <Button onClick={onPublicar} disabled={ocupado}>
              {ocupado ? 'Publicando…' : 'Publicar no blog'}
            </Button>
            <Badge tone="wait">rascunho</Badge>
          </>
        )}
      </div>
    </Card>
  );
}

// ── 4. Social ────────────────────────────────────────────────────────────────

export function PassoSocial({
  estado, agendamento, naFila = 0, onAgendar, ocupado,
}: {
  estado: EstadoStudio;
  agendamento?: Agendamento | null;
  naFila?: number;
  onAgendar?: () => void;
  ocupado?: boolean;
}) {
  const plano = (estado.planoSocial || {}) as Record<string, any>;
  const linkedin: any[]  = plano.linkedin || [];
  const threads: any[]   = plano.threads || [];
  const carrossel: any[] = plano.carrossel || [];
  const stories: any[]   = plano.stories || [];
  const comunidade: any[] = plano.youtube_community || [];
  const total = linkedin.length + threads.length + carrossel.length + stories.length + comunidade.length;
  const framesDeStories = stories.reduce((a, s) => a + (s.frames?.length || 0), 0);

  const todas    = [...linkedin, ...threads, ...carrossel, ...stories, ...comunidade];
  const levamAoVideo = todas.filter((p) => p?.cta?.tipo === 'assistir');
  const metodos  = new Set(todas.map((p) => p?.copy_skill_id).filter(Boolean));
  const fatia    = todas.length ? Math.round((levamAoVideo.length / todas.length) * 100) : 0;

  if (!total) {
    return <Empty title="Nenhuma peça social ainda">O plano é montado depois da aprovação do vídeo.</Empty>;
  }

  return (
    <div className="space-y-4">
      <Card>
        <Eyebrow>passo 4 de 4 · social</Eyebrow>
        <SectionTitle hint={plano.promessa_video}>
          {total} peças na semana
        </SectionTitle>
        <div className="flex flex-wrap gap-2">
          <Badge tone="done">{linkedin.length} LinkedIn</Badge>
          <Badge tone="done">{threads.length} Threads</Badge>
          <Badge tone="done">{carrossel.length} carrossel</Badge>
          <Badge tone="done">{stories.length} publicações de stories ({framesDeStories} frames)</Badge>
          {comunidade.length > 0 && <Badge tone="done">{comunidade.length} Comunidade YT</Badge>}
          <Badge tone={fatia >= 25 && fatia <= 70 ? 'done' : 'wait'}>
            {fatia}% levam ao vídeo
          </Badge>
          <Badge tone={metodos.size >= 3 ? 'done' : 'wait'}>
            {metodos.size} métodos de copy
          </Badge>
        </div>
        {(fatia < 25 || fatia > 70 || metodos.size < 3) && (
          <div className="mt-3">
            <Notice tone="wait" title="A composição do plano está desequilibrada">
              {fatia < 25 && 'Poucas peças convertem para o vídeo. '}
              {fatia > 70 && 'Quase toda peça pede para assistir — repetição cansa e derruba o alcance. '}
              {metodos.size < 3 && 'Poucos métodos de copy: as peças vão soar iguais.'}
            </Notice>
          </div>
        )}

        {/* A ação que faltava. Até aqui o plano parava nesta tela: era gerado,
            exibido e nunca publicado, porque o publisher lê a fila e o plano
            vivia no checkpoint do grafo. */}
        {onAgendar && (
          <div className="mt-5 border-t border-black/[0.06] pt-4">
            {naFila > 0 ? (
              <div className="flex flex-wrap items-center gap-3">
                <Badge tone="done">{naFila} na fila</Badge>
                <p className="text-[12.5px] text-[#6b6b6b]">
                  O publicador roda de hora em hora e solta cada peça no horário marcado.
                </p>
              </div>
            ) : (
              <div className="flex flex-wrap items-center gap-3">
                <Button onClick={onAgendar} loading={ocupado}>
                  Agendar a semana
                </Button>
                <p className="text-[12.5px] text-[#6b6b6b]">
                  Distribui as peças em D+1 a D+7 e desenha as imagens de carrossel
                  e stories. Nada vai ao ar antes do horário marcado.
                </p>
              </div>
            )}

            {agendamento && agendamento.falhas.length > 0 && (
              <div className="mt-3">
                <Notice title={`${agendamento.falhas.length} peça(s) não entraram na fila`}>
                  <ul className="list-disc space-y-0.5 pl-4">
                    {agendamento.falhas.map((f, i) => <li key={i}>{f}</li>)}
                  </ul>
                  <p className="mt-2">
                    As demais {agendamento.enfileirados} foram agendadas — uma falha de
                    imagem não derruba a semana inteira.
                  </p>
                </Notice>
              </div>
            )}
          </div>
        )}
      </Card>

      {/* O artigo é o destino de [LINK_ARTIGO] nas peças acima. Ele já existe
          no blog como rascunho: a URL é real, mas o post só aparece na
          listagem quando você promover. */}
      {estado.artigo?.url && (
        <Card>
          <Eyebrow>artigo no blog</Eyebrow>
          <SectionTitle hint="Gravado como rascunho. A URL já é a definitiva — publique quando quiser que apareça na listagem.">
            {estado.artigo.titulo}
          </SectionTitle>
          <a href={estado.artigo.url} target="_blank" rel="noopener noreferrer"
            className="text-[13px] text-[#e67e22] underline underline-offset-2">
            {estado.artigo.url}
          </a>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        {linkedin.map((p, i) => <LinkedInPreview key={p.id || i} post={p} />)}
        {threads.map((t, i) => <ThreadsPreview key={t.id || i} thread={t} />)}
        {carrossel.map((c, i) => <CarrosselPreview key={c.id || i} carrossel={c} />)}
        {stories.map((s, i) => <StoryPreview key={s.id || i} story={s} />)}
        {comunidade.map((p, i) => <YouTubeCommunityPreview key={p.id || i} post={p} />)}
      </div>
    </div>
  );
}

// ── Trabalhando ──────────────────────────────────────────────────────────────

export function PassoTrabalhando({ titulo, sub, trilha }: {
  titulo: string; sub: string; trilha: string[];
}) {
  return (
    <Card>
      <Working label={titulo} />
      <p className="mt-2 text-[13px] text-[#6b6b6b]">{sub}</p>
      {trilha.length > 0 && (
        <ul className="mt-4 space-y-1.5 border-t border-black/[0.06] pt-4">
          {trilha.slice(-6).map((t, i) => (
            <li key={i} className="font-mono text-[11px] text-[#8a8a8a]">{t}</li>
          ))}
        </ul>
      )}
    </Card>
  );
}


// ── Produção do vídeo ─────────────────────────────────────────────────────────

const STATUS_PRODUCAO: Record<string, { rotulo: string; tone: 'neutral' | 'active' | 'done' | 'error' | 'wait' }> = {
  completed:        { rotulo: 'pronto',      tone: 'done' },
  running:          { rotulo: 'rodando',     tone: 'active' },
  pending_callback: { rotulo: 'aguardando',  tone: 'active' },
  queued:           { rotulo: 'na fila',     tone: 'wait' },
  error:            { rotulo: 'falhou',      tone: 'error' },
  waiting:          { rotulo: '—',           tone: 'neutral' },
};

/**
 * Progresso da produção. Fica separado da trilha da jornada porque acontece
 * FORA do grafo: o Studio já avançou para o plano social enquanto voz, avatar
 * e edição rodam em Cloud Run Jobs encadeados por Pub/Sub.
 */
export function PainelProducao({
  producao, onDerivarVertical, ocupado,
}: {
  producao: Producao;
  onDerivarVertical?: () => void;
  ocupado?: boolean;
}) {
  const falhou = producao.etapas.find((e) => e.status === 'error');
  const corte  = producao.corteVertical;
  const corteEmCurso = corte === 'queued' || corte === 'running';
  const cortePronto  = corte === 'completed';

  return (
    <Card>
      <Eyebrow>produção do vídeo</Eyebrow>
      <SectionTitle hint="Roda em segundo plano. Você pode revisar o plano social enquanto isso.">
        {producao.videoPronto ? 'Vídeo pronto' : 'Produzindo o vídeo'}
      </SectionTitle>

      <div className="flex flex-wrap gap-2">
        {producao.etapas.map((e) => {
          const m = STATUS_PRODUCAO[e.status] ?? STATUS_PRODUCAO.waiting;
          return (
            <span key={e.id} className="inline-flex items-center gap-1.5 rounded-lg border border-black/[0.08] px-2.5 py-1.5">
              <span className="text-[12px] font-medium text-[#1e1e1e]">{e.rotulo}</span>
              <Badge tone={m.tone}>{m.rotulo}</Badge>
            </span>
          );
        })}
      </div>

      {falhou && (
        <div className="mt-4">
          <Notice title={`A etapa "${falhou.rotulo}" falhou`}>
            {falhou.detalhe || 'Sem detalhe informado.'}
          </Notice>
        </div>
      )}

      {producao.youtubeUrl && (
        <div className="mt-4 rounded-xl border border-[#16a34a]/25 bg-[#16a34a]/[0.04] p-4">
          <p className="text-[13px] font-semibold text-[#1e1e1e]">
            No YouTube como privado
            {producao.duracaoS ? ` · ${Math.round(producao.duracaoS / 60)} min` : ''}
          </p>
          <a href={producao.youtubeUrl} target="_blank" rel="noopener noreferrer"
            className="mt-1 inline-block text-[13px] text-[#e67e22] underline underline-offset-2">
            {producao.youtubeUrl}
          </a>
          <p className="mt-2 text-[12.5px] leading-relaxed text-[#4a4a4a]">
            Assista antes de tornar público. O corte vertical sai deste mesmo vídeo.
          </p>

          {/* Passo 6 do fluxo: o Reel e o Short são recortes DESTE vídeo, não
              produções novas. O avatar sai de um crop 9:16 dos clipes já
              gerados e a fala é o mesmo áudio — zero HeyGen, zero ElevenLabs. */}
          {onDerivarVertical && (
            <div className="mt-4 border-t border-[#16a34a]/20 pt-3.5">
              {cortePronto ? (
                <Badge tone="done">Reel e Short prontos</Badge>
              ) : corteEmCurso ? (
                <Working label="Recortando o Reel e o Short…" />
              ) : (
                <div className="flex flex-wrap items-center gap-3">
                  <Button variant="secondary" onClick={onDerivarVertical} loading={ocupado}>
                    Gerar Reel e Short
                  </Button>
                  <p className="text-[12.5px] text-[#6b6b6b]">
                    Recorta deste vídeo. Não gasta crédito de avatar nem de voz.
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
