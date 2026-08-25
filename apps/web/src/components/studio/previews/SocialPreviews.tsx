/**
 * SocialPreviews.tsx — O conteúdo como ele vai aparecer.
 *
 * Uma lista de texto cru não responde a pergunta que o revisor tem: "isso
 * funciona no feed?". Um post do LinkedIn corta na terceira linha, um
 * carrossel se lê deslizando, um story tem 15 segundos. A prévia imita o
 * suficiente da plataforma para essa decisão ser possível — sem virar um
 * clone pixel-perfect, que seria manutenção sem retorno.
 *
 * Todos mostram o CTA em destaque, porque é o campo que mais saiu errado em
 * produção: texto cortado no meio e link apontando para o blog quando o
 * assunto era o vídeo.
 */
'use client';

import { useState } from 'react';
import { Badge, Card, cx } from '../ui/primitives';

// O publisher troca estes marcadores pela URL real na hora de publicar.
function comLinks(texto: string): string {
  return texto
    .replace(/\[LINK_CANAL\]/g, 'youtube.com/@victorzore')
    .replace(/\[LINK_ARTIGO\]/g, 'eozore.com/blog/…');
}

/**
 * Rótulos dos tipos de CTA. "Assistir" leva ao vídeo agora; os outros
 * trabalham alcance, e é isso que sustenta o alcance das peças que convertem.
 * Nenhum deles é "fora do funil" — a regra de mistura é do plano, não da peça.
 */
const CTA_ROTULO: Record<string, string> = {
  assistir: 'assistir ao vídeo',
  salvar: 'salvar o post',
  marcar: 'marcar alguém',
  comentar: 'comentar',
  seguir: 'seguir o perfil',
  compartilhar: 'compartilhar',
  ler_artigo: 'ler o artigo',
};

function Cta({ cta }: { cta: Record<string, any> }) {
  const converte = cta?.tipo === 'assistir';
  return (
    <div className={cx(
      'mt-3 rounded-lg border px-3 py-2',
      converte ? 'border-primary/30 bg-primary/[0.06]' : 'border-black/10 bg-black/[0.02]',
    )}>
      <div className="flex items-center gap-2">
        <span className="font-mono text-[9px] uppercase tracking-wider text-text-soft">
          {CTA_ROTULO[cta?.tipo] || cta?.tipo}
        </span>
        {converte && <Badge tone="active">leva ao vídeo</Badge>}
      </div>
      <p className="mt-1 text-[13px] text-text-main">{comLinks(cta?.texto || '')}</p>
    </div>
  );
}

/** Método de copy que o agente escolheu para esta peça. */
function Metodo({ id }: { id?: string }) {
  if (!id) return null;
  return (
    <span className="font-mono text-[9px] uppercase tracking-wider text-text-faint">
      {id.replace('copy-', '')}
    </span>
  );
}

function Lacuna({ texto }: { texto: string }) {
  return (
    <p className="mt-2 text-[12px] italic leading-relaxed text-text-soft">
      Deixa em aberto: {texto}
    </p>
  );
}

function Dia({ n }: { n: number }) {
  return <Badge>{n === 0 ? 'mesmo dia do vídeo' : `D+${n}`}</Badge>;
}

function Cabecalho({ rotulo, cor, peca }: { rotulo: string; cor: string; peca: Record<string, any> }) {
  return (
    <div className="flex items-center justify-between border-b border-black/[0.06] px-4 py-2.5">
      <div className="flex items-center gap-2">
        <span className={cx('text-[11px] font-bold', cor)}>{rotulo}</span>
        <Metodo id={peca.copy_skill_id} />
      </div>
      <Dia n={peca.dia_offset ?? 0} />
    </div>
  );
}

// ── LinkedIn ─────────────────────────────────────────────────────────────────

/**
 * Cores de marca das plataformas. São referência EXTERNA — não fazem parte da
 * paleta éozoré e não devem virar token: mudam quando a plataforma muda, não
 * quando nosso design muda. Agrupadas para não ficarem como hex solto no meio
 * do JSX, onde pareciam decisão nossa.
 */
