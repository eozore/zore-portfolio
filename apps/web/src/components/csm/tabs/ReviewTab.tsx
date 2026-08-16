/* ============================================================
   ReviewTab.tsx — Aba 3: Revisão do pacote + Aprovação
   O pacote é gerado automaticamente em background após publicação.
   Aqui o usuário revisa roteiro, copies e slides, depois aprova.
   Aprovação dispara o pipeline de produção (TTS + HeyGen + render).
   ============================================================ */
'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import type {
  DraftState, ManifestSegmentV2, ManifestAnchor,
  SpecialistLinkedIn, SpecialistThread,
} from '../CsmDashboard';
import type { ApproveResult, StepStatus } from '@/app/api/csm/approve-package/route';
import { normalizeChannelToggles, isChannelEnabled, type ChannelToggles } from '@/lib/channels';
import DerivativesReview, { type ExcludedSet } from './DerivativesReview';
import styles from './PackageTab.module.css';

interface ReviewTabProps {
  draft: DraftState;
  updateDraft: (partial: Partial<DraftState>) => void;
  sessionId: string;
  onBack: () => void;
  onApproved: () => void;
  /** Reexecuta a geração do pacote a partir do artigo já publicado (estado de erro). */
  onRetryPackage: () => void;
}

type SubTab = 'roteiro' | 'slides' | 'thumbnails' | 'linkedin' | 'derivacoes';

function buildTranscript(chatHistory: DraftState['chatHistory']): string {
  return (chatHistory ?? []).map((m) => `${m.role === 'user' ? 'CEO' : 'CMO'}: ${m.text}`).join('\n\n');
}

function slugify(str: string): string {
  return str.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9\s-]/g, '').trim().replace(/\s+/g, '-').replace(/-+/g, '-').slice(0, 100);
}

function prevYoutubeScript(manifest: DraftState['manifestV2'] | undefined): string {
  return manifest?.youtube?.segments?.map((segment) => segment.script).filter(Boolean).join('\n\n') ?? '';
}

function beatClass(beat: string): string {
  const b = beat.toLowerCase();
  if (b.includes('hook'))         return styles.beatHook;
  if (b.includes('intro'))        return styles.beatIntro;
  if (b.includes('teoria'))       return styles.beatTeoria;
  if (b.includes('codigo'))       return styles.beatCodigo;
  if (b.includes('demo'))         return styles.beatDemo;
  if (b.includes('resumo') || b.includes('cta')) return styles.beatResumo;
  return styles.beatDefault;
}

/** Checkpoints do package-job traduzidos para linguagem de usuário. */
const STAGE_LABELS: Record<string, string> = {
  'script:enviando':          'Enviando pauta e artigo para a fila…',
  'script:enfileirado':       'Na fila — o job vai começar em instantes',
  'script:iniciado':          'Escrevendo o roteiro segmentado e desenhando os slides',
  'script:persistindo':       'Salvando roteiro e deck',
  'script:concluido':         'Roteiro pronto',
  'derivatives:enfileirado':  'Na fila — derivações vão começar em instantes',
  'derivatives:iniciado':     'Gerando thumbnails e copies de LinkedIn/Threads',
  'derivatives:omnicanal':    'Gerando reels, shorts, carrosséis e stories',
  'derivatives:persistindo':  'Salvando derivações',
  'derivatives:concluido':    'Pacote completo',
};

const PACKAGE_STATUS_LABELS: Record<string, string> = {
  idle:       'Aguardando publicação',
  generating: 'Gerando pacote de conteúdo...',
  script_ready: 'Roteiro pronto para aprovação',
  ready:      'Pacote pronto para revisão',
  error:      'Erro na geração do pacote',
};

