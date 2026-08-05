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
import styles from './PackageTab.module.css';

interface ReviewTabProps {
  draft: DraftState;
  updateDraft: (partial: Partial<DraftState>) => void;
  sessionId: string;
  onBack: () => void;
  onApproved: () => void;
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

const PACKAGE_STATUS_LABELS: Record<string, string> = {
  idle:       'Aguardando publicação',
  generating: 'Gerando pacote de conteúdo...',
  script_ready: 'Roteiro pronto para aprovação',
  ready:      'Pacote pronto para revisão',
  error:      'Erro na geração do pacote',
};

export default function ReviewTab({ draft, updateDraft, sessionId, onBack, onApproved }: ReviewTabProps) {
  const [activeTab, setActiveTab] = useState<SubTab>('roteiro');
  const [isApproving, setIsApproving] = useState(false);
  const [isGeneratingDerivatives, setIsGeneratingDerivatives] = useState(false);
  const [approveResult, setApproveResult] = useState<ApproveResult | null>(null);
  const [approveError, setApproveError] = useState('');

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

  // Poll Firestore para ver se o pacote ficou pronto
  useEffect(() => {
    if (!isGenerating || !sessionId) return;
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/csm/session?id=${sessionId}`);
        if (!res.ok) return;
        const data = await res.json();
        const d = data.draft;
        if (d?.manifestV2 || d?.repurposedData) {
          updateDraft({
            manifestV2:       d.manifestV2 ?? null,
            manifestHtml:     d.manifestHtml ?? '',
            thumbnails:       d.thumbnails ?? null,
            specialistCopies: d.specialistCopies ?? null,
            repurposedData:   d.repurposedData ?? null,
            youtubeScript:    d.youtubeScript ?? prevYoutubeScript(d.manifestV2),
            packageStatus:    d.packageStatus ?? (d.repurposedData ? 'ready' : 'script_ready'),
            workflowStage:    d.workflowStage ?? (d.repurposedData ? 'package_ready' : 'script_ready'),
          });
          clearInterval(interval);
        }
        setPollCount((c) => c + 1);
      } catch { /* silent */ }
    }, 8_000); // poll a cada 8s
    return () => clearInterval(interval);
  }, [isGenerating, sessionId, updateDraft]);

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
      updateDraft({
        repurposedData: data.repurposedData ?? null,
        youtubeScript: data.youtubeScript ?? draft.youtubeScript,
        packageStatus: 'ready',
        workflowStage: 'package_ready',
      });
    } catch (err) {
      setApproveError(err instanceof Error ? err.message : 'Falha ao gerar derivações');
    } finally {
      setIsGeneratingDerivatives(false);
    }
  }, [packageStatus, isGeneratingDerivatives, sessionId, updateDraft, draft.youtubeScript]);

  // ── Aprovação final: dispara pipeline TTS + HeyGen + render ─────────────
  const handleApprove = useCallback(async () => {
    if (!hasPackage || packageStatus !== 'ready' || isApproving) return;
    setIsApproving(true); setApproveError(''); setApproveResult(null);

    const pauta     = draft.pauta;
    const spLi      = (spCopies?.linkedin_posts ?? []) as SpecialistLinkedIn[];
    const spTh      = (spCopies?.threads ?? []) as SpecialistThread[];
    const rdPosts   = rd?.linkedinPosts ?? [];
    const reelItems = rd?.reelsScripts ?? [];
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

    const videoItems = reelItems.map((r, i) => ({
      id: (r as { id?: string }).id ?? `reel-${i}`,
      platform: 'instagram' as const, format: 'reel',
      title: (r as { title?: string }).title ?? `Reel ${i + 1}`,
      copy: (r as { script?: string }).script ?? '',
      scheduledAt: new Date().toISOString(), status: 'aprovado' as const,
    }));

    try {
      const res = await fetch('/api/csm/approve-package', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          textItems:     textItems.length  ? textItems  : undefined,
          videoItems:    videoItems.length ? videoItems : undefined,
          youtubeScript: hasYT ? (draft.youtubeScript || ytSegments.map((s) => s.script).join('\n\n')) : undefined,
          articleSlug,
          articleTitle,
          sessionId,
          csmSession: 'authenticated',
        }),
      });
      const result: ApproveResult = await res.json();
      setApproveResult(result);
      if (result.text.status !== 'error' && result.video.status !== 'error') {
        onApproved();
      }
    } catch (err) {
      setApproveError(err instanceof Error ? err.message : 'Falha na aprovação');
    } finally {
      setIsApproving(false);
    }
  }, [hasPackage, packageStatus, isApproving, draft, spCopies, rd, ytSegments, sessionId, onApproved]);

  const tabs: { id: SubTab; label: string; count?: number }[] = [
    { id: 'roteiro',    label: 'Roteiro',    count: ytSegments.length },
    { id: 'slides',     label: 'Slides' },
    { id: 'thumbnails', label: 'Thumbnails' },
    { id: 'linkedin',   label: 'LinkedIn',   count: linkedinPosts.length },
    { id: 'derivacoes', label: 'Derivações' },
  ];

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
              Roteiro + assets de apoio — pode levar 4-8 minutos
            </div>
            <div className={styles.elapsedLabel}>
              Polling {pollCount}x · atualiza automaticamente quando pronto
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
              ? 'Ocorreu um erro na geração. Volte para o Artigo e tente novamente.'
              : 'Publique o artigo primeiro. O pacote será gerado automaticamente.'}
          </div>
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
              {t.count !== undefined && t.count > 0 && (
                <span className={`${styles.badge} ${styles.badgeOrange}`}>{t.count}</span>
              )}
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
            {!thumbs ? (
              <div className={styles.emptyState}><div className={styles.emptyDesc}>Thumbnails não disponíveis.</div></div>
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
              <div className={styles.emptyState}><div className={styles.emptyDesc}>Copies LinkedIn não disponíveis.</div></div>
            ) : (
              (linkedinPosts as SpecialistLinkedIn[]).map((p, i) => (
                <div key={p.id ?? i} className={styles.card}>
                  <div className={styles.cardTitle}>Post #{i + 1}</div>
                  <div className={styles.segScript} style={{ whiteSpace: 'pre-wrap' }}>{p.hook}{'\n\n'}{p.copy}</div>
                  {p.hashtags && <div style={{ color: '#60a5fa', fontSize: '0.78rem', marginTop: '4px' }}>{p.hashtags}</div>}
                </div>
              ))
            )}
          </div>
        )}

        {/* Derivações */}
        {activeTab === 'derivacoes' && (
          <div className={styles.panel}>
            <div className={styles.card}>
              <div className={styles.cardTitle}>Resumo das Derivações</div>
              {[
                ['Reels',     rd?.reelsScripts?.length     ?? 0],
                ['Threads',   threads.length],
                ['Shorts YT', rd?.youtubeShorts?.length    ?? 0],
                ['Carrosséis',rd?.carousels?.length        ?? 0],
                ['Stories',   rd?.storiesIdeas?.length     ?? 0],
              ].map(([label, count]) => (
                <div key={label as string} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                  <span style={{ color: '#94a3b8', fontSize: '0.85rem' }}>{label as string}</span>
                  <span style={{ color: '#fff', fontWeight: 'bold', fontSize: '0.85rem' }}>{count as number}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </>)}

      {/* Barra de ação */}
      <div className={styles.actionBar} style={{ justifyContent: 'space-between', marginTop: '16px' }}>
        <button className={styles.backBtn} onClick={onBack}>← Artigo</button>

        {approveError && (
          <div style={{ color: '#f87171', fontSize: '0.8rem', padding: '8px' }}>{approveError}</div>
        )}

        {approveResult && (
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <span style={{ color: '#4ade80', fontSize: '0.85rem', fontWeight: 'bold' }}>
              ✓ Pipeline disparado
            </span>
            {approveResult.errors?.length > 0 && (
              <span style={{ color: '#fbbf24', fontSize: '0.75rem' }}>
                ({approveResult.errors.length} erro(s) parcial(is))
              </span>
            )}
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
            background: approveResult ? 'rgba(74,222,128,0.15)' : !hasPackage || packageStatus !== 'ready' ? 'rgba(255,255,255,0.05)' : 'linear-gradient(135deg,#16a34a,#15803d)',
            color: approveResult ? '#4ade80' : !hasPackage || packageStatus !== 'ready' ? '#64748b' : '#fff',
          }}>
          {isApproving ? 'Aprovando...' : approveResult ? '✓ Aprovado' : '✅ Aprovar & Produzir Vídeo'}
        </button>}
      </div>

    </div></div>
  );
}
