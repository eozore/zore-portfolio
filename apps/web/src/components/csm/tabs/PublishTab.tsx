/* ============================================================
   PublishTab.tsx - Aba 3: Metadados, preview final e publicacao
   ============================================================ */
'use client';

import { useState } from 'react';
import type { DraftState, OutputFormat } from '../CsmDashboard';
import type { ArticleCategory } from '@/types/article';
import styles from './PublishTab.module.css';

interface PublishTabProps {
  draft: DraftState;
  updateDraft: (partial: Partial<DraftState>) => void;
  onBack: () => void;
  onNext?: () => void;
}

type PublishStatus = 'idle' | 'publishing' | 'published' | 'error';

function slugify(str: string): string {
  return str
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9\s-]/g, '')
    .trim()
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .slice(0, 100);
}

const CATEGORY_LABELS: Record<ArticleCategory, string> = {
  estatistica: 'Estatistica',
  ml: 'Machine Learning',
  ia: 'Inteligencia Artificial',
};

export default function PublishTab({ draft, updateDraft, onBack, onNext }: PublishTabProps) {
  const [title, setTitle] = useState(draft.suggestedTitle || '');
  const [slug, setSlug] = useState(draft.suggestedSlug || '');
  const [coverImage, setCoverImage] = useState('https://storage.googleapis.com/eozore-assets/covers/default.jpg');
  const [readTime, setReadTime] = useState(draft.estimatedReadTime);
  const [publishedAt, setPublishedAt] = useState(() => {
    const now = new Date();
    now.setSeconds(0, 0);
    return now.toISOString().slice(0, 16);
  });

  const [publishStatus, setPublishStatus] = useState<PublishStatus>('idle');
  const [publishError, setPublishError] = useState('');
  const [publishedUrl, setPublishedUrl] = useState('');
  const [exportLoading, setExportLoading] = useState<OutputFormat | null>(null);

  const handleTitleChange = (val: string) => {
    setTitle(val);
    const nextSlug = (!slug || slug === slugify(title)) ? slugify(val) : slug;
    if (nextSlug !== slug) {
      setSlug(nextSlug);
    }
    updateDraft({
      suggestedTitle: val,
      suggestedSlug: nextSlug,
    });
  };

  const handleSlugChange = (val: string) => {
    const sanitized = val.toLowerCase().replace(/[^a-z0-9-]/g, '');
    setSlug(sanitized);
    updateDraft({
      suggestedSlug: sanitized,
    });
  };

  const isSlugValid = /^[a-z0-9-]+$/.test(slug) && slug.length > 0 && slug.length <= 100;
  const isTitleValid = title.length > 0 && title.length <= 150;
  const isCoverValid = coverImage.startsWith('https://');
  const isReadTimeValid = Number.isInteger(readTime) && readTime >= 1 && readTime <= 120;
  const canPublish = isTitleValid && isSlugValid && isCoverValid && isReadTimeValid && draft.generatedContent.trim().length > 0;

  const handlePublish = async () => {
    if (!canPublish) return;
    setPublishStatus('publishing');
    setPublishError('');

    const publishedAtISO = new Date(publishedAt).toISOString();

    try {
      const res = await fetch('/api/csm/publish', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-csm-session': 'authenticated',
        },
        body: JSON.stringify({
          title,
          slug,
          content: draft.generatedContent,
          category: draft.category,
          language: draft.language,
          publishedAt: publishedAtISO,
          readTime,
          coverImage,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || data.errors?.[0]?.reason || `HTTP ${res.status}`);
      }

      setPublishedUrl(data.url);
      setPublishStatus('published');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Erro ao publicar';
      setPublishError(message);
      setPublishStatus('error');
    }
  };

  const [repurposeLoading, setRepurposeLoading] = useState(false);

  const handleRepurpose = async () => {
    if (draft.repurposedData) {
      onNext?.();
      return;
    }
    setRepurposeLoading(true);
    try {
      const res = await fetch('/api/csm/repurpose', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title,
          slug,
          content: draft.generatedContent,
          category: draft.category,
          language: draft.language,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Erro ao derivar');
      updateDraft({ repurposedData: data });
      onNext?.();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Erro ao derivar conteudo');
    } finally {
      setRepurposeLoading(false);
    }
  };

  const handleExport = async (format: OutputFormat) => {
    setExportLoading(format);
    try {
      const res = await fetch('/api/csm/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content: draft.generatedContent,
          title,
          format,
          category: draft.category,
          language: draft.language,
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Erro ao exportar');

      const blob = new Blob([data.output], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${slug || 'conteudo'}-${format}.txt`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: unknown) {
      console.error('[export]', err);
    } finally {
      setExportLoading(null);
    }
  };

  return (
    <div className={styles.container}>
      {/* Left - Metadata form */}
      <div className={styles.formCol}>
        <div className={styles.card}>
          <h2 className={styles.sectionTitle}>
            Metadados do Artigo
          </h2>

          {/* Title */}
          <div className={styles.field}>
            <label className={styles.fieldLabel} htmlFor="pub-title">Titulo</label>
            <input
              id="pub-title"
              type="text"
              value={title}
              onChange={(e) => handleTitleChange(e.target.value)}
              className={`${styles.fieldInput} ${!isTitleValid && title ? styles.fieldInputError : ''}`}
              placeholder="Titulo do artigo (max 150 chars)"
              maxLength={150}
              disabled={publishStatus === 'publishing' || publishStatus === 'published'}
            />
            <span className={styles.fieldHint}>{title.length}/150</span>
          </div>

          {/* Slug */}
          <div className={styles.field}>
            <label className={styles.fieldLabel} htmlFor="pub-slug">Slug</label>
            <div className={styles.slugInputWrapper}>
              <span className={styles.slugPrefix}>/{draft.language}/blog/</span>
              <input
                id="pub-slug"
                type="text"
                value={slug}
                onChange={(e) => handleSlugChange(e.target.value)}
                className={`${styles.fieldInputSlug} ${!isSlugValid && slug ? styles.fieldInputError : ''}`}
                placeholder="meu-artigo-slug"
                maxLength={100}
                disabled={publishStatus === 'publishing' || publishStatus === 'published'}
              />
            </div>
            {!isSlugValid && slug && (
              <span className={styles.fieldError}>Apenas letras minusculas, numeros e hifens</span>
            )}
          </div>

          {/* Cover Image */}
          <div className={styles.field}>
            <label className={styles.fieldLabel} htmlFor="pub-cover">Cover Image URL</label>
            <input
              id="pub-cover"
              type="text"
              value={coverImage}
              onChange={(e) => setCoverImage(e.target.value)}
              className={`${styles.fieldInput} ${!isCoverValid && coverImage ? styles.fieldInputError : ''}`}
              placeholder="https://..."
              disabled={publishStatus === 'publishing' || publishStatus === 'published'}
            />
            {!isCoverValid && coverImage && (
              <span className={styles.fieldError}>URL deve comecar com https://</span>
            )}
          </div>

          {/* Row: Category + Language */}
          <div className={styles.fieldRow}>
            <div className={styles.field}>
              <label className={styles.fieldLabel}>Categoria</label>
              <div className={styles.readonlyPill}>{CATEGORY_LABELS[draft.category]}</div>
            </div>
            <div className={styles.field}>
              <label className={styles.fieldLabel}>Idioma</label>
              <div className={styles.readonlyPill}>{draft.language}</div>
            </div>
          </div>

          {/* Row: ReadTime + PublishedAt */}
          <div className={styles.fieldRow}>
            <div className={styles.field}>
              <label className={styles.fieldLabel} htmlFor="pub-readtime">Tempo de leitura (min)</label>
              <input
                id="pub-readtime"
                type="number"
                min={1}
                max={120}
                value={readTime}
                onChange={(e) => {
                  const val = parseInt(e.target.value, 10) || 1;
                  setReadTime(val);
                  updateDraft({ estimatedReadTime: val });
                }}
                className={styles.fieldInputSmall}
                disabled={publishStatus === 'publishing' || publishStatus === 'published'}
              />
            </div>
            <div className={styles.field}>
              <label className={styles.fieldLabel} htmlFor="pub-date">Data de publicacao</label>
              <input
                id="pub-date"
                type="datetime-local"
                value={publishedAt}
                onChange={(e) => setPublishedAt(e.target.value)}
                className={styles.fieldInputSmall}
                disabled={publishStatus === 'publishing' || publishStatus === 'published'}
              />
            </div>
          </div>
        </div>

        {/* Export panel */}
        <div className={styles.card}>
          <h2 className={styles.sectionTitle}>
            Exportar Conteudo
          </h2>
          <p className={styles.exportDesc}>Baixe o conteudo formatado para outros canais</p>
          <div className={styles.exportBtns}>
            {[
              { format: 'blog' as OutputFormat, label: 'Blog JSON' },
              { format: 'youtube' as OutputFormat, label: 'YouTube Script' },
              { format: 'linkedin' as OutputFormat, label: 'LinkedIn Post' },
            ].map(({ format, label }) => (
              <button
                key={format}
                onClick={() => handleExport(format)}
                disabled={exportLoading !== null || !draft.generatedContent}
                className={styles.exportBtn}
                type="button"
              >
                {exportLoading === format && (
                  <span className={styles.btnSpinner} />
                )}
                {label}
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="13" height="13" className={styles.downloadIcon}>
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="7 10 12 15 17 10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Right - Status + Actions */}
      <div className={styles.actionCol}>
        <button onClick={onBack} className={styles.backBtn} type="button">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
            <path d="M19 12H5M12 5l-7 7 7 7" />
          </svg>
          Voltar ao Editor
        </button>

        <div className={`${styles.card} ${styles.publishCard}`}>
          <h2 className={styles.sectionTitle}>
            Publicar no Blog
          </h2>

          {/* Content preview */}
          <div className={styles.contentPreview}>
            <div className={styles.previewRow}>
              <span className={styles.previewKey}>Palavras</span>
              <span className={styles.previewVal}>
                {draft.generatedContent.trim().split(/\s+/).filter(Boolean).length.toLocaleString()}
              </span>
            </div>
            <div className={styles.previewRow}>
              <span className={styles.previewKey}>Chars</span>
              <span className={styles.previewVal}>{draft.generatedContent.length.toLocaleString()}</span>
            </div>
            <div className={styles.previewRow}>
              <span className={styles.previewKey}>Formato</span>
              <span className={styles.previewVal}>{draft.format}</span>
            </div>
            <div className={styles.previewRow}>
              <span className={styles.previewKey}>Leitura</span>
              <span className={styles.previewVal}>~{readTime} min</span>
            </div>
          </div>

          {/* Validation checklist */}
          <div className={styles.checklist}>
            {[
              { ok: isTitleValid, label: 'Titulo valido' },
              { ok: isSlugValid, label: 'Slug valido' },
              { ok: isCoverValid, label: 'Cover image HTTPS' },
              { ok: isReadTimeValid, label: 'Tempo de leitura valido' },
              { ok: draft.generatedContent.trim().length > 0, label: 'Conteudo nao vazio' },
            ].map(({ ok, label }) => (
              <div key={label} className={`${styles.checkItem} ${ok ? styles.checkOk : styles.checkFail}`}>
                <span className={styles.checkIcon}>{ok ? '\u2713' : '\u2717'}</span>
                {label}
              </div>
            ))}
          </div>

          {/* Status feedback */}
          {publishStatus === 'error' && (
            <div className={styles.errorBox}>
              {publishError}
            </div>
          )}

          {publishStatus === 'published' && (
            <div className={styles.successBox}>
              <div className={styles.successTitle}>Publicado com sucesso</div>
              <a
                href={publishedUrl}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.successLink}
              >
                {publishedUrl}
              </a>
              <button
                onClick={onNext}
                className={styles.repurposeActionBtn}
                type="button"
                style={{ marginTop: '12px', width: '100%', padding: '12px', borderRadius: '10px', background: '#7c3aed', color: '#fff', fontWeight: 'bold', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}
              >
                Criar Roteiro do YouTube &rarr;
              </button>
            </div>
          )}

          <button
            onClick={handlePublish}
            disabled={!canPublish || publishStatus === 'publishing' || publishStatus === 'published'}
            className={`${styles.publishBtn} ${publishStatus === 'published' ? styles.publishBtnDone : ''}`}
            type="button"
          >
            {publishStatus === 'publishing' ? (
              <>
                <span className={styles.btnSpinner} />
                Publicando...
              </>
            ) : publishStatus === 'published' ? (
              <>Publicado</>
            ) : (
              <>
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
                  <path d="M22 2L11 13" /><path d="M22 2L15 22 11 13 2 9l20-7z" />
                </svg>
                Publicar Artigo
              </>
            )}
          </button>

          {publishStatus !== 'published' && (
            <button
              onClick={onNext}
              disabled={!draft.generatedContent}
              type="button"
              style={{ marginTop: '12px', width: '100%', padding: '12px', borderRadius: '12px', background: 'rgba(124,58,237,0.15)', color: '#7c3aed', border: '1px solid #7c3aed', fontWeight: 'bold', cursor: 'pointer' }}
            >
              Avancar para Roteiro de Video &rarr;
            </button>
          )}

          {repurposeLoading && (
            <div style={{ textAlign: 'center', marginTop: '8px', color: '#a78bfa', fontSize: '0.85rem' }}>
              Gerando derivacoes...
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