const COR_PLATAFORMA = {
  linkedin:  'text-[#0a66c2]',
  instagram: 'text-[#c13584]',
  youtube:   'text-[#ff0000]',
} as const;

export function LinkedInPreview({ post }: { post: Record<string, any> }) {
  const [aberto, setAberto] = useState(false);
  const corpo: string = post.corpo || '';
  // O LinkedIn colapsa em ~3 linhas e mostra "ver mais". O que está acima
  // desse corte é o que decide se alguém lê o resto.
  const cortado = corpo.length > 220;
  const visivel = aberto || !cortado ? corpo : corpo.slice(0, 220);

  return (
    <Card padded={false} className="overflow-hidden">
      <Cabecalho rotulo="LinkedIn" cor={COR_PLATAFORMA.linkedin} peca={post} />
      <div className="p-4">
        <div className="flex items-center gap-2.5">
          <div className="h-9 w-9 rounded-full bg-primary/20" />
          <div>
            <p className="text-[13px] font-semibold leading-tight text-text-main">Victor Zoré</p>
            <p className="text-[11px] text-text-soft">Líder Técnico em IA e ML</p>
          </div>
        </div>
        <p className="mt-3 text-[14px] font-semibold leading-snug text-text-main">{post.gancho}</p>
        <p className="mt-2 whitespace-pre-wrap text-[13px] leading-relaxed text-ink">
          {comLinks(visivel)}
          {cortado && !aberto && '… '}
          {cortado && (
            <button
              onClick={() => setAberto(!aberto)}
              className="ml-0.5 font-semibold text-text-muted hover:text-text-main"
            >
              {aberto ? 'ver menos' : 'ver mais'}
            </button>
          )}
        </p>
        {!!post.hashtags?.length && (
          <p className="mt-2 text-[13px] text-[#0a66c2]">
            {post.hashtags.map((h: string) => `#${h}`).join(' ')}
          </p>
        )}
        {post.lacuna && <Lacuna texto={post.lacuna} />}
        {post.cta && <Cta cta={post.cta} />}
      </div>

      {/* O link mora AQUI, não no post — link no corpo mede pior no alcance
          do LinkedIn. Visualmente separado do card do post, como aparece de
          verdade: um comentário publicado por você logo em seguida. */}
      {post.comentario_fixado && (
        <div className="border-t border-black/[0.06] bg-black/[0.015] p-4">
          <p className="mb-1.5 font-mono text-[9px] uppercase tracking-wider text-text-soft">
            seu primeiro comentário
          </p>
          <div className="flex gap-2.5">
            <div className="h-7 w-7 shrink-0 rounded-full bg-primary/20" />
            <p className="rounded-2xl bg-black/[0.04] px-3 py-2 text-[12.5px] leading-relaxed text-ink">
              {comLinks(post.comentario_fixado)}
            </p>
          </div>
        </div>
      )}
    </Card>
  );
}

// ── Threads ──────────────────────────────────────────────────────────────────

export function ThreadsPreview({ thread }: { thread: Record<string, any> }) {
  const posts: string[] = thread.posts || [];
  return (
    <Card padded={false} className="overflow-hidden">
      <Cabecalho rotulo={`Threads · série de ${posts.length}`} cor="text-text-main" peca={thread} />
      <div className="p-4">
        <p className="text-[14px] font-semibold leading-snug text-text-main">{thread.gancho}</p>
        <div className="mt-3 space-y-0">
          {posts.map((p, i) => (
            <div key={i} className="relative pb-4 pl-6 last:pb-0">
              {/* Linha que conecta a série — é assim que o Threads encadeia. */}
              {i < posts.length - 1 && (
                <span className="absolute left-[7px] top-4 h-full w-px bg-black/10" />
              )}
              <span className="absolute left-0 top-1 h-3.5 w-3.5 rounded-full border-2 border-primary bg-white" />
              <p className="text-[13px] leading-relaxed text-ink">{comLinks(p)}</p>
              <span className={cx(
                'mt-1 inline-block font-mono text-[10px]',
                p.length > 480 ? 'text-accent-error' : 'text-text-faint',
              )}>
                {p.length}/500
              </span>
            </div>
          ))}
        </div>
        {thread.lacuna && <Lacuna texto={thread.lacuna} />}
        {thread.cta && <Cta cta={thread.cta} />}
      </div>
    </Card>
  );
}

