/* ============================================================
   DerivativesReview.tsx — revisão visual das derivações

   Substitui a tabela de contagens que existia antes ("Reels 3,
   Stories 5, Carrosséis 1"), que obrigava o usuário a aprovar 13
   imagens e 12 peças de texto sem ter visto nenhuma delas.

   Três decisões de design:

   1. Cada formato é mostrado na proporção em que será consumido —
      carrossel 1:1 com scroll horizontal (o mesmo gesto do swipe),
      stories 9:16. Julgar uma peça vertical num card horizontal
      esconde exatamente os problemas de enquadramento.

   2. O gancho de Reels/Shorts é o elemento visual dominante. São os
      3 primeiros segundos que decidem a retenção; o resto do roteiro
      é contexto secundário.

   3. Cada peça pode ser excluída individualmente. Sem isso "revisar"
      é só olhar — o usuário via um carrossel ruim e a única saída era
      reprovar o pacote inteiro.
   ============================================================ */
'use client';

import { useMemo, useState } from 'react';
import type { DraftState } from '../CsmDashboard';
import { isChannelEnabled, type ChannelToggles } from '@/lib/channels';
import styles from './DerivativesReview.module.css';

/** Item excluído da publicação, identificado por `${kind}:${id}`. */
export type ExcludedSet = Set<string>;

interface Props {
  draft: DraftState;
  channelToggles: ChannelToggles;
  excluded: ExcludedSet;
  onToggle: (key: string) => void;
}

/** Serve imagem do bucket privado através da rota autenticada. */
function mediaUrl(src?: string): string {
  return src ? `/api/csm/media?src=${encodeURIComponent(src)}` : '';
}

/** ~2,5 palavras por segundo é a cadência de narração medida nos roteiros. */
function spokenSeconds(text?: string): number {
  return Math.round((text ?? '').trim().split(/\s+/).filter(Boolean).length / 2.5);
}

function Toggle({ on, onClick }: { on: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`${styles.toggle} ${on ? styles.toggleOn : styles.toggleOff}`}
      title={on ? 'Publicar esta peça' : 'Excluída — não será publicada'}
    >
      {on ? '✓ incluída' : '✕ excluída'}
    </button>
  );
}

function Section({ title, meta, children }: { title: string; meta: string; children: React.ReactNode }) {
  return (
    <section className={styles.section}>
      <header className={styles.sectionHead}>
        <h3 className={styles.sectionTitle}>{title}</h3>
        <span className={styles.sectionMeta}>{meta}</span>
      </header>
      {children}
    </section>
  );
}

