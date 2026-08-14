/* ============================================================
   ArticleTab.tsx — Aba 2: Gerar artigo + Publicar
   Substitui GenerateTab + PublishTab com fluxo unificado.
   Ao publicar, chama onPublished(url) e dispara geração do
   pacote de conteúdo em background via publish/route.ts.
   ============================================================ */
'use client';

import { useState, useMemo, useEffect } from 'react';
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
  onPublished: (url: string, packageAlreadyStarted?: boolean) => void;
}

interface PublishedArticle {
  id: string;
  title: string;
  slug: string;
  content: string;
  category: string;
  language: 'pt-BR' | 'en';
  publishedAt?: string;
  coverImage?: string;
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
  // Marcam edição manual: enquanto false, os campos continuam se auto-preenchendo
  // conforme o artigo é gerado. Depois que o usuário digita, paramos de sobrescrever.
  const [titleTouched, setTitleTouched] = useState(false);
  const [slugTouched, setSlugTouched] = useState(false);
  const [publishStatus, setPublishStatus] = useState<PublishStatus>('idle');
  const [publishError, setPublishError] = useState('');
  const [publishedArticles, setPublishedArticles] = useState<PublishedArticle[]>([]);
  const [loadingArticles, setLoadingArticles] = useState(false);
  const [resumingArticle, setResumingArticle] = useState<string | null>(null);
  const [resumeError, setResumeError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoadingArticles(true);
    fetch(`/api/csm/articles?language=${draft.language}`)
      .then(async (response) => {
        if (!response.ok) return;
        const data = await response.json();
        if (!cancelled) setPublishedArticles(data.articles ?? []);
      })
      .catch(() => undefined)
      .finally(() => { if (!cancelled) setLoadingArticles(false); });
    return () => { cancelled = true; };
  }, [draft.language]);

  /**
   * Preenchimento automático de título/slug/tempo de leitura.
   *
   * O título vinha só do bloco `META:` emitido no fim do artigo — se o modelo
   * não emitisse o META (ou o JSON viesse quebrado), os campos ficavam vazios e
   * o botão de publicar seguia bloqueado sem explicação. Aqui usamos uma cadeia
   * de fallback e só paramos de auto-preencher depois que o usuário edita.
   */
  useEffect(() => {
    const fromMeta  = draft.suggestedTitle?.trim();
    const fromPauta = draft.pauta?.titulo?.trim();
    // Último recurso: primeiro heading markdown do próprio conteúdo
    const fromHeading = draft.generatedContent.match(/^#{1,3}\s+(.+)$/m)?.[1]?.trim();
    const resolved = fromMeta || fromPauta || fromHeading || '';

    if (!titleTouched && resolved && resolved !== title) setTitle(resolved);
    if (!slugTouched) {
      const resolvedSlug = draft.suggestedSlug?.trim() || (resolved ? slugify(resolved) : '');
      if (resolvedSlug && resolvedSlug !== slug) setSlug(resolvedSlug);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft.suggestedTitle, draft.suggestedSlug, draft.pauta?.titulo, draft.generatedContent, titleTouched, slugTouched]);

  // Tempo de leitura acompanha o texto até o usuário mexer nele manualmente
  useEffect(() => {
    if (draft.estimatedReadTime) setReadTime(draft.estimatedReadTime);
  }, [draft.estimatedReadTime]);

  const isEmpty = !draft.generatedContent.trim();
  const wordCount = draft.generatedContent.trim().split(/\s+/).filter(Boolean).length;
  const charCount = draft.generatedContent.length;
  const rt = useMemo(() => estimateReadTime(draft.generatedContent), [draft.generatedContent]);

  const isTitleValid = title.length > 0 && title.length <= 150;
  const isSlugValid  = /^[a-z0-9-]+$/.test(slug) && slug.length > 0 && slug.length <= 100;
  const isCoverValid = coverImage.startsWith('https://');
  const canPublish   = isTitleValid && isSlugValid && isCoverValid && !isEmpty && publishStatus !== 'published';

  const handleTitleChange = (val: string) => {
    setTitleTouched(true);
    setTitle(val);
    if (!slugTouched) setSlug(slugify(val));
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
              // Não sobrescreve o que o usuário já editou à mão; o efeito de
              // auto-preenchimento cuida do resto a partir do draft.
              if (!titleTouched && parsed.title) setTitle(parsed.title);
              if (!slugTouched  && parsed.slug)  setSlug(parsed.slug);
              if (parsed.readTime) setReadTime(parsed.readTime);
              updateDraft({
                ...(parsed.title    ? { suggestedTitle: parsed.title } : {}),
                ...(parsed.slug     ? { suggestedSlug: parsed.slug } : {}),
                ...(parsed.readTime ? { estimatedReadTime: parsed.readTime } : {}),
              });
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

  const handleResumePackage = (article: PublishedArticle) => {
    setResumingArticle(article.id);
    setResumeError('');

    const pauta = draft.pauta ?? {
      titulo: article.title,
      subtitulo: '',
      tese: 'Desenvolver uma explicação prática e rigorosa a partir do artigo publicado.',
      publico: 'Líderes e profissionais que precisam compreender o tema.',
      objetivo_aprendizado: 'Compreender e aplicar os conceitos principais do artigo.',
      hardskills: [],
      duracao_alvo: '8 min',
      serie: 'conteudo-tecnico',
      tipo_artigo: 'tecnico' as const,
      nivel_tecnico: 'medio' as const,
    };
    const articleUrl = `/${article.language}/blog/${article.slug}`;

    // Navega JÁ para a aba Pacote com o estado "gerando" — a tela de progresso
    // e o polling do Firestore assumem a partir daí. Antes, o botão ficava
    // preso em "Gerando..." por vários minutos sem nenhum outro feedback.
    updateDraft({
      pauta,
      topic: article.title,
      generatedContent: article.content,
      suggestedTitle: article.title,
      suggestedSlug: article.slug,
      publishedArticleUrl: articleUrl,
      packageStatus: 'generating',
      packageStartedAt: Date.now(),
      workflowStage: 'package_generating',
      packageError: '',
    });
    onPublished(articleUrl, true);

    // Geração continua em background; a rota persiste o resultado na sessão e
    // o polling do ReviewTab o captura mesmo que esta promise nunca resolva
    // (ex.: instância reciclada no meio) — o estado fica no Firestore.
    void fetch('/api/csm/package', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        pauta,
        chatTranscript: `Artigo publicado retomado: ${article.title}`,
        category: article.category || draft.category,
        language: article.language,
        sessionId,
        articleContent: article.content,
      }),
    }).catch(() => undefined).finally(() => setResumingArticle(null));
  };

  // A lista de retomar só domina a tela quando o usuário chegou SEM projeto
  // ativo (sem pauta e sem conteúdo) — nesse caso ela é o ponto de entrada.
  // Com projeto em andamento, ela fica colapsada para o editor ter espaço.
  const hasActiveProject = Boolean(draft.pauta?.titulo || draft.generatedContent.trim());

  return (
    <div className={styles.container}>
      <details open={!hasActiveProject} style={{ margin: '12px 16px 0', border: '1px solid rgba(30,30,30,0.1)', borderRadius: '12px', background: '#ffffff' }}>
        <summary style={{ cursor: 'pointer', padding: '12px 16px', color: '#d97706', fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.08em', userSelect: 'none', listStyle: 'none', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '0.85rem' }}>📂</span>
          RETOMAR ARTIGO PUBLICADO
          <span style={{ color: '#8a8a8a', fontWeight: 500, textTransform: 'none', letterSpacing: 0 }}>
            {loadingArticles ? '(carregando...)' : `(${publishedArticles.length} no blog)`}
          </span>
          <span style={{ marginLeft: 'auto', color: '#a8a8a8', fontSize: '0.7rem', fontWeight: 500, textTransform: 'none', letterSpacing: 0 }}>clique para abrir/fechar</span>
        </summary>
        <div style={{ padding: '0 16px 14px' }}>
          <div style={{ color: '#6b6b6b', fontSize: '0.8rem', marginBottom: '10px' }}>Use esta lista para gerar o roteiro e o pacote de um artigo que já está no blog — sem passar pelo CMO.</div>
          {loadingArticles ? <span style={{ color: '#8a8a8a', fontSize: '0.8rem' }}>Carregando artigos...</span> : publishedArticles.length === 0 ? <span style={{ color: '#8a8a8a', fontSize: '0.8rem' }}>Nenhum artigo publicado encontrado.</span> : (
            <div style={{ display: 'grid', gap: '8px' }}>
              {publishedArticles.map((article) => (
                <div key={article.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', padding: '8px 10px', borderRadius: '8px', background: 'rgba(30,30,30,0.03)' }}>
                  <div style={{ minWidth: 0 }}><div style={{ color: '#1e1e1e', fontSize: '0.85rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{article.title}</div><div style={{ color: '#8a8a8a', fontSize: '0.72rem' }}>/{article.slug}</div></div>
                  <button type="button" onClick={() => void handleResumePackage(article)} disabled={resumingArticle !== null} style={{ flexShrink: 0, padding: '7px 11px', border: '1px solid rgba(217,119,6,0.35)', borderRadius: '7px', background: 'rgba(217,119,6,0.1)', color: '#d97706', cursor: resumingArticle !== null ? 'wait' : 'pointer', fontSize: '0.75rem' }}>{resumingArticle === article.id ? 'Gerando...' : 'Gerar pacote'}</button>
                </div>
              ))}
            </div>
          )}
          {resumeError && <div style={{ color: '#dc2626', fontSize: '0.78rem', marginTop: '8px' }}>{resumeError}</div>}
        </div>
      </details>
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
          {genError && <span style={{ color: '#dc2626', fontSize: '0.8rem' }}>{genError}</span>}
          <button onClick={triggerGeneration} disabled={isGenerating} className={styles.generateBtn} type="button"
            style={{ background: isGenerating ? 'rgba(230,126,34,0.2)' : 'linear-gradient(135deg,#e67e22,#f39c12)', color: isGenerating ? '#d97706' : '#ffffff', padding: '10px 18px', borderRadius: '10px', fontWeight: 'bold', border: 'none', cursor: isGenerating ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', gap: '8px' }}>
            {isGenerating ? `${generatingPhase} (${elapsed}s)` : isEmpty ? 'Gerar com IA' : 'Regerar Artigo'}
          </button>
        </div>
      </div>

      {/* Title / Slug bar */}
      <div style={{ display: 'flex', gap: '16px', padding: '8px 16px', background: 'rgba(30,30,30,0.02)', borderBottom: '1px solid rgba(30,30,30,0.05)', flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: '280px', display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span style={{ color: '#6b6b6b', fontSize: '0.72rem', fontWeight: 'bold', minWidth: '48px' }}>TÍTULO:</span>
          <input type="text" value={title} onChange={(e) => handleTitleChange(e.target.value)}
            style={{ flex: 1, background: 'rgba(30,30,30,0.04)', border: '1px solid rgba(30,30,30,0.08)', color: '#1e1e1e', padding: '6px 10px', borderRadius: '6px', fontSize: '0.85rem', fontWeight: 600 }}
            placeholder={draft.topic || 'Título do artigo'} />
        </div>
        <div style={{ flex: 1, minWidth: '280px', display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span style={{ color: '#6b6b6b', fontSize: '0.72rem', fontWeight: 'bold', minWidth: '48px' }}>SLUG:</span>
          <input type="text" value={slug} onChange={(e) => { setSlugTouched(true); setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-_]+/g, '-')); }}
            style={{ flex: 1, background: 'rgba(30,30,30,0.04)', border: '1px solid rgba(30,30,30,0.08)', color: '#d97706', fontFamily: 'monospace', padding: '6px 10px', borderRadius: '6px', fontSize: '0.85rem' }}
            placeholder="url-amigavel" />
        </div>
      </div>

      {/* Editor + Preview */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Editor */}
        {(pane === 'editor' || pane === 'split') && (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', borderRight: pane === 'split' ? '1px solid rgba(30,30,30,0.06)' : 'none' }}>
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
                <div style={{ textAlign: 'center', padding: '60px 20px', color: '#6b6b6b' }}>
                  {isGenerating ? (
                    <div>
                      <div style={{ fontSize: '1rem', color: '#d97706', fontWeight: 'bold', marginBottom: '8px' }}>{generatingPhase || 'Gerando...'}</div>
                      <div style={{ fontSize: '0.85rem' }}>Pipeline: Crítico → Pesquisa (arXiv) → Redação</div>
                      <div style={{ fontSize: '0.8rem', marginTop: '4px', color: '#8a8a8a' }}>{elapsed}s decorridos — pode levar 3-8 min</div>
                    </div>
                  ) : (
                    <div>
                      <p style={{ fontSize: '1rem', color: '#1e1e1e', fontWeight: 600, marginBottom: '8px' }}>Nenhum artigo ainda</p>
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
        <div style={{ borderTop: '1px solid rgba(30,30,30,0.08)', background: 'rgba(30,30,30,0.02)', padding: '16px 20px', display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
          {/* Cover + ReadTime + Date */}
          <div style={{ flex: 2, minWidth: '280px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <span style={{ color: '#6b6b6b', fontSize: '0.72rem', fontWeight: 'bold', minWidth: '60px' }}>COVER:</span>
              <input type="text" value={coverImage} onChange={(e) => setCoverImage(e.target.value)}
                style={{ flex: 1, background: 'rgba(30,30,30,0.04)', border: '1px solid rgba(30,30,30,0.08)', color: '#1e1e1e', padding: '6px 10px', borderRadius: '6px', fontSize: '0.8rem' }}
                placeholder="https://..." disabled={publishStatus === 'published'} />
            </div>
            <div style={{ display: 'flex', gap: '16px' }}>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <span style={{ color: '#6b6b6b', fontSize: '0.72rem', fontWeight: 'bold' }}>LEITURA:</span>
                <input type="number" min={1} max={120} value={readTime}
                  onChange={(e) => { const v = parseInt(e.target.value,10)||1; setReadTime(v); updateDraft({ estimatedReadTime: v }); }}
                  style={{ width: '60px', background: 'rgba(30,30,30,0.04)', border: '1px solid rgba(30,30,30,0.08)', color: '#1e1e1e', padding: '6px 8px', borderRadius: '6px', fontSize: '0.8rem' }}
                  disabled={publishStatus === 'published'} />
                <span style={{ color: '#8a8a8a', fontSize: '0.72rem' }}>min</span>
              </div>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <span style={{ color: '#6b6b6b', fontSize: '0.72rem', fontWeight: 'bold' }}>DATA:</span>
                <input type="datetime-local" value={publishedAt} onChange={(e) => setPublishedAt(e.target.value)}
                  style={{ background: 'rgba(30,30,30,0.04)', border: '1px solid rgba(30,30,30,0.08)', color: '#1e1e1e', padding: '6px 8px', borderRadius: '6px', fontSize: '0.8rem' }}
                  disabled={publishStatus === 'published'} />
              </div>
            </div>
          </div>

          {/* Status + Publish Button */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', minWidth: '200px' }}>
            {publishStatus === 'error' && <div style={{ color: '#dc2626', fontSize: '0.8rem' }}>{publishError}</div>}
            {publishStatus === 'published' && (
              <div style={{ color: '#16a34a', fontSize: '0.85rem', fontWeight: 'bold' }}>
                ✓ Publicado — gerando pacote de conteúdo...
              </div>
            )}
            {publishStatus !== 'published' && (
              <button onClick={handlePublish} disabled={!canPublish || publishStatus === 'publishing'} type="button"
                style={{ padding: '12px 24px', borderRadius: '10px', background: canPublish ? 'linear-gradient(135deg,#e67e22,#d35400)' : 'rgba(30,30,30,0.12)', color: '#fff', fontWeight: 'bold', border: 'none', cursor: canPublish ? 'pointer' : 'not-allowed', fontSize: '0.95rem' }}>
                {publishStatus === 'publishing' ? 'Publicando...' : '🚀 Publicar Artigo'}
              </button>
            )}
            {publishStatus !== 'published' && !canPublish && (
              <span style={{ color: '#dc2626', fontSize: '0.72rem' }}>
                {isEmpty ? 'Gere ou cole o conteúdo do artigo primeiro.'
                  : !isTitleValid ? 'Preencha o título (até 150 caracteres).'
                  : !isSlugValid ? 'Slug inválido — use apenas letras minúsculas, números e hífens.'
                  : !isCoverValid ? 'A imagem de capa precisa ser uma URL https://.'
                  : 'Complete os campos acima para publicar.'}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
