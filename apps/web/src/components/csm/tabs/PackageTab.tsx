/* ================================================================
   PackageTab.tsx — Sprint 3 / G4 — Preview unificado do pacote
   6 sub-tabs: Roteiro | Slides | Thumbnails | Artigo | LinkedIn | Derivações
   ================================================================ */
'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import type {
  DraftState, PautaConcebida, RepurposedData,
  ManifestSegmentV2, ManifestAnchor,
  SpecialistLinkedIn, SpecialistThread,
} from '../CsmDashboard';
import type { ApproveResult, StepStatus } from '@/app/api/csm/approve-package/route';
import RichArticleRenderer from '../RichArticleRenderer';
import styles from './PackageTab.module.css';

interface PackageTabProps {
  draft: DraftState;
  updateDraft: (partial: Partial<DraftState>) => void;
  sessionId: string;
  onBack: () => void;
  onNext: () => void;
  /** Quando true: o usuário acabou de clicar em "Gerar Pacote" no IdeaTab */
  pendingGeneration?: boolean;
  /** Chamado assim que a geração começa — Dashboard zera o flag */
  onGenerationStarted?: () => void;
  /** Legado — mantido por compatibilidade mas não mais necessário */
  triggerRef?: React.MutableRefObject<(() => void) | null>;
}

type SubTab = 'roteiro' | 'slides' | 'thumbnails' | 'artigo' | 'linkedin' | 'derivacoes';

const PHASES = [
  'Iniciando pipeline Critic → Research...',
  'Pesquisando fontes e referências técnicas...',
  'Escrevendo artigo com rigor matemático...',
  'Gerando roteiro segmentado e âncoras...',
  'Criando thumbnails e copies especializados...',
  'Finalizando pacote completo...',
];

function slugify(str: string): string {
  return str.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9\s-]/g, '').trim().replace(/\s+/g, '-').replace(/-+/g, '-').slice(0, 100);
}

function useCopyFeedback() {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const copy = useCallback((text: string, key: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 1800);
    });
  }, []);
  return { copiedKey, copy };
}

function buildTranscript(chatHistory: DraftState['chatHistory']): string {
  return (chatHistory ?? [])
    .map((m) => `${m.role === 'user' ? 'CEO' : 'CMO'}: ${m.text}`)
    .join('\n\n');
}

/** Mapeia beat → CSS class */
function beatClass(beat: string): string {
  const b = beat.toLowerCase();
  if (b.includes('hook'))          return styles.beatHook;
  if (b.includes('intro'))         return styles.beatIntro;
  if (b.includes('teoria'))        return styles.beatTeoria;
  if (b.includes('codigo') || b.includes('code')) return styles.beatCodigo;
  if (b.includes('demo'))          return styles.beatDemo;
  if (b.includes('comparativo'))   return styles.beatComparativo;
  if (b.includes('consideracao'))  return styles.beatConsideracoes;
  if (b.includes('resumo') || b.includes('cta')) return styles.beatResumo;
  if (b.includes('gancho'))        return styles.beatGancho;
  if (b.includes('insight'))       return styles.beatInsight;
  return styles.beatDefault;
}

/** Mapeia action → CSS class de âncora */
function anchorClass(action: string): string {
  if (action === 'reveal')    return `${styles.anchorBadge} ${styles.anchorBadgeReveal}`;
  if (action === 'highlight') return `${styles.anchorBadge} ${styles.anchorBadgeHighlight}`;
  return styles.anchorBadge;
}

