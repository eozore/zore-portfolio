/* ============================================================
   ArticleTab.tsx — Aba 2: Gerar artigo + Publicar
   Substitui GenerateTab + PublishTab com fluxo unificado.
   Ao publicar, chama onPublished(url) e dispara geração do
   pacote de conteúdo em background via publish/route.ts.
   ============================================================ */
'use client';

import { useState, useMemo } from 'react';
import type { DraftState } from '../CsmDashboard';
import styles from './GenerateTab.module.css';
import pubStyles from './PublishTab.module.css';
import RichArticleRenderer from '../RichArticleRenderer';

interface ArticleTabProps {
  draft: DraftState;
  updateDraft: (partial: Partial<DraftState>) => void;
  sessionId: string;
  onBack: () => void;
  /** Chamado após publicação bem-sucedida com a URL do artigo */
  onPublished: (url: string) => void;
}

type PublishStatus = 'idle' | 'publishing' | 'published' | 'error';
type Pane = 'editor' | 'preview' | 'split';

function estimateReadTime(text: string): number {
  return Math.max(1, Math.min(120, Math.round(text.trim().split(/\s+/).length / 200)));
}

function slugify(str: string): string {
  return str.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9\s-]/g, '').trim().replace(/\s+/g, '-').replace(/-+/g, '-').slice(0, 100);
}

const CATEGORY_LABELS: Record<string, string> = {
  estatistica: 'Estatística',
  ml: 'Machine Learning',
  ia: 'Inteligência Artificial',
};