export default function DerivativesReview({ draft, channelToggles, excluded, onToggle }: Props) {
  const rd = draft.repurposedData;
  const [zoom, setZoom] = useState<string | null>(null);

  const on = (id: string) => isChannelEnabled(channelToggles, id);

  const carousels   = on('instagram_carousel') ? (rd?.carousels ?? [])     : [];
  const stories     = on('instagram_stories')  ? (rd?.storiesIdeas ?? [])  : [];
  const imagePosts  = on('instagram_feed')     ? (rd?.imagePosts ?? [])    : [];
  const reels       = on('instagram_reels')    ? (rd?.reelsScripts ?? [])  : [];
  const shorts      = on('youtube_shorts')     ? (rd?.youtubeShorts ?? []) : [];

  const total = carousels.length + stories.length + imagePosts.length + reels.length + shorts.length;
  const publicando = total - [...excluded].filter((k) =>
    ['carousel', 'story', 'image', 'reel', 'short'].some((p) => k.startsWith(`${p}:`))).length;

  const semImagem = useMemo(() => {
    const faltando: string[] = [];
    carousels.forEach((c, i) => { if (((c as { imageUrls?: string[] }).imageUrls ?? []).length < 2) faltando.push(`carrossel ${i + 1}`); });
    stories.forEach((s, i) => { if (!(s as { imageUrl?: string }).imageUrl) faltando.push(`story ${i + 1}`); });
    imagePosts.forEach((p, i) => { if (!(p as { imageUrl?: string }).imageUrl) faltando.push(`post ${i + 1}`); });
    return faltando;
  }, [carousels, stories, imagePosts]);

  if (total === 0) {
    return (
      <div className={styles.empty}>
        <div className={styles.emptyIcon}>📭</div>
        <div className={styles.emptyTitle}>Nenhuma derivação disponível</div>
        <div className={styles.emptyDesc}>
          Aprove o roteiro para gerar Reels, Shorts, carrossel, stories e posts de imagem.
        </div>
      </div>
    );
  }

  return (
    <div className={styles.wrap}>
      {/* Resumo: quantas peças realmente vão ao ar */}
      <div className={styles.summary}>
        <span className={styles.summaryCount}>{publicando}</span>
        <span className={styles.summaryLabel}>
          de {total} peças serão publicadas ao longo da semana
        </span>
        {semImagem.length > 0 && (
          <span className={styles.warn} title="Instagram rejeita post sem mídia — estas peças não serão enfileiradas">
            ⚠ sem imagem: {semImagem.join(', ')}
          </span>
        )}
      </div>

      {/* ── Carrossel ─────────────────────────────────────────── */}
      {carousels.map((c, ci) => {
        const urls = (c as { imageUrls?: string[] }).imageUrls ?? [];
        const key = `carousel:${c.id ?? ci}`;
        const incluido = !excluded.has(key);
        return (
          <Section key={key} title="Carrossel · Instagram" meta={`${urls.length} slides`}>
            <div className={`${styles.card} ${incluido ? '' : styles.cardOff}`}>
              <div className={styles.cardHead}>
                <span className={styles.cardTitle}>{c.title}</span>
                <Toggle on={incluido} onClick={() => onToggle(key)} />
              </div>
              {urls.length >= 2 ? (
                /* Scroll horizontal reproduz o swipe: você avalia a sequência
                   do jeito que o leitor vai percorrer, não como grade estática. */
                <div className={styles.swipe}>
                  {urls.map((u, i) => (
                    <button key={i} className={styles.swipeItem} onClick={() => setZoom(u)} type="button">
                      <img src={mediaUrl(u)} alt={`Slide ${i + 1}`} loading="lazy" />
                      <span className={styles.swipeNum}>{i + 1}</span>
                    </button>
                  ))}
                </div>
              ) : (
                <div className={styles.missing}>
                  Sem imagens renderizadas — o Instagram exige 2 ou mais slides, então este carrossel não será publicado.
                </div>
              )}
              {c.caption && <p className={styles.caption}>{c.caption}</p>}
            </div>
          </Section>
        );
      })}

      {/* ── Stories ───────────────────────────────────────────── */}
      {stories.length > 0 && (
        <Section title="Stories · Instagram" meta={`${stories.length} peças, uma por dia`}>
          <div className={styles.storyRow}>
            {stories.map((s, i) => {
              const key = `story:${s.id ?? i}`;
              const incluido = !excluded.has(key);
              const url = (s as { imageUrl?: string }).imageUrl;
              return (
                <div key={key} className={`${styles.storyCard} ${incluido ? '' : styles.cardOff}`}>
                  <div className={styles.storyDay}>{s.day}</div>
                  {url ? (
                    <button className={styles.storyImg} onClick={() => setZoom(url)} type="button">
                      <img src={mediaUrl(url)} alt={s.angle ?? `Story ${i + 1}`} loading="lazy" />
                    </button>
                  ) : (
                    <div className={styles.storyImgMissing}>sem imagem</div>
                  )}
                  <Toggle on={incluido} onClick={() => onToggle(key)} />
                </div>
              );
            })}
          </div>
        </Section>
      )}

      {/* ── Posts de imagem ───────────────────────────────────── */}
      {imagePosts.length > 0 && (
        <Section title="Posts de imagem · Instagram" meta={`${imagePosts.length} peça(s)`}>
          <div className={styles.feedRow}>
            {imagePosts.map((p, i) => {
              const key = `image:${p.id ?? i}`;
              const incluido = !excluded.has(key);
              const url = (p as { imageUrl?: string }).imageUrl;
              return (
                <div key={key} className={`${styles.feedCard} ${incluido ? '' : styles.cardOff}`}>
                  {url ? (
                    <button className={styles.feedImg} onClick={() => setZoom(url)} type="button">
                      <img src={mediaUrl(url)} alt={p.title} loading="lazy" />
                    </button>
                  ) : (
                    <div className={styles.storyImgMissing}>sem imagem</div>
                  )}
                  <div className={styles.feedBody}>
                    <span className={styles.cardTitle}>{p.title}</span>
                    <p className={styles.caption}>{p.copy}</p>
                    <Toggle on={incluido} onClick={() => onToggle(key)} />
                  </div>
                </div>
              );
            })}
          </div>
        </Section>
      )}

      {/* ── Reels e Shorts ────────────────────────────────────── */}
      {[
        { titulo: 'Reels · Instagram', prefixo: 'reel',  itens: reels  as { id?: string; title?: string; hook3s?: string; script?: string; visualCue?: string }[] },
        { titulo: 'Shorts · YouTube',  prefixo: 'short', itens: shorts as { id?: string; title?: string; hook3s?: string; script?: string; visualCue?: string }[] },
      ].filter((g) => g.itens.length > 0).map((g) => (
        <Section key={g.prefixo} title={g.titulo} meta={`${g.itens.length} roteiro(s)`}>
          {g.itens.map((r, i) => {
            const key = `${g.prefixo}:${r.id ?? i}`;
            const incluido = !excluded.has(key);
            const dur = spokenSeconds(r.script);
            /* Reels/Shorts perdem alcance passando de ~60s; sinalizar aqui é
               mais barato que descobrir depois de renderizar o vídeo. */
            const longo = dur > 60;
            return (
              <div key={key} className={`${styles.card} ${incluido ? '' : styles.cardOff}`}>
                <div className={styles.cardHead}>
                  <span className={styles.cardTitle}>{r.title}</span>
                  <span className={`${styles.dur} ${longo ? styles.durWarn : ''}`}>~{dur}s</span>
                  <Toggle on={incluido} onClick={() => onToggle(key)} />
                </div>
                {r.hook3s && (
                  <div className={styles.hook}>
                    <span className={styles.hookLabel}>gancho · 3s</span>
                    <p className={styles.hookText}>{r.hook3s}</p>
                  </div>
                )}
                <p className={styles.script}>{r.script}</p>
                {r.visualCue && <p className={styles.visual}>🎬 {r.visualCue}</p>}
              </div>
            );
          })}
        </Section>
      ))}

      {/* Lightbox — imagem em tamanho real, para ler o texto de verdade */}
      {zoom && (
        <div className={styles.lightbox} onClick={() => setZoom(null)} role="presentation">
          <img src={mediaUrl(zoom)} alt="Visualização ampliada" />
          <button className={styles.lightboxClose} type="button" aria-label="Fechar">✕</button>
        </div>
      )}
    </div>
  );
}