export default function PackageTab({ draft, updateDraft, sessionId, onBack, onNext, triggerRef, pendingGeneration, onGenerationStarted }: PackageTabProps) {
  const [isGenerating, setIsGenerating] = useState(false);
  const [phaseIndex, setPhaseIndex]     = useState(0);
  const [elapsed, setElapsed]           = useState(0);
  const [error, setError]               = useState<string | null>(null);
  const [partialError, setPartialError] = useState<string | null>(null);
  const [activeTab, setActiveTab]       = useState<SubTab>('roteiro');
  const { copiedKey, copy }             = useCopyFeedback();
  const hasTriggered = useRef(false);

  // ── G5: estados de aprovação ─────────────────────────────────────────────
  const [isApproving, setIsApproving]       = useState(false);
  const [approveResult, setApproveResult]   = useState<ApproveResult | null>(null);
  const [approveStepText,  setStepText]     = useState<StepStatus>('skipped');
  const [approveStepVideo, setStepVideo]    = useState<StepStatus>('skipped');
  const [approveDetailText,  setDetailText]  = useState('');
  const [approveDetailVideo, setDetailVideo] = useState('');

  const pauta      = draft.pauta as PautaConcebida | undefined;
  // hasPackage: pacote gerado = artigo existe E (manifestV2 OU repurposedData gerados)
  // Isso evita mostrar "Distribuir Pacote" antes da geração quando só o artigo foi restaurado
  const hasPackage = !!(draft.generatedContent?.trim() && (draft.manifestV2 || draft.repurposedData));

  // ── manifest v2 accessors ────────────────────────────────────────────────
  const manifest    = draft.manifestV2 ?? null;
  const ytSegments  = (manifest as any)?.youtube?.segments as ManifestSegmentV2[] | undefined ?? [];
  const reels       = (manifest as any)?.reels ?? [];
  const manifestHtml= draft.manifestHtml ?? '';
  const thumbs      = draft.thumbnails ?? null;
  const spCopies    = draft.specialistCopies ?? null;

  // ── repurposedData accessors (Sprint 1 fallback) ─────────────────────────
  const rd          = draft.repurposedData;
  const linkedinFallback = rd?.linkedinPosts ?? [];
  const reelsScripts     = rd?.reelsScripts  ?? [];
  const shorts           = rd?.youtubeShorts ?? [];
  const carousels        = rd?.carousels     ?? [];
  const storiesIdeas     = rd?.storiesIdeas  ?? [];

  // ── auto-trigger ─────────────────────────────────────────────────────────
  const triggerPackage = useCallback(async () => {
    // Não gera se já tem pacote completo (artigo + manifestV2/repurposedData)
    const alreadyGenerated = !!(draft.generatedContent?.trim() && (draft.manifestV2 || draft.repurposedData));
    if (!pauta || alreadyGenerated || isGenerating) return;
    setIsGenerating(true); setError(null); setPartialError(null);
    setElapsed(0); setPhaseIndex(0);
    hasTriggered.current = true;

    const startTime = Date.now();
    const timer      = setInterval(() => setElapsed(Math.floor((Date.now() - startTime) / 1000)), 1000);
    const phaseTimer = setInterval(() => setPhaseIndex((p) => Math.min(p + 1, PHASES.length - 1)), 40_000);

    try {
      const res  = await fetch('/api/csm/package', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pauta, chatTranscript: buildTranscript(draft.chatHistory),
          category: draft.category, language: draft.language, sessionId,
        }),
      });

      // Fix: captura respostas non-JSON (timeout upstream, 502, etc.)
      const contentType = res.headers.get('content-type') || '';
      if (!contentType.includes('application/json')) {
        const rawText = await res.text();
        throw new Error(rawText.slice(0, 150) || `HTTP ${res.status} sem JSON`);
      }

      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? `HTTP ${res.status}`);

      updateDraft({
        topic:           data.suggestedTitle || pauta.titulo,
        suggestedTitle:  data.suggestedTitle || pauta.titulo,
        suggestedSlug:   data.suggestedSlug  || slugify(pauta.titulo),
        estimatedReadTime: data.estimatedReadTime ?? 10,
        generatedContent:  data.articleContent ?? '',
        repurposedData:    (data.repurposedData as RepurposedData) ?? null,
        manifestV2:        data.manifestV2    ?? null,
        manifestHtml:      data.manifestHtml  ?? '',
        thumbnails:        data.thumbnails    ?? null,
        specialistCopies:  data.specialistCopies ?? null,
        format: 'blog',
      });
      if (data.partialError) setPartialError(data.partialError);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha na geração do pacote.');
    } finally {
      clearInterval(timer); clearInterval(phaseTimer); setIsGenerating(false);
    }
  }, [pauta, hasPackage, isGenerating, draft.chatHistory, draft.category, draft.language, sessionId, updateDraft]);

  // ── Disparo de geração: roda UMA VEZ ao montar se pendingGeneration=true ─
  // Usa um ref para capturar o valor no momento exato do mount e evitar
  // que o useEffect re-execute quando o flag é zerado pelo Dashboard.
  const pendingRef = useRef(pendingGeneration ?? false);
  useEffect(() => {
    const alreadyGenerated = !!(draft.generatedContent?.trim() && (draft.manifestV2 || draft.repurposedData));
    if (pendingRef.current && pauta && !alreadyGenerated && !isGenerating && !hasTriggered.current) {
      pendingRef.current = false;
      onGenerationStarted?.();
      triggerPackage();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Expõe requestGeneration via ref (legado)
  useEffect(() => {
    if (triggerRef) {
      triggerRef.current = () => {
        if (!hasTriggered.current && pauta && !hasPackage) triggerPackage();
      };
    }
  }, [triggerRef, pauta, hasPackage, triggerPackage]);

  // ── G5: orquestra aprovação única (texto social + vídeo pipeline) ─────────
  // NOTA: O artigo já foi publicado no PublishTab ANTES de chegar aqui.
  const handleApprove = useCallback(async () => {
    if (!pauta || !hasPackage || isApproving) return;
    setIsApproving(true);
    setApproveResult(null);

    // Determina quais etapas vão rodar
    const rdPosts      = draft.repurposedData?.linkedinPosts ?? [];
    const spLi         = (draft.specialistCopies?.linkedin_posts ?? []) as SpecialistLinkedIn[];
    const spTh         = (draft.specialistCopies?.threads ?? []) as SpecialistThread[];
    const hasText      = spLi.length > 0 || rdPosts.length > 0;
    const hasYT        = !!draft.youtubeScript?.trim();
    const reelItems    = (draft.repurposedData?.reelsScripts ?? []) as any[];
    const hasVideo     = hasYT || reelItems.length > 0;

    // Inicia estados visuais
    setStepText (hasText  ? 'skipped' : 'skipped');
    setStepVideo(hasVideo ? 'skipped' : 'skipped');
    setDetailText(''); setDetailVideo('');

    // Simula "running" enquanto aguarda
    if (hasText)  { setStepText('skipped');  setDetailText('agendando…'); }
    if (hasVideo) { setStepVideo('skipped'); setDetailVideo('disparando pipeline…'); }
    await new Promise((r) => setTimeout(r, 50));

    // Monta o payload (artigo já publicado — só referência)
    const articleSlug = draft.suggestedSlug || slugify(pauta.titulo);
    const articleTitle = draft.suggestedTitle || pauta.titulo;

    // Itens de texto: specialist copies têm prioridade, fallback para repurposed
    const textItems = spLi.length > 0
      ? [
          ...spLi.map((p) => ({
            platform: 'linkedin' as const,
            format: 'text',
            title: p.hook.slice(0, 120),
            copy: `${p.hook}\n\n${p.copy}\n\n${p.hashtags}`,
            scheduledAt: new Date().toISOString(),
            status: 'aprovado' as const,
          })),
          ...spTh.flatMap((t) => [{
            platform: 'threads' as const,
            format: 'thread',
            title: t.topic,
            copy: (t.posts ?? []).join('\n\n---\n\n'),
            threadPosts: t.posts,
            scheduledAt: new Date().toISOString(),
            status: 'aprovado' as const,
          }]),
        ]
      : rdPosts.map((p) => ({
          platform: 'linkedin' as const,
          format: 'text',
          title: p.hook?.slice(0, 120) ?? '',
          copy: `${p.hook ?? ''}\n\n${p.copy ?? ''}`,
          scheduledAt: new Date().toISOString(),
          status: 'aprovado' as const,
        }));

    const videoItems = reelItems.map((r, i) => ({
      id: r.id ?? `reel-${i}`,
      platform: 'instagram' as const,
      format: 'reel',
      title: r.title ?? `Reel ${i + 1}`,
      copy: r.script ?? '',
      scheduledAt: new Date().toISOString(),
      status: 'aprovado' as const,
    }));

    try {
      const res = await fetch('/api/csm/approve-package', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          textItems:    textItems.length ? textItems : undefined,
          videoItems:   videoItems.length ? videoItems : undefined,
          youtubeScript: hasYT ? draft.youtubeScript : undefined,
          articleSlug,
          articleTitle,
          sessionId,
          csmSession: 'authenticated',
        }),
      });

      const result: ApproveResult = await res.json();
      setApproveResult(result);

      // Atualiza estado visual de cada etapa
      setStepText(result.text.status);
      setStepVideo(result.video.status);
      setDetailText(result.text.detail ?? '');
      setDetailVideo(result.video.detail ?? '');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Falha na aprovação.';
      setStepText('error'); setStepVideo('error');
      setDetailText(msg); setDetailVideo(msg);
      setApproveResult({
        text: { status: 'error', detail: msg },
        video: { status: 'error', detail: msg },
        errors: [msg],
        approved_at: new Date().toISOString(),
      });
    } finally {
      setIsApproving(false);
    }
  }, [pauta, hasPackage, isApproving, draft, sessionId]);

  const estimatedTotal = 360;
  const progressPct = isGenerating
    ? Math.min(95, Math.round((elapsed / estimatedTotal) * 100))
    : hasPackage ? 100 : 0;

  // ── sem pauta ────────────────────────────────────────────────────────────
  if (!pauta) {
    return (
      <div className={styles.container}><div className={styles.inner}>
        <div className={styles.emptyState}>
          <div className={styles.emptyIcon}>💬</div>
          <div className={styles.emptyTitle}>Pauta ainda não concebida</div>
          <div className={styles.emptyDesc}>
            Converse com o CMO AI até ele emitir{' '}
            <strong>PAUTA CONCEBIDA COM SUCESSO</strong> e aprove o esboço.
          </div>
        </div>
        <div className={styles.actionBar}>
          <button className={styles.backBtn} onClick={onBack}>← Chat CMO</button>
        </div>
      </div></div>
    );
  }

  // ── pauta pronta mas pacote ainda não gerado (aguardando handoff) ─────────
  if (pauta && !hasPackage && !isGenerating && !error) {
    return (
      <div className={styles.container}><div className={styles.inner}>
        <header className={styles.header}>
          <div className={styles.kicker}>pauta aprovada · aguardando geração</div>
          <h1 className={styles.title}><em>{pauta.titulo}</em></h1>
          <div className={styles.metaRow}>
            {pauta.subtitulo && <span className={styles.metaItem}><b>Subtítulo:</b> {pauta.subtitulo}</span>}
            {pauta.tese      && <span className={styles.metaItem}><b>Tese:</b> {pauta.tese}</span>}
          </div>
        </header>
        <div className={styles.emptyState}>
          <div className={styles.emptyIcon}>✅</div>
          <div className={styles.emptyTitle}>Artigo publicado — pacote não gerado ainda</div>
          <div className={styles.emptyDesc}>
            Você chegou aqui após publicar o artigo. Clique em{' '}
            <strong>&ldquo;Gerar Pacote de Conteúdo&rdquo;</strong> para criar as
            derivações (roteiro YouTube, copies LinkedIn, thumbnails, etc).
          </div>
          <button
            className={styles.nextBtn}
            style={{ marginTop: 24 }}
            onClick={() => { hasTriggered.current = false; triggerPackage(); }}
          >
            Gerar Pacote de Conteúdo →
          </button>
        </div>
        <div className={styles.actionBar} style={{ justifyContent: 'center' }}>
          <button className={styles.backBtn} onClick={onBack}>← Voltar à Publicação</button>
        </div>
      </div></div>
    );
  }

  // ── sub-tab definitions ───────────────────────────────────────────────────
  const tabs: { id: SubTab; label: string; n: string; count?: number }[] = [
    { id: 'roteiro',    label: 'Roteiro',    n: '01', count: ytSegments.length },
    { id: 'slides',     label: 'Slides',     n: '02' },
    { id: 'thumbnails', label: 'Thumbnails', n: '03' },
    { id: 'artigo',     label: 'Artigo',     n: '04' },
    { id: 'linkedin',   label: 'LinkedIn',   n: '05',
      count: (spCopies?.linkedin_posts?.length ?? 0) || linkedinFallback.length },
    { id: 'derivacoes', label: 'Derivações', n: '06' },
  ];

  return (
    <div className={styles.container}><div className={styles.inner}>

      {/* ── header ─────────────────────────────────────────────────── */}
      <header className={styles.header}>
        <div className={styles.kicker}>pacote de conteúdo · sprint 3</div>
        <h1 className={styles.title}><em>{pauta.titulo}</em></h1>
        <div className={styles.metaRow}>
          {pauta.subtitulo  && <span className={styles.metaItem}><b>Subtítulo:</b> {pauta.subtitulo}</span>}
          {pauta.tese       && <span className={styles.metaItem}><b>Tese:</b> {pauta.tese}</span>}
          {pauta.publico    && <span className={styles.metaItem}><b>Público:</b> {pauta.publico}</span>}
          {pauta.duracao_alvo && <span className={styles.metaItem}><b>Duração:</b> {pauta.duracao_alvo}</span>}
        </div>
      </header>

      {/* ── generating ─────────────────────────────────────────────── */}
      {isGenerating && (
        <div className={styles.generatingBox}>
          <div className={styles.spinner} aria-hidden="true" />
          <div>
            <div className={styles.generatingTitle}>Gerando pacote de conteúdo…</div>
            <div className={styles.generatingPhase}>{PHASES[phaseIndex]}</div>
          </div>
          <div className={styles.progressTrack}>
            <div className={styles.progressFill} style={{ width: `${progressPct}%` }} />
          </div>
          <div className={styles.elapsedLabel}>{elapsed}s · estimativa: 4–8 min</div>
        </div>
      )}

      {/* ── error ──────────────────────────────────────────────────── */}
      {error && !isGenerating && (
        <div className={styles.errorBox}>
          <div className={styles.errorIcon}>⚠️</div>
          <div className={styles.errorText}>
            <strong>Falha na geração</strong>{error}
            <div><button className={styles.retryBtn}
              onClick={() => { hasTriggered.current = false; triggerPackage(); }}>
              Tentar novamente
            </button></div>
          </div>
        </div>
      )}

      {/* ── package content ────────────────────────────────────────── */}
      {hasPackage && !isGenerating && (<>

        {/* sub-tab nav */}
        <nav className={styles.packageNav} aria-label="Seções do pacote">
          {tabs.map((t) => (
            <button key={t.id}
              className={`${styles.tabBtn} ${activeTab === t.id ? styles.active : ''}`}
              onClick={() => setActiveTab(t.id)}
              aria-current={activeTab === t.id ? 'true' : undefined}
            >
              <span className={styles.tabBadge}>{t.n}</span>
              {t.label}
              {t.count !== undefined && t.count > 0 &&
                <span className={`${styles.badge} ${styles.badgeOrange}`}>{t.count}</span>}
            </button>
          ))}
        </nav>

        {/* ── 01 · Roteiro segmentado ──────────────────────────────── */}
        <div className={`${styles.panel} ${activeTab === 'roteiro' ? styles.active : ''}`}>
          {ytSegments.length === 0 ? (
            <div className={styles.emptyState}>
              <div className={styles.emptyDesc}>
                {draft.generatedContent?.trim()
                  ? 'Roteiro segmentado não gerado. O manifesto v2 requer o CMO Agent Python ativo. Gere o pacote novamente com o agente disponível.'
                  : 'Roteiro segmentado não disponível. Gere o pacote de conteúdo primeiro.'}
              </div>
            </div>
          ) : (
            <div className={styles.card}>
              <div className={styles.cardTitle}>
                <em>Roteiro YouTube · {ytSegments.length} segmentos</em>
              </div>
              <div className={styles.cardSub}>
                manifesto v2 · âncoras sincronizadas
                <span className={`${styles.badge} ${styles.badgeGreen}`}>v2</span>
              </div>
              <button
                className={`${styles.copyBtn} ${copiedKey === 'roteiro' ? styles.done : ''}`}
                onClick={() => copy(ytSegments.map((s) => s.script).filter(Boolean).join('\n\n'), 'roteiro')}
              >{copiedKey === 'roteiro' ? 'Copiado ✓' : 'Copiar tudo'}</button>

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
                  {seg.anchors?.length > 0 && (
                    <div className={styles.anchorList}>
                      {seg.anchors.map((a: ManifestAnchor, ai) => (
                        <span key={ai} className={anchorClass(a.action)}
                          title={`${a.action}${a.element ? ` #${a.element}` : ''}`}
                        >
                          {a.on_phrase}{a.element ? ` → #${a.element}` : ''}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── 02 · Slides (deck iframes) ────────────────────────────── */}
        <div className={`${styles.panel} ${activeTab === 'slides' ? styles.active : ''}`}>
          {!manifestHtml ? (
            <div className={styles.card}>
              <div className={styles.cardTitle}>Deck de Slides</div>
              <div className={styles.emptyState}>
                <div className={styles.emptyDesc}>
                  Deck SVG animado não disponível nesta sessão. Requer CMO Agent
                  Python com scriptwriter_agent ativo.
                </div>
              </div>
            </div>
          ) : (
            <>
              <div className={styles.card}>
                <div className={styles.cardTitle}>Deck YouTube <span className={`${styles.badge} ${styles.badgeOrange}`}>16:9</span></div>
                <div className={styles.cardSub}>deck v2 · slides com âncoras · Playwright-ready</div>
                <div className={styles.deckWrap}>
                  <iframe
                    className={styles.deckFrame}
                    srcDoc={manifestHtml}
                    title="Deck YouTube 16:9"
                    sandbox="allow-scripts"
                  />
                </div>
                <div className={styles.deckActions}>
                  <button className={styles.openDeckBtn} onClick={() => {
                    const blob = new Blob([manifestHtml], { type: 'text/html' });
                    window.open(URL.createObjectURL(blob), '_blank');
                  }}>Abrir em tela cheia ↗</button>
                </div>
                <div className={styles.deckNote}>
                  ✓ Self-contained · funciona offline · Playwright renderiza direto
                </div>
              </div>

              {reels.length > 0 && (
                <div className={styles.grid2}>
                  {reels.slice(0, 2).map((reel: any, ri: number) => (
                    <div key={reel.reel_id ?? ri} className={styles.card}>
                      <div className={styles.cardTitle}>
                        Mini-deck {reel.title ?? `Reel ${ri + 1}`}
                        <span className={`${styles.badge} ${styles.badgeGreen}`}>9:16</span>
                      </div>
                      <div className={styles.cardSub}>{reel.segments?.length ?? 0} segmentos</div>
                      <iframe
                        className={styles.deckFrameVert}
                        srcDoc={manifestHtml}
                        title={`Mini-deck Reel ${ri + 1}`}
                        sandbox="allow-scripts"
                      />
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>

        {/* ── 03 · Thumbnails ──────────────────────────────────────── */}
        <div className={`${styles.panel} ${activeTab === 'thumbnails' ? styles.active : ''}`}>
          {!thumbs ? (
            <div className={styles.card}>
              <div className={styles.cardTitle}>Thumbnails</div>
              <div className={styles.emptyState}>
                <div className={styles.emptyDesc}>
                  Thumbnails não geradas nesta sessão. Requer CMO Agent Python com
                  thumbnail_agent ativo.
                </div>
              </div>
            </div>
          ) : (
            <div className={styles.card}>
              <div className={styles.cardTitle}><em>2 opções de thumbnail</em></div>
              <div className={styles.cardSub}>1200 × 628px · dark premium · Playwright-ready</div>
              <div className={styles.thumbnailGrid}>
                {([
                  { key: 'option_minimal',     label: 'Opção Minimal (SVG conceitual)' },
                  { key: 'option_provocative', label: 'Opção Provocativa (contraste numérico)' },
                ] as const).map(({ key, label }) => (
                  thumbs[key] ? (
                    <div key={key} className={styles.thumbnailCard}>
                      <div className={styles.thumbnailLabel}>{label}</div>
                      <iframe
                        className={styles.thumbnailFrame}
                        srcDoc={thumbs[key]}
                        title={label}
                        sandbox="allow-scripts"
                      />
                      <div className={styles.thumbnailActions}>
                        <button className={`${styles.copyBtn} ${copiedKey === key ? styles.done : ''}`}
                          style={{ position: 'static' }}
                          onClick={() => copy(thumbs[key], key)}
                        >{copiedKey === key ? 'HTML copiado ✓' : 'Copiar HTML'}</button>
                        <button className={styles.openDeckBtn} onClick={() => {
                          const blob = new Blob([thumbs[key]], { type: 'text/html' });
                          window.open(URL.createObjectURL(blob), '_blank');
                        }}>Abrir ↗</button>
                      </div>
                    </div>
                  ) : null
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ── 04 · Artigo ──────────────────────────────────────────── */}
        <div className={`${styles.panel} ${activeTab === 'artigo' ? styles.active : ''}`}>
          <div className={styles.card}>
            <div className={styles.cardTitle}><em>{draft.suggestedTitle || pauta.titulo}</em></div>
            <div className={styles.cardSub}>
              artigo técnico · {draft.estimatedReadTime} min de leitura
              {draft.suggestedSlug && (
                <span className={`${styles.badge} ${styles.badgeOrange}`}>/{draft.suggestedSlug}</span>
              )}
            </div>
            <button
              className={`${styles.copyBtn} ${copiedKey === 'artigo' ? styles.done : ''}`}
              onClick={() => copy(draft.generatedContent, 'artigo')}
            >{copiedKey === 'artigo' ? 'Copiado ✓' : 'Copiar'}</button>
            <div style={{ marginTop: 16, background: '#ffffff', borderRadius: 10, overflow: 'hidden' }}>
              <RichArticleRenderer content={draft.generatedContent} />
            </div>
          </div>
        </div>

        {/* ── 05 · LinkedIn ──────────────────────────────────────────── */}
        <div className={`${styles.panel} ${activeTab === 'linkedin' ? styles.active : ''}`}>
          {/* Specialist copies (copy_agent — prioridade) */}
          {spCopies?.linkedin_posts && spCopies.linkedin_posts.length > 0 && (
            <>
              {(spCopies.linkedin_posts as SpecialistLinkedIn[]).map((post, i) => (
                <div key={post.id ?? i} className={styles.card}>
                  <div className={styles.cardTitle}>
                    Post {i + 1}
                    <span className={`${styles.badge} ${styles.badgeGreen}`}>specialist</span>
                  </div>
                  <div className={styles.cardSub}>linkedin · copy_agent · até 1200 chars</div>
                  <button
                    className={`${styles.copyBtn} ${copiedKey === `li-sp-${i}` ? styles.done : ''}`}
                    onClick={() => copy(`${post.hook}\n\n${post.copy}\n\n${post.hashtags}`, `li-sp-${i}`)}
                  >{copiedKey === `li-sp-${i}` ? 'Copiado ✓' : 'Copiar'}</button>
                  <div className={styles.postHook}>{post.hook}</div>
                  <div className={styles.derivItem}>
                    <div className={styles.derivLabel}>corpo</div>
                    <div className={styles.derivText}>{post.copy}</div>
                  </div>
                  <div className={styles.postHashtags}>{post.hashtags}</div>
                </div>
              ))}
              {/* Threads */}
              {spCopies.threads && (spCopies.threads as SpecialistThread[]).map((thread, ti) => (
                <div key={thread.id ?? ti} className={styles.card}>
                  <div className={styles.cardTitle}>Thread {thread.thread_number} — {thread.topic}</div>
                  <div className={styles.cardSub}>threads · {thread.posts?.length ?? 0} posts encadeados</div>
                  <button
                    className={`${styles.copyBtn} ${copiedKey === `th-${ti}` ? styles.done : ''}`}
                    onClick={() => copy((thread.posts ?? []).join('\n\n---\n\n'), `th-${ti}`)}
                  >{copiedKey === `th-${ti}` ? 'Copiado ✓' : 'Copiar thread'}</button>
                  {(thread.posts ?? []).map((post: string, pi: number) => (
                    <div key={pi} className={styles.threadPost}>
                      <div className={styles.threadPostNum}>POST {pi + 1}</div>
                      {post}
                    </div>
                  ))}
                  <div className={styles.postHashtags}>{thread.hashtags}</div>
                </div>
              ))}
            </>
          )}
          {/* Fallback: repurposedData (Sprint 1) */}
          {(!spCopies?.linkedin_posts?.length) && linkedinFallback.map((post, i) => (
            <div key={post.id ?? i} className={styles.card}>
              <div className={styles.cardTitle}>Post {i + 1}</div>
              <div className={styles.cardSub}>linkedin · distribution_agent</div>
              <button
                className={`${styles.copyBtn} ${copiedKey === `li-${i}` ? styles.done : ''}`}
                onClick={() => copy(`${post.hook}\n\n${post.copy}`, `li-${i}`)}
              >{copiedKey === `li-${i}` ? 'Copiado ✓' : 'Copiar'}</button>
              <div className={styles.derivItem}>
                <div className={styles.derivLabel}>gancho</div>
                <div className={styles.derivText}>{post.hook}</div>
              </div>
              <div className={styles.derivItem} style={{ marginTop: 10 }}>
                <div className={styles.derivLabel}>corpo</div>
                <div className={styles.derivText}>{post.copy}</div>
              </div>
            </div>
          ))}
          {!spCopies?.linkedin_posts?.length && !linkedinFallback.length && (
            <div className={styles.emptyState}>
              <div className={styles.emptyDesc}>Nenhum post LinkedIn gerado.</div>
            </div>
          )}
        </div>

        {/* ── 06 · Derivações (Reels, Shorts, Carrosséis, Stories) ─────── */}
        <div className={`${styles.panel} ${activeTab === 'derivacoes' ? styles.active : ''}`}>
          {reelsScripts.length > 0 && (
            <>
              <div className={styles.card} style={{ marginBottom: 8 }}>
                <div className={styles.cardTitle}>Reels Instagram</div>
                <div className={styles.cardSub}>{reelsScripts.length} roteiro(s)</div>
              </div>
              <div className={styles.grid2}>
                {reelsScripts.map((reel, i) => (
                  <div key={reel.id ?? i} className={styles.card}>
                    <div className={styles.cardTitle}>{reel.title}</div>
                    <div className={styles.cardSub}>reel · 30–60s</div>
                    <button
                      className={`${styles.copyBtn} ${copiedKey === `reel-${i}` ? styles.done : ''}`}
                      onClick={() => copy(reel.script, `reel-${i}`)}
                    >{copiedKey === `reel-${i}` ? 'Copiado ✓' : 'Copiar'}</button>
                    <div className={styles.derivItem}>
                      <div className={styles.derivLabel}>hook 3s</div>
                      <div className={styles.derivText}>{reel.hook3s}</div>
                    </div>
                    <div className={styles.derivItem}>
                      <div className={styles.derivLabel}>roteiro</div>
                      <div className={styles.derivText}>{reel.script}</div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {shorts.length > 0 && (
            <>
              <div className={styles.card} style={{ marginBottom: 8, marginTop: 16 }}>
                <div className={styles.cardTitle}>YouTube Shorts</div>
                <div className={styles.cardSub}>{shorts.length} roteiro(s)</div>
              </div>
              <div className={styles.grid2}>
                {shorts.map((s, i) => (
                  <div key={s.id ?? i} className={styles.card}>
                    <div className={styles.cardTitle}>{s.title}</div>
                    <div className={styles.cardSub}>short · 30–60s</div>
                    <button
                      className={`${styles.copyBtn} ${copiedKey === `short-${i}` ? styles.done : ''}`}
                      onClick={() => copy(s.script, `short-${i}`)}
                    >{copiedKey === `short-${i}` ? 'Copiado ✓' : 'Copiar'}</button>
                    <div className={styles.derivItem}>
                      <div className={styles.derivLabel}>hook 3s</div>
                      <div className={styles.derivText}>{s.hook3s}</div>
                    </div>
                    <div className={styles.derivItem}>
                      <div className={styles.derivLabel}>roteiro</div>
                      <div className={styles.derivText}>{s.script}</div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {carousels.length > 0 && carousels.map((carousel, i) => (
            <div key={carousel.id ?? i} className={styles.card} style={{ marginTop: 16 }}>
              <div className={styles.cardTitle}>{carousel.title}</div>
              <div className={styles.cardSub}>carrossel · {carousel.slides?.length ?? 0} slides</div>
              <button
                className={`${styles.copyBtn} ${copiedKey === `car-${i}` ? styles.done : ''}`}
                onClick={() => copy(carousel.caption, `car-${i}`)}
              >{copiedKey === `car-${i}` ? 'Copiado ✓' : 'Copiar legenda'}</button>
              {(carousel.slides ?? []).map((slide, si) => (
                <div key={si} className={styles.derivItem}>
                  <div className={styles.derivLabel}>slide {slide.slideNumber}</div>
                  <div className={styles.derivText}>
                    <strong style={{ color: '#eae4dc' }}>{slide.heading}</strong>
                    {'\n'}{slide.body}
                  </div>
                </div>
              ))}
            </div>
          ))}

          {storiesIdeas.length > 0 && (
            <div className={styles.card} style={{ marginTop: 16 }}>
              <div className={styles.cardTitle}>Stories da Semana</div>
              <div className={styles.cardSub}>{storiesIdeas.length} sugestões</div>
              {storiesIdeas.map((story, i) => (
                <div key={story.id ?? i} className={styles.derivItem}>
                  <div className={styles.derivLabel}>{story.day} — {story.angle}</div>
                  <div className={styles.derivText}>{story.copy}</div>
                  {story.interactiveElement && (
                    <div className={styles.derivMeta}>🎯 {story.interactiveElement}</div>
                  )}
                </div>
              ))}
            </div>
          )}

          {!reelsScripts.length && !shorts.length && !carousels.length && !storiesIdeas.length && (
            <div className={styles.emptyState}>
              <div className={styles.emptyDesc}>Derivações não disponíveis.</div>
            </div>
          )}
        </div>

      </>)}

      {/* ── partial error note ─────────────────────────────────────── */}
      {partialError && !isGenerating && (
        <div className={styles.partialErrorNote} style={{ marginTop: 16 }}>
          ⚠ Erros parciais: {partialError}
        </div>
      )}

      {/* ── bottom bar ─────────────────────────────────────────────── */}
      <div className={styles.actionBar}>
        <div className={styles.actionBarLeft}>
          <button className={styles.backBtn} onClick={onBack} disabled={isGenerating}>
            ← Publicação
          </button>
        </div>
        <button
          className={styles.nextBtn}
          onClick={onNext}
          disabled={isGenerating || !hasPackage}
          title={!hasPackage ? 'Aguarde a geração' : 'Ir para o roteiro YouTube'}
        >{isGenerating ? 'Gerando…' : 'Roteiro YouTube →'}</button>
      </div>

      {/* ── approve bar (sticky bottom) ────────────────────────────── */}
      {hasPackage && !isGenerating && (
        <div className={styles.approveBar}>
          <button
            className={styles.approveBtn}
            onClick={handleApprove}
            disabled={isApproving}
            title="Agendar posts sociais e disparar pipeline de vídeo"
          >✓ Distribuir Pacote</button>
        </div>
      )}

      {/* ── approve overlay (progresso por etapa) ──────────────────── */}
      {(isApproving || approveResult) && (
        <div className={styles.approveOverlay} role="dialog" aria-modal="true" aria-label="Aprovação do pacote">
          <div className={styles.approveModal}>
            <div className={styles.approveModalTitle}>
              {isApproving ? 'Distribuindo pacote…' : approveResult?.errors.length ? 'Distribuído com erros' : '✓ Pacote distribuído!'}
            </div>
            <div className={styles.approveModalSub}>
              {isApproving ? 'aguarde · as etapas rodam em paralelo' : approveResult?.approved_at ? new Date(approveResult.approved_at).toLocaleString('pt-BR') : ''}
            </div>

            <div className={styles.approveSteps}>
              {/* Texto social */}
              <div className={`${styles.approveStep} ${
                isApproving && !approveResult ? styles.stepRunning :
                approveStepText === 'ok'      ? styles.stepDone    :
                approveStepText === 'error'   ? styles.stepError   :
                styles.stepSkipped
              }`}>
                {isApproving && !approveResult ? <div className={styles.stepSpinner} /> :
                 approveStepText === 'ok'      ? <span className={styles.stepIcon}>✓</span> :
                 approveStepText === 'error'   ? <span className={styles.stepIcon}>✗</span> :
                                                 <span className={styles.stepIcon}>—</span>}
                <div className={styles.stepBody}>
                  <div className={styles.stepLabel}>LinkedIn & Threads</div>
                  {approveDetailText && (
                    <div className={`${styles.stepDetail} ${approveStepText === 'ok' ? styles.detailOk : approveStepText === 'error' ? styles.detailError : ''}`}>
                      {approveDetailText}
                    </div>
                  )}
                </div>
              </div>

              {/* Pipeline de vídeo */}
              <div className={`${styles.approveStep} ${
                isApproving && !approveResult ? styles.stepRunning :
                approveStepVideo === 'ok'      ? styles.stepDone    :
                approveStepVideo === 'error'   ? styles.stepError   :
                styles.stepSkipped
              }`}>
                {isApproving && !approveResult ? <div className={styles.stepSpinner} /> :
                 approveStepVideo === 'ok'      ? <span className={styles.stepIcon}>✓</span> :
                 approveStepVideo === 'error'   ? <span className={styles.stepIcon}>✗</span> :
                                                  <span className={styles.stepIcon}>—</span>}
                <div className={styles.stepBody}>
                  <div className={styles.stepLabel}>YouTube & Reels</div>
                  {approveDetailVideo && (
                    <div className={`${styles.stepDetail} ${approveStepVideo === 'ok' ? styles.detailOk : approveStepVideo === 'error' ? styles.detailError : ''}`}>
                      {approveDetailVideo}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Banner resultado */}
            {approveResult && (
              <div className={`${styles.approveResultBanner} ${
                approveResult.errors.length ? styles.bannerPartial : styles.bannerSuccess
              }`}>
                {approveResult.errors.length
                  ? `⚠ Distribuído com ${approveResult.errors.length} erro(s)`
                  : '✓ Pacote distribuído com sucesso!'}
              </div>
            )}

            {!isApproving && (
              <button
                className={styles.approveCloseBtn}
                onClick={() => { setApproveResult(null); if (!approveResult?.errors.length) onNext(); }}
              >
                {approveResult?.errors.length ? 'Fechar' : 'Continuar →'}
              </button>
            )}
          </div>
        </div>
      )}

    </div></div>
  );
}