export default function ReviewTab({ draft, updateDraft, sessionId, onBack, onApproved, onRetryPackage }: ReviewTabProps) {
  const [activeTab, setActiveTab] = useState<SubTab>('roteiro');
  const [isApproving, setIsApproving] = useState(false);
  const [isGeneratingDerivatives, setIsGeneratingDerivatives] = useState(false);
  const [approveResult, setApproveResult] = useState<ApproveResult | null>(null);
  const [approveError, setApproveError] = useState('');
  const [channelToggles, setChannelToggles] = useState<ChannelToggles>(() => normalizeChannelToggles(null));
  const [retryingAsset, setRetryingAsset] = useState<'thumbnails' | 'copies' | null>(null);
  /** Peças que o usuário excluiu na revisão — chave `${tipo}:${id}`. Vive só
   *  nesta sessão de revisão: reprovar uma peça é decisão do momento da
   *  aprovação, não estado que deva sobreviver a uma regeneração. */
  const [excluded, setExcluded] = useState<ExcludedSet>(() => new Set());
  const [assetRetryError, setAssetRetryError] = useState('');

  // Carrega os canais ligados/desligados em Configurações → Canais & Formatos,
  // para ocultar sub-abas e itens de canais que o usuário desligou.
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch('/api/csm/config/channels', { headers: { 'x-csm-session': 'authenticated' } });
        if (res.ok) {
          const data = await res.json();
          setChannelToggles(normalizeChannelToggles(data.toggles));
        }
      } catch { /* mantém defaults */ }
    })();
  }, []);

  // Pollings para aguardar pacote gerado em background
  const [pollCount, setPollCount] = useState(0);
  const packageStatus = draft.packageStatus ?? 'idle';
  const isGenerating  = packageStatus === 'generating';
  const hasPackage    = !!(draft.manifestV2 || draft.repurposedData);

  // Acessores do pacote
  const manifest    = draft.manifestV2 ?? null;
  const ytSegments  = useMemo(() => manifest?.youtube?.segments ?? [], [manifest]);
  const manifestHtml = draft.manifestHtml ?? '';
  const thumbs      = draft.thumbnails ?? null;
  const spCopies    = draft.specialistCopies ?? null;
  const rd          = draft.repurposedData;
  const linkedinPosts = spCopies?.linkedin_posts ?? rd?.linkedinPosts ?? [];
  const threads       = spCopies?.threads ?? rd?.threads ?? [];

  /**
   * Polling do estado escrito pelo package-job.
   *
   * A geração agora roda num Cloud Run Job; esta aba é a única fonte de
   * verdade sobre o progresso. A condição de parada é o packageStatus deixar
   * de ser "generating" — antes era "chegou manifestV2 ou repurposedData",
   * que nunca terminava na fase de derivações (o manifesto já existia desde a
   * fase anterior) e não tinha como distinguir erro de "ainda processando".
   */
  useEffect(() => {
    if (!isGenerating || !sessionId) return;
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/csm/session?id=${sessionId}`);
        if (!res.ok) return;
        const data = await res.json();
        const d = data.draft;
        if (!d) return;

        const done = d.packageStatus && d.packageStatus !== 'generating';
        updateDraft({
          manifestV2:       d.manifestV2 ?? draft.manifestV2 ?? null,
          manifestHtml:     d.manifestHtml ?? draft.manifestHtml ?? '',
          thumbnails:       d.thumbnails ?? draft.thumbnails ?? null,
          specialistCopies: d.specialistCopies ?? draft.specialistCopies ?? null,
          repurposedData:   d.repurposedData ?? draft.repurposedData ?? null,
          youtubeScript:    d.youtubeScript ?? prevYoutubeScript(d.manifestV2),
          packageStage:     d.packageStage ?? '',
          packageStageDetail: d.packageStageDetail ?? '',
          ...(done ? {
            packageStatus: d.packageStatus,
            workflowStage: d.workflowStage ?? (d.packageStatus === 'ready' ? 'package_ready' : 'script_ready'),
            packageError:  d.packageError ?? '',
          } : {}),
        } as Partial<DraftState>);

        if (done) clearInterval(interval);
        setPollCount((c) => c + 1);
      } catch { /* silent */ }
    }, 8_000); // poll a cada 8s
    return () => clearInterval(interval);
  }, [isGenerating, sessionId, updateDraft, draft.manifestV2, draft.manifestHtml, draft.thumbnails, draft.specialistCopies, draft.repurposedData]);

  const handleApproveScript = useCallback(async () => {
    if (packageStatus !== 'script_ready' || isGeneratingDerivatives || !sessionId) return;
    setIsGeneratingDerivatives(true);
    setApproveError('');
    try {
      const res = await fetch('/api/csm/derivatives', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessionId }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      // 202 — o package-job assume daqui. Entrar em "generating" religa o
      // polling acima, que traz o resultado quando o job terminar.
      updateDraft({
        packageStatus: 'generating',
        workflowStage: 'package_generating',
        packageStage: 'derivatives:enfileirado',
        packageError: '',
      } as Partial<DraftState>);
    } catch (err) {
      setApproveError(err instanceof Error ? err.message : 'Falha ao enfileirar as derivações');
    } finally {
      setIsGeneratingDerivatives(false);
    }
  }, [packageStatus, isGeneratingDerivatives, sessionId, updateDraft]);

  // ── Aprovação final: dispara pipeline TTS + HeyGen + render ─────────────
  const handleApprove = useCallback(async () => {
    if (!hasPackage || packageStatus !== 'ready' || isApproving) return;
    setIsApproving(true); setApproveError(''); setApproveResult(null);

    const pauta     = draft.pauta;
    const linkedinOn = isChannelEnabled(channelToggles, 'linkedin_text');
    const threadsOn  = isChannelEnabled(channelToggles, 'threads_posts');
    const reelsOn    = isChannelEnabled(channelToggles, 'instagram_reels');
    const spLi      = linkedinOn ? ((spCopies?.linkedin_posts ?? []) as SpecialistLinkedIn[]) : [];
    const spTh      = threadsOn  ? ((spCopies?.threads ?? []) as SpecialistThread[]) : [];
    const rdPosts   = linkedinOn ? (rd?.linkedinPosts ?? []) : [];
    const reelItems = reelsOn    ? (rd?.reelsScripts ?? []) : [];
    const hasYT     = !!draft.youtubeScript?.trim() || ytSegments.length > 0;

    const articleSlug  = draft.suggestedSlug  || slugify(pauta?.titulo ?? 'artigo');
    const articleTitle = draft.suggestedTitle || pauta?.titulo || 'Artigo';

    // Monta itens de texto
    const textItems = spLi.length > 0
      ? [
          ...spLi.map((p) => ({
            platform: 'linkedin' as const, format: 'text',
            title: p.hook.slice(0, 120),
            copy: `${p.hook}\n\n${p.copy}\n\n${p.hashtags}`,
            scheduledAt: new Date().toISOString(), status: 'aprovado' as const,
          })),
          ...spTh.map((t) => ({
            platform: 'threads' as const, format: 'thread',
            title: t.topic, copy: (t.posts ?? []).join('\n\n---\n\n'),
            threadPosts: t.posts, scheduledAt: new Date().toISOString(), status: 'aprovado' as const,
          })),
        ]
      : rdPosts.map((p) => ({
          platform: 'linkedin' as const, format: 'text',
          title: p.hook?.slice(0, 120) ?? '',
          copy: `${p.hook ?? ''}\n\n${p.copy ?? ''}`,
          scheduledAt: new Date().toISOString(), status: 'aprovado' as const,
        }));

    // A exclusão feita na revisão precisa valer aqui, senão o toggle é
    // decorativo: o usuário marca "excluída" e a peça publica assim mesmo.
    const incluido = (kind: string, id: string | undefined, i: number) =>
      !excluded.has(`${kind}:${id ?? i}`);

    const videoItems = reelItems
      .filter((r, i) => incluido('reel', (r as { id?: string }).id, i))
      .map((r, i) => ({
      id: (r as { id?: string }).id ?? `reel-${i}`,
      platform: 'instagram' as const, format: 'reel',
      title: (r as { title?: string }).title ?? `Reel ${i + 1}`,
      copy: (r as { script?: string }).script ?? '',
      scheduledAt: new Date().toISOString(), status: 'aprovado' as const,
    }));

    /**
     * Carrossel, stories e posts de imagem.
     *
     * Estes três eram gerados, exibidos nesta aba, e então DESCARTADOS: nunca
     * entravam no payload da aprovação, então nada além de LinkedIn, Threads e
     * Reels chegava a publicar. Só entram itens com imagem renderizada — o
     * Instagram rejeita post sem mídia, e enfileirar um item fadado a falhar só
     * gera ruído na fila.
     */
    const carouselOn = isChannelEnabled(channelToggles, 'instagram_carousel');
    const storiesOn  = isChannelEnabled(channelToggles, 'instagram_stories');
    const feedOn     = isChannelEnabled(channelToggles, 'instagram_feed');

    type MediaItem = {
      id: string; platform: string; format: string; title: string; copy: string;
      imageUrl?: string; imageUrls?: string[];
      scheduledAt: string; status: 'aprovado';
    };
    const mediaItems: MediaItem[] = [];

    if (carouselOn) {
      (rd?.carousels ?? []).forEach((c, i) => {
        if (!incluido('carousel', c.id, i)) return;
        const urls = (c as { imageUrls?: string[] }).imageUrls ?? [];
        if (urls.length < 2) return;   // Instagram exige 2+ imagens no carrossel
        mediaItems.push({
          id: c.id ?? `carousel-${i}`, platform: 'instagram', format: 'carousel',
          title: c.title ?? `Carrossel ${i + 1}`, copy: c.caption ?? '',
          imageUrls: urls,
          scheduledAt: new Date().toISOString(), status: 'aprovado',
        });
      });
    }
    if (storiesOn) {
      (rd?.storiesIdeas ?? []).forEach((s, i) => {
        if (!incluido('story', s.id, i)) return;
        const url = (s as { imageUrl?: string }).imageUrl;
        if (!url) return;
        mediaItems.push({
          id: s.id ?? `story-${i}`, platform: 'instagram', format: 'story',
          title: s.angle ?? `Story ${i + 1}`, copy: s.copy ?? '',
          imageUrl: url,
          scheduledAt: new Date().toISOString(), status: 'aprovado',
        });
      });
    }
    if (feedOn) {
      (rd?.imagePosts ?? []).forEach((p, i) => {
        if (!incluido('image', p.id, i)) return;
        const url = (p as { imageUrl?: string }).imageUrl;
        if (!url) return;
        mediaItems.push({
          id: p.id ?? `image-${i}`, platform: 'instagram', format: 'image',
          title: p.title ?? `Post ${i + 1}`, copy: p.copy ?? '',
          imageUrl: url,
          scheduledAt: new Date().toISOString(), status: 'aprovado',
        });
      });
    }

    try {
      const res = await fetch('/api/csm/approve-package', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          textItems:     textItems.length  ? textItems  : undefined,
          videoItems:    videoItems.length ? videoItems : undefined,
          mediaItems:    mediaItems.length ? mediaItems : undefined,
          youtubeScript: hasYT ? (draft.youtubeScript || ytSegments.map((s) => s.script).join('\n\n')) : undefined,
          articleSlug,
          articleTitle,
          sessionId,
          csmSession: 'authenticated',
        }),
      });
      const result: ApproveResult = await res.json();
      setApproveResult(result);
      // Persiste o calendário da semana no draft — sem isso o plano sumia no
      // primeiro reload e a aba Publicações não tinha como exibi-lo.
      if (result.plan?.length) updateDraft({ publishPlan: result.plan });
      if (result.text.status !== 'error' && result.video.status !== 'error') {
        onApproved();
      }
    } catch (err) {
      setApproveError(err instanceof Error ? err.message : 'Falha na aprovação');
    } finally {
      setIsApproving(false);
    }
  }, [hasPackage, packageStatus, isApproving, draft, spCopies, rd, ytSegments, sessionId, onApproved, channelToggles, updateDraft, excluded]);

  const linkedinChannelOn = isChannelEnabled(channelToggles, 'linkedin_text') || isChannelEnabled(channelToggles, 'threads_posts');
  const derivacoesChannelOn = ['instagram_reels', 'instagram_stories', 'instagram_feed', 'instagram_carousel', 'youtube_shorts', 'youtube_community']
    .some((id) => isChannelEnabled(channelToggles, id));

  // Retomada por asset — reexecuta só thumbnails ou só copies, sem tocar no
  // roteiro/slides já aprovados. Ver /api/csm/package/asset-retry.
  const handleRetryAsset = useCallback(async (asset: 'thumbnails' | 'copies') => {
    if (retryingAsset || !sessionId) return;
    setRetryingAsset(asset);
    setAssetRetryError('');
    try {
      const res = await fetch('/api/csm/package/asset-retry', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessionId, asset }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      if (asset === 'thumbnails') updateDraft({ thumbnails: data.thumbnails ?? null });
      else updateDraft({ specialistCopies: data.specialistCopies ?? null });
    } catch (err) {
      setAssetRetryError(err instanceof Error ? err.message : 'Falha ao regenerar');
    } finally {
      setRetryingAsset(null);
    }
  }, [retryingAsset, sessionId, updateDraft]);

  // Cada sub-aba mostra quantos itens realmente existem — sem isso, "Slides"
  // e "Derivações" pareciam abas mortas mesmo quando o pacote tinha conteúdo,
  // porque só apareciam clicando dentro. Contagem 0 = badge cinza "vazio", não
  // some, para deixar claro que o agente daquele asset falhou ou não gerou.
  const slideCount = ytSegments.filter((s) => !!s.slide).length;
  const thumbCount = [thumbs?.option_minimal, thumbs?.option_provocative].filter(Boolean).length;
  const derivacoesCount = (rd?.reelsScripts?.length ?? 0) + (rd?.youtubeShorts?.length ?? 0)
    + (rd?.carousels?.length ?? 0) + (rd?.storiesIdeas?.length ?? 0) + (rd?.imagePosts?.length ?? 0);

  const tabs: { id: SubTab; label: string; count: number }[] = [
    { id: 'roteiro',    label: 'Roteiro',    count: ytSegments.length },
    { id: 'slides',     label: 'Slides',     count: slideCount },
    { id: 'thumbnails', label: 'Thumbnails', count: thumbCount },
    ...(linkedinChannelOn ? [{ id: 'linkedin' as const, label: 'LinkedIn',   count: linkedinPosts.length + threads.length }] : []),
    ...(derivacoesChannelOn ? [{ id: 'derivacoes' as const, label: 'Derivações', count: derivacoesCount }] : []),
  ];

  // Se a sub-aba ativa foi desligada (usuário mudou config em outra aba), volta para roteiro.
  useEffect(() => {
    if (!tabs.some((t) => t.id === activeTab)) setActiveTab('roteiro');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [linkedinChannelOn, derivacoesChannelOn]);

  return (
    <div className={styles.container}><div className={styles.inner}>

      {/* Header */}
      <header className={styles.header}>
        <div className={styles.kicker}>revisão do pacote de conteúdo</div>
        <h1 className={styles.title}><em>{draft.pauta?.titulo ?? draft.suggestedTitle ?? 'Pacote'}</em></h1>
        {draft.publishedArticleUrl && (
          <div className={styles.metaRow}>
            <span className={styles.metaItem}>
              <b>Artigo:</b>{' '}
              <a href={draft.publishedArticleUrl} target="_blank" rel="noopener noreferrer"
                style={{ color: '#7c3aed', textDecoration: 'underline' }}>
                {draft.publishedArticleUrl}
              </a>
            </span>
          </div>
        )}
      </header>

      {/* Status do pacote */}
      {isGenerating && (
        <div className={styles.generatingBox}>
          <div className={styles.spinner} />
          <div>
            <div className={styles.generatingTitle}>Gerando pacote de conteúdo em background…</div>
            <div className={styles.generatingPhase}>
              {/* Checkpoint real publicado pelo package-job a cada etapa. */}
              {STAGE_LABELS[draft.packageStage ?? ''] ?? 'Roteiro + assets de apoio — pode levar 4-8 minutos'}
              {draft.packageStageDetail ? ` · ${draft.packageStageDetail}` : ''}
            </div>
            <div className={styles.elapsedLabel}>
              Polling {pollCount}x · roda num job dedicado — pode fechar esta aba sem perder o progresso
            </div>
          </div>
        </div>
      )}

      {!isGenerating && !hasPackage && (
        <div className={styles.emptyState}>
          <div className={styles.emptyIcon}>⏳</div>
          <div className={styles.emptyTitle}>Pacote ainda não disponível</div>
          <div className={styles.emptyDesc}>
            {packageStatus === 'error'
              ? 'Ocorreu um erro na geração do pacote.'
              : 'Publique o artigo primeiro. O pacote será gerado automaticamente.'}
          </div>
          {packageStatus === 'error' && (
            <>
              {draft.packageError && (
                <div style={{ color: '#dc2626', fontSize: '0.75rem', marginTop: '8px', maxWidth: '520px', wordBreak: 'break-word', fontFamily: 'monospace' }}>
                  {draft.packageError}
                </div>
              )}
              <button onClick={onRetryPackage} disabled={!draft.generatedContent}
                style={{ marginTop: '16px', padding: '10px 24px', borderRadius: '10px', border: 'none', background: 'linear-gradient(135deg,#d97706,#ea580c)', color: '#fff', fontWeight: 700, fontSize: '0.9rem', cursor: 'pointer' }}>
                ↺ Gerar pacote novamente
              </button>
              <div style={{ color: '#8a8a8a', fontSize: '0.72rem', marginTop: '8px' }}>
                O artigo publicado é reaproveitado — só o pacote é regenerado.
              </div>
            </>
          )}
        </div>
      )}

      {/* Conteúdo do pacote */}
      {hasPackage && !isGenerating && (<>
        {/* Sub-tab nav */}
        <nav className={styles.packageNav}>
          {tabs.map((t) => (
            <button key={t.id} onClick={() => setActiveTab(t.id)}
              className={`${styles.packageNavBtn} ${activeTab === t.id ? styles.packageNavBtnActive : ''}`}>
              {t.label}
              <span
                className={`${styles.badge} ${t.count > 0 ? styles.badgeOrange : styles.badgeEmpty}`}
                title={t.count > 0 ? `${t.count} item(ns)` : 'Nada gerado ainda — pode ser falha do agente'}
              >
                {t.count > 0 ? t.count : '—'}
              </span>
            </button>
          ))}
        </nav>

        {/* Roteiro */}
        {activeTab === 'roteiro' && (
          <div className={styles.panel}>
            {ytSegments.length === 0 ? (
              <div className={styles.emptyState}>
                <div className={styles.emptyDesc}>Roteiro segmentado não disponível (CMO Agent indisponível durante geração).</div>
              </div>
            ) : (
              <div className={styles.card}>
                <div className={styles.cardTitle}>Roteiro YouTube · {ytSegments.length} segmentos</div>
                {ytSegments.map((seg, i) => (
                  <div key={seg.id ?? i} className={styles.segmentCard}>
                    <div className={styles.segmentHead}>
                      <span className={styles.segId}>{seg.id}</span>
                      <span className={`${styles.beatTag} ${beatClass(seg.beat)}`}>{seg.beat}</span>
                      {seg.slide
                        ? <span className={styles.slideTag}>slide {seg.slide}</span>
                        : <span className={`${styles.slideTag} ${styles.slideTagNone}`}>avatar full</span>}
                    </div>
                    {seg.script && <div className={styles.segScript}>{seg.script}</div>}
                    {(seg.anchors ?? []).length > 0 && (
                      <div className={styles.anchorList}>
                        {seg.anchors.map((a, ai) => (
                          <span key={ai} className={styles.anchorBadge}>{a.on_phrase}</span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Slides */}
        {activeTab === 'slides' && (
          <div className={styles.panel}>
            {!manifestHtml ? (
              <div className={styles.emptyState}><div className={styles.emptyDesc}>Deck de slides não disponível.</div></div>
            ) : (
              <div className={styles.card}>
                <div className={styles.cardTitle}>Deck de Slides</div>
                <iframe srcDoc={manifestHtml} style={{ width: '100%', height: '500px', border: 'none', borderRadius: '12px' }} title="Slides Preview" />
              </div>
            )}
          </div>
        )}

        {/* Thumbnails */}
        {activeTab === 'thumbnails' && (
          <div className={styles.panel}>
            {!thumbs || (!thumbs.option_minimal && !thumbs.option_provocative) ? (
              <div className={styles.emptyState}>
                <div className={styles.emptyDesc}>Thumbnails não disponíveis (falha na geração).</div>
                <button onClick={() => handleRetryAsset('thumbnails')} disabled={retryingAsset === 'thumbnails'}
                  style={{ marginTop: '12px', padding: '8px 18px', borderRadius: '8px', border: '1px solid rgba(230,126,34,0.35)', background: 'rgba(230,126,34,0.1)', color: '#e67e22', fontWeight: 700, fontSize: '0.8rem', cursor: retryingAsset ? 'wait' : 'pointer' }}>
                  {retryingAsset === 'thumbnails' ? 'Gerando…' : '↺ Gerar novamente'}
                </button>
                {assetRetryError && <div style={{ color: '#dc2626', fontSize: '0.75rem', marginTop: '8px' }}>{assetRetryError}</div>}
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                {[['Minimalista', thumbs.option_minimal], ['Provocativa', thumbs.option_provocative]].map(([label, html]) => (
                  <div key={label} className={styles.card}>
                    <div className={styles.cardTitle}>{label}</div>
                    {html ? <iframe srcDoc={html} style={{ width: '100%', height: '200px', border: 'none', borderRadius: '8px' }} title={label} /> : <div className={styles.emptyDesc}>Indisponível</div>}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* LinkedIn */}
        {activeTab === 'linkedin' && (
          <div className={styles.panel}>
            {linkedinPosts.length === 0 ? (
              <div className={styles.emptyState}>
                <div className={styles.emptyDesc}>Copies LinkedIn não disponíveis (falha na geração).</div>
                <button onClick={() => handleRetryAsset('copies')} disabled={retryingAsset === 'copies'}
                  style={{ marginTop: '12px', padding: '8px 18px', borderRadius: '8px', border: '1px solid rgba(230,126,34,0.35)', background: 'rgba(230,126,34,0.1)', color: '#e67e22', fontWeight: 700, fontSize: '0.8rem', cursor: retryingAsset ? 'wait' : 'pointer' }}>
                  {retryingAsset === 'copies' ? 'Gerando…' : '↺ Gerar novamente'}
                </button>
                {assetRetryError && <div style={{ color: '#dc2626', fontSize: '0.75rem', marginTop: '8px' }}>{assetRetryError}</div>}
              </div>
            ) : (
              (linkedinPosts as SpecialistLinkedIn[]).map((p, i) => (
                <div key={p.id ?? i} className={styles.card}>
                  <div className={styles.cardTitle}>Post #{i + 1}</div>
                  <div className={styles.segScript} style={{ whiteSpace: 'pre-wrap' }}>{p.hook}{'\n\n'}{p.copy}</div>
                  {p.hashtags && <div style={{ color: '#2563eb', fontSize: '0.78rem', marginTop: '4px' }}>{p.hashtags}</div>}
                </div>
              ))
            )}
          </div>
        )}

        {/* Derivações */}
        {activeTab === 'derivacoes' && (
          <div className={styles.panel}>
            <DerivativesReview
              draft={draft}
              channelToggles={channelToggles}
              excluded={excluded}
              onToggle={(key) => setExcluded((prev) => {
                const next = new Set(prev);
                if (next.has(key)) next.delete(key); else next.add(key);
                return next;
              })}
            />
          </div>
        )}
      </>)}

      {/* Plano da semana — o que sai em cada dia após a aprovação */}
      {approveResult?.plan?.length ? (
        <div className={styles.card} style={{ marginTop: '16px' }}>
          <div className={styles.cardTitle}>Plano de publicação · próximos 7 dias</div>
          <div style={{ fontSize: '0.78rem', color: '#6b6b6b', marginBottom: '10px' }}>
            O publicador roda de hora em hora e envia cada peça no horário abaixo.
          </div>
          {approveResult.plan.map((day) => (
            <div key={day.day} style={{ marginBottom: '10px' }}>
              <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#e67e22', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: '4px' }}>
                Dia {day.day} · {new Date(day.date).toLocaleDateString('pt-BR', { weekday: 'short', day: '2-digit', month: '2-digit' })}
              </div>
              {day.items.map((item, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', padding: '5px 0', borderBottom: '1px solid rgba(30,30,30,0.05)', fontSize: '0.8rem' }}>
                  <span style={{ color: '#1e1e1e', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    <b style={{ color: '#6b6b6b', fontWeight: 600 }}>{item.platform}</b> · {item.title || item.format}
                  </span>
                  <span style={{ color: '#6b6b6b', flexShrink: 0, fontFamily: 'monospace' }}>
                    {new Date(item.scheduledAt).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              ))}
            </div>
          ))}
        </div>
      ) : null}

      {/* Barra de ação */}
      <div className={styles.actionBar} style={{ justifyContent: 'space-between', marginTop: '16px' }}>
        <button className={styles.backBtn} onClick={onBack}>← Artigo</button>

        {approveError && (
          <div style={{ color: '#dc2626', fontSize: '0.8rem', padding: '8px' }}>{approveError}</div>
        )}

        {approveResult && (
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <span style={{ color: '#16a34a', fontSize: '0.85rem', fontWeight: 'bold' }}>
              ✓ Pipeline disparado
            </span>
            {approveResult.errors?.length > 0 && (
              <span style={{ color: '#d97706', fontSize: '0.75rem' }}>
                ({approveResult.errors.length} erro(s) parcial(is))
              </span>
            )}
            {approveResult.blockedChannels?.length ? (
              <span style={{ color: '#8a8a8a', fontSize: '0.75rem' }}>
                {approveResult.blockedChannels.length} canal(is) ignorado(s) (desligado em Configurações)
              </span>
            ) : null}
          </div>
        )}

        {packageStatus === 'script_ready' ? (
          <button
            onClick={handleApproveScript}
            disabled={isGeneratingDerivatives}
            style={{ padding: '14px 28px', borderRadius: '12px', fontWeight: 'bold', border: 'none', cursor: isGeneratingDerivatives ? 'not-allowed' : 'pointer', fontSize: '1rem', background: 'linear-gradient(135deg,#d97706,#ea580c)', color: '#fff' }}>
            {isGeneratingDerivatives ? 'Gerando derivações...' : '✅ Aprovar roteiro e gerar derivações'}
          </button>
        ) : <button
          onClick={handleApprove}
          disabled={!hasPackage || packageStatus !== 'ready' || isApproving || !!approveResult}
          style={{
            padding: '14px 28px', borderRadius: '12px', fontWeight: 'bold', border: 'none', cursor: !hasPackage || packageStatus !== 'ready' || isApproving || !!approveResult ? 'not-allowed' : 'pointer', fontSize: '1rem',
            background: approveResult ? 'rgba(22,163,74,0.15)' : !hasPackage || packageStatus !== 'ready' ? 'rgba(30,30,30,0.05)' : 'linear-gradient(135deg,#16a34a,#15803d)',
            color: approveResult ? '#16a34a' : !hasPackage || packageStatus !== 'ready' ? '#8a8a8a' : '#ffffff',
          }}>
          {isApproving ? 'Aprovando...' : approveResult ? '✓ Aprovado' : '✅ Aprovar & Produzir Vídeo'}
        </button>}
      </div>

    </div></div>
  );
}