export default function ArticleTab({ draft, updateDraft, sessionId, onBack, onPublished }: ArticleTabProps) {
  const [pane, setPane] = useState<Pane>('split');
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatingPhase, setGeneratingPhase] = useState('');
  const [elapsed, setElapsed] = useState(0);
  const [genError, setGenError] = useState('');

  // Publish state
  const [title, setTitle] = useState(draft.suggestedTitle || '');
  const [slug, setSlug] = useState(draft.suggestedSlug || '');
  const [coverImage, setCoverImage] = useState('https://storage.googleapis.com/eozore-assets/covers/default.jpg');
  const [readTime, setReadTime] = useState(draft.estimatedReadTime || 10);
  const [publishedAt, setPublishedAt] = useState(() => {
    const now = new Date(); now.setSeconds(0, 0);
    return now.toISOString().slice(0, 16);
  });
  const [publishStatus, setPublishStatus] = useState<PublishStatus>('idle');
  const [publishError, setPublishError] = useState('');

  const isEmpty = !draft.generatedContent.trim();
  const wordCount = draft.generatedContent.trim().split(/\s+/).filter(Boolean).length;
  const charCount = draft.generatedContent.length;
  const rt = useMemo(() => estimateReadTime(draft.generatedContent), [draft.generatedContent]);

  const isTitleValid = title.length > 0 && title.length <= 150;
  const isSlugValid  = /^[a-z0-9-]+$/.test(slug) && slug.length > 0 && slug.length <= 100;
  const isCoverValid = coverImage.startsWith('https://');
  const canPublish   = isTitleValid && isSlugValid && isCoverValid && !isEmpty && publishStatus !== 'published';

  const handleTitleChange = (val: string) => {
    setTitle(val);
    if (!slug || slug === slugify(title)) setSlug(slugify(val));
    updateDraft({ suggestedTitle: val, suggestedSlug: slugify(val) });
  };

  // ── Geração do artigo ────────────────────────────────────────────────────
  const triggerGeneration = async () => {
    setIsGenerating(true); setGenError(''); setElapsed(0);
    setGeneratingPhase('Inicializando agentes...');
    updateDraft({ generatedContent: '' });

    const start = Date.now();
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000);

    try {
      const res = await fetch('/api/csm/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic: draft.topic,
          context: draft.context,
          format: 'blog',
          category: draft.category,
          language: draft.language,
          sessionId,
        }),
      });
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
      setGeneratingPhase('Pesquisando e escrevendo artigo...');

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let current = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';
        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data: ')) continue;
          const jsonStr = trimmed.slice(6).trim();
          if (!jsonStr || jsonStr === '[DONE]') continue;
          try {
            const parsed = JSON.parse(jsonStr);
            if (parsed.type === 'content') {
              current += parsed.chunk;
              updateDraft({ generatedContent: current, estimatedReadTime: estimateReadTime(current) });
            } else if (parsed.type === 'replace') {
              current = parsed.content;
              updateDraft({ generatedContent: current, estimatedReadTime: estimateReadTime(current) });
            } else if (parsed.type === 'meta') {
              setTitle(parsed.title || title);
              setSlug(parsed.slug || slug);
              setReadTime(parsed.readTime || readTime);
              updateDraft({ suggestedTitle: parsed.title, suggestedSlug: parsed.slug, estimatedReadTime: parsed.readTime });
            } else if (parsed.type === 'error') {
              throw new Error(parsed.message);
            }
          } catch { /* skip incomplete lines */ }
        }
      }
    } catch (err: unknown) {
      setGenError(err instanceof Error ? err.message : 'Falha na geração');
    } finally {
      clearInterval(timer);
      setIsGenerating(false);
      setGeneratingPhase('');
    }
  };

  // ── Publicação do artigo ─────────────────────────────────────────────────
  const handlePublish = async () => {
    if (!canPublish) return;
    setPublishStatus('publishing'); setPublishError('');
    try {
      const res = await fetch('/api/csm/publish', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-csm-session': 'authenticated' },
        body: JSON.stringify({
          title,
          slug,
          content: draft.generatedContent,
          category: draft.category,
          language: draft.language,
          publishedAt: new Date(publishedAt).toISOString(),
          readTime,
          coverImage,
          // Passa pauta para disparar geração do pacote em background
          pauta: draft.pauta ?? null,
          sessionId,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || data.errors?.[0]?.reason || `HTTP ${res.status}`);
      setPublishStatus('published');
      onPublished(data.url);
    } catch (err: unknown) {
      setPublishError(err instanceof Error ? err.message : 'Erro ao publicar');
      setPublishStatus('error');
    }
  };

  return (
    <div className={styles.container}>
      {/* Toolbar */}
      <div className={styles.toolbar}>
        <div className={styles.toolbarLeft}>
          <button onClick={onBack} className={styles.backBtn} type="button">← Voltar</button>
          <div className={styles.paneToggle}>
            {(['editor', 'split', 'preview'] as Pane[]).map((p) => (
              <button key={p} onClick={() => setPane(p)}
                className={`${styles.paneBtn} ${pane === p ? styles.paneBtnActive : ''}`} type="button">
                <span className={styles.paneBtnLabel}>{p === 'editor' ? 'Editor' : p === 'split' ? 'Split' : 'Preview'}</span>
              </button>
            ))}
          </div>
        </div>
        <div className={styles.toolbarRight}>
          <div className={styles.stats}>
            <span className={styles.stat}><span className={styles.statVal}>{wordCount.toLocaleString()}</span><span className={styles.statKey}>palavras</span></span>
            <span className={styles.statSep} />
            <span className={styles.stat}><span className={styles.statVal}>~{rt} min</span><span className={styles.statKey}>leitura</span></span>
          </div>
          {genError && <span style={{ color: '#f87171', fontSize: '0.8rem' }}>{genError}</span>}
          <button onClick={triggerGeneration} disabled={isGenerating} className={styles.generateBtn} type="button"
            style={{ background: isGenerating ? 'rgba(230,126,34,0.2)' : 'linear-gradient(135deg,#e67e22,#f39c12)', color: isGenerating ? '#f39c12' : '#000', padding: '10px 18px', borderRadius: '10px', fontWeight: 'bold', border: 'none', cursor: isGenerating ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', gap: '8px' }}>
            {isGenerating ? `${generatingPhase} (${elapsed}s)` : isEmpty ? 'Gerar com IA' : 'Regerar Artigo'}
          </button>
        </div>
      </div>

      {/* Title / Slug bar */}
      <div style={{ display: 'flex', gap: '16px', padding: '8px 16px', background: 'rgba(255,255,255,0.02)', borderBottom: '1px solid rgba(255,255,255,0.05)', flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: '280px', display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span style={{ color: '#94a3b8', fontSize: '0.72rem', fontWeight: 'bold', minWidth: '48px' }}>TÍTULO:</span>
          <input type="text" value={title} onChange={(e) => handleTitleChange(e.target.value)}
            style={{ flex: 1, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: '#fff', padding: '6px 10px', borderRadius: '6px', fontSize: '0.85rem', fontWeight: 600 }}
            placeholder={draft.topic || 'Título do artigo'} />
        </div>
        <div style={{ flex: 1, minWidth: '280px', display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span style={{ color: '#94a3b8', fontSize: '0.72rem', fontWeight: 'bold', minWidth: '48px' }}>SLUG:</span>
          <input type="text" value={slug} onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-_]+/g, '-'))}
            style={{ flex: 1, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: '#fbbf24', fontFamily: 'monospace', padding: '6px 10px', borderRadius: '6px', fontSize: '0.85rem' }}
            placeholder="url-amigavel" />
        </div>
      </div>

      {/* Editor + Preview */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Editor */}
        {(pane === 'editor' || pane === 'split') && (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', borderRight: pane === 'split' ? '1px solid rgba(255,255,255,0.06)' : 'none' }}>
            <div className={styles.paneHeader}><span className={styles.paneHeaderLabel}>Markdown</span></div>
            <textarea className={styles.editor} value={draft.generatedContent}
              onChange={(e) => updateDraft({ generatedContent: e.target.value, estimatedReadTime: estimateReadTime(e.target.value) })}
              placeholder={isGenerating ? 'Gerando artigo...' : 'O conteúdo gerado aparecerá aqui...'}
              disabled={isGenerating} spellCheck={false} />
          </div>
        )}
        {/* Preview */}
        {(pane === 'preview' || pane === 'split') && (
          <div style={{ flex: 1, overflowY: 'auto', background: '#eae9e6' }}>
            <div style={{ maxWidth: '768px', margin: '0 auto', padding: '2rem 1rem' }}>
              {isEmpty ? (
                <div style={{ textAlign: 'center', padding: '60px 20px', color: '#94a3b8' }}>
                  {isGenerating ? (
                    <div>
                      <div style={{ fontSize: '1rem', color: '#f39c12', fontWeight: 'bold', marginBottom: '8px' }}>{generatingPhase || 'Gerando...'}</div>
                      <div style={{ fontSize: '0.85rem' }}>Pipeline: Crítico → Pesquisa (arXiv) → Redação</div>
                      <div style={{ fontSize: '0.8rem', marginTop: '4px', color: '#64748b' }}>{elapsed}s decorridos — pode levar 3-8 min</div>
                    </div>
                  ) : (
                    <div>
                      <p style={{ fontSize: '1rem', color: '#fff', marginBottom: '8px' }}>Artigo vazio</p>
                      <p style={{ fontSize: '0.85rem' }}>Clique em &quot;Gerar com IA&quot; para começar</p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="bg-[#f8f7f4] shadow rounded-2xl p-8 text-[#1e1e1e]">
                  <RichArticleRenderer content={draft.generatedContent} />
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Publish Panel */}
      {!isEmpty && (
        <div style={{ borderTop: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.02)', padding: '16px 20px', display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
          {/* Cover + ReadTime + Date */}
          <div style={{ flex: 2, minWidth: '280px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <span style={{ color: '#94a3b8', fontSize: '0.72rem', fontWeight: 'bold', minWidth: '60px' }}>COVER:</span>
              <input type="text" value={coverImage} onChange={(e) => setCoverImage(e.target.value)}
                style={{ flex: 1, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: '#fff', padding: '6px 10px', borderRadius: '6px', fontSize: '0.8rem' }}
                placeholder="https://..." disabled={publishStatus === 'published'} />
            </div>
            <div style={{ display: 'flex', gap: '16px' }}>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <span style={{ color: '#94a3b8', fontSize: '0.72rem', fontWeight: 'bold' }}>LEITURA:</span>
                <input type="number" min={1} max={120} value={readTime}
                  onChange={(e) => { const v = parseInt(e.target.value,10)||1; setReadTime(v); updateDraft({ estimatedReadTime: v }); }}
                  style={{ width: '60px', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: '#fff', padding: '6px 8px', borderRadius: '6px', fontSize: '0.8rem' }}
                  disabled={publishStatus === 'published'} />
                <span style={{ color: '#64748b', fontSize: '0.72rem' }}>min</span>
              </div>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <span style={{ color: '#94a3b8', fontSize: '0.72rem', fontWeight: 'bold' }}>DATA:</span>
                <input type="datetime-local" value={publishedAt} onChange={(e) => setPublishedAt(e.target.value)}
                  style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: '#fff', padding: '6px 8px', borderRadius: '6px', fontSize: '0.8rem' }}
                  disabled={publishStatus === 'published'} />
              </div>
            </div>
          </div>

          {/* Status + Publish Button */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', minWidth: '200px' }}>
            {publishStatus === 'error' && <div style={{ color: '#f87171', fontSize: '0.8rem' }}>{publishError}</div>}
            {publishStatus === 'published' && (
              <div style={{ color: '#4ade80', fontSize: '0.85rem', fontWeight: 'bold' }}>
                ✓ Publicado — gerando pacote de conteúdo...
              </div>
            )}
            {publishStatus !== 'published' && (
              <button onClick={handlePublish} disabled={!canPublish || publishStatus === 'publishing'} type="button"
                style={{ padding: '12px 24px', borderRadius: '10px', background: canPublish ? 'linear-gradient(135deg,#7c3aed,#6d28d9)' : 'rgba(124,58,237,0.2)', color: '#fff', fontWeight: 'bold', border: 'none', cursor: canPublish ? 'pointer' : 'not-allowed', fontSize: '0.95rem' }}>
                {publishStatus === 'publishing' ? 'Publicando...' : '🚀 Publicar Artigo'}
              </button>
            )}
            {!isTitleValid && <span style={{ color: '#f87171', fontSize: '0.72rem' }}>Título obrigatório</span>}
            {!isSlugValid && slug && <span style={{ color: '#f87171', fontSize: '0.72rem' }}>Slug inválido</span>}
          </div>
        </div>
      )}
    </div>
  );
}