// ── Carrossel ────────────────────────────────────────────────────────────────

export function CarrosselPreview({ carrossel }: { carrossel: Record<string, any> }) {
  const slides: Record<string, any>[] = carrossel.slides || [];
  const [i, setI] = useState(0);
  const slide = slides[i];

  return (
    <Card padded={false} className="overflow-hidden">
      <Cabecalho rotulo={`Instagram · carrossel de ${slides.length}`} cor={COR_PLATAFORMA.instagram} peca={carrossel} />

      {/* Quadrado 1:1, como no feed. */}
      <div className="relative aspect-square bg-asset-bg p-8">
        <div className="flex h-full flex-col justify-center">
          <span className="font-mono text-[10px] uppercase tracking-widest text-asset-accent">
            {i + 1} / {slides.length}
          </span>
          <h3 className="mt-3 text-[22px] font-bold leading-tight text-asset-ink">
            {slide?.titulo}
          </h3>
          <p className="mt-3 text-[13px] leading-relaxed text-asset-muted">{slide?.corpo}</p>
        </div>
        {i > 0 && (
          <button onClick={() => setI(i - 1)}
            className="absolute left-2 top-1/2 h-9 w-9 -translate-y-1/2 rounded-full bg-white/10 text-white hover:bg-white/20">
            ‹
          </button>
        )}
        {i < slides.length - 1 && (
          <button onClick={() => setI(i + 1)}
            className="absolute right-2 top-1/2 h-9 w-9 -translate-y-1/2 rounded-full bg-white/10 text-white hover:bg-white/20">
            ›
          </button>
        )}
      </div>

      <div className="flex justify-center gap-1.5 py-2.5">
        {slides.map((_, n) => (
          <button key={n} onClick={() => setI(n)}
            className={cx('h-1.5 rounded-full transition-all',
              n === i ? 'w-5 bg-primary' : 'w-1.5 bg-black/15')} />
        ))}
      </div>

      <div className="border-t border-black/[0.06] p-4">
        <p className="text-[13px] leading-relaxed text-ink">{comLinks(carrossel.legenda || '')}</p>
        {carrossel.lacuna && <Lacuna texto={carrossel.lacuna} />}
        {carrossel.cta && <Cta cta={carrossel.cta} />}
      </div>
    </Card>
  );
}

// ── Stories ──────────────────────────────────────────────────────────────────

/**
 * Uma PUBLICAÇÃO de stories = uma sequência de 3 a 4 frames, tocada em
 * ordem — não um card só. As barrinhas de progresso no topo são o sinal
 * visual do Instagram para "isso é uma sequência", e são o motivo de existir
 * este componente em vez de mostrar `story.texto` direto.
 */
export function StoryPreview({ story }: { story: Record<string, any> }) {
  const frames: Record<string, any>[] = story.frames || [];
  const [i, setI] = useState(0);
  const frame = frames[i];

  return (
    <Card padded={false} className="overflow-hidden">
      <Cabecalho rotulo={`Story · ${frames.length} frames`} cor={COR_PLATAFORMA.instagram} peca={story} />

      <div className="relative mx-auto my-3 aspect-[9/16] w-40 overflow-hidden rounded-xl bg-asset-bg">
        {/* Barrinhas de progresso — o sinal de "sequência" do Instagram */}
        <div className="absolute inset-x-2 top-2 z-10 flex gap-1">
          {frames.map((_, n) => (
            <span key={n} className={cx('h-[3px] flex-1 rounded-full',
              n === i ? 'bg-white' : n < i ? 'bg-white/70' : 'bg-white/25')} />
          ))}
        </div>

        <button onClick={() => setI((i - 1 + frames.length) % frames.length)}
          className="absolute inset-y-0 left-0 z-10 w-1/3" aria-label="frame anterior" />
        <button onClick={() => setI((i + 1) % frames.length)}
          className="absolute inset-y-0 right-0 z-10 w-1/3" aria-label="próximo frame" />

        {/* Só `texto` e `enquete` viram imagem — é o que social_publish.py
            renderiza. `ilustracao` é DIREÇÃO DE ARTE: descreve a imagem que
            deveria estar no fundo, e hoje nada a gera. Fica fora da moldura
            do telefone para não passar por conteúdo. */}
        <div className="flex h-full flex-col justify-center gap-2 p-4">
          <p className="text-[13px] font-semibold leading-snug text-asset-ink">{frame?.texto}</p>
        </div>

        {frame?.enquete && (
          <div className="absolute inset-x-3 bottom-4 rounded-lg bg-white/95 px-2.5 py-2">
            <p className="text-[10px] font-semibold text-text-main">{frame.enquete}</p>
            <div className="mt-1.5 flex gap-1">
              <span className="flex-1 rounded bg-black/[0.06] py-1 text-center text-[9px]">Sim</span>
              <span className="flex-1 rounded bg-black/[0.06] py-1 text-center text-[9px]">Não</span>
            </div>
          </div>
        )}
      </div>

      <div className="flex justify-center gap-1.5 pb-2">
        {frames.map((_, n) => (
          <button key={n} onClick={() => setI(n)}
            className={cx('h-1.5 rounded-full transition-all',
              n === i ? 'w-5 bg-[#c13584]' : 'w-1.5 bg-black/15')} />
        ))}
      </div>

      <div className="px-4 pb-4">
        {/* Direção de arte do frame visível. NÃO vai ao ar: a imagem publicada
            é gerada por template a partir de `texto`, e não existe geração de
            imagem em nenhum ponto da pipeline. Enquanto isso não existir, o
            story sai tipográfico — dizer isso aqui é mais honesto do que
            desenhar um preview que promete o que não sai. */}
        {frame?.ilustracao && (
          <div className="mb-3 rounded-lg border border-dashed border-asset-accent/40 bg-asset-accent/[0.05] px-3 py-2">
            <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-asset-accent">
              direção de arte · não é publicada
            </p>
            <p className="mt-1 text-[11.5px] leading-snug text-text-muted">{frame.ilustracao}</p>
          </div>
        )}
        {story.lacuna && <Lacuna texto={story.lacuna} />}
        {story.cta && <Cta cta={story.cta} />}
      </div>
    </Card>
  );
}

// ── YouTube Community ─────────────────────────────────────────────────────────

export function YouTubeCommunityPreview({ post }: { post: Record<string, any> }) {
  return (
    <Card padded={false} className="overflow-hidden">
      <Cabecalho rotulo="Comunidade do YouTube" cor={COR_PLATAFORMA.youtube} peca={post} />
      <div className="p-4">
        <div className="flex items-center gap-2.5">
          <div className="h-9 w-9 rounded-full bg-primary/20" />
          <div>
            <p className="text-[13px] font-semibold leading-tight text-text-main">Victor Zoré</p>
            <p className="text-[11px] text-text-soft">Alcança quem já é inscrito</p>
          </div>
        </div>
        <p className="mt-3 whitespace-pre-wrap text-[13px] leading-relaxed text-ink">
          {comLinks(post.texto || '')}
        </p>
        {!!post.enquete_opcoes?.length && (
          <div className="mt-3 space-y-1.5">
            {post.enquete_opcoes.map((op: string, n: number) => (
              <div key={n} className="rounded-lg border border-black/10 px-3 py-2 text-[12.5px] text-ink">
                {op}
              </div>
            ))}
          </div>
        )}
        {post.lacuna && <Lacuna texto={post.lacuna} />}
        {post.cta && <Cta cta={post.cta} />}
      </div>
    </Card>
  );
}
