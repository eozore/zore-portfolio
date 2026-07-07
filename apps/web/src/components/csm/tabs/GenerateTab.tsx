/* ============================================================
   GenerateTab.tsx — Aba 2: Editor Markdown + Preview ao vivo
   ============================================================ */
'use client';

import { useState, useMemo } from 'react';
import type { DraftState } from '../CsmDashboard';
import styles from './GenerateTab.module.css';
import RichArticleRenderer from '../RichArticleRenderer';

interface GenerateTabProps {
  draft: DraftState;
  updateDraft: (partial: Partial<DraftState>) => void;
  onBack: () => void;
  onNext: () => void;
  sessionId: string;
}

function estimateReadTime(text: string): number {
  const words = text.trim().split(/\s+/).length;
  return Math.max(1, Math.min(120, Math.round(words / 200)));
}

export default function GenerateTab({ draft, updateDraft, onBack, onNext, sessionId }: GenerateTabProps) {
  const [activePane, setActivePane] = useState<'editor' | 'blocks' | 'preview' | 'split'>('split');
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState('');
  const [generatingPhase, setGeneratingPhase] = useState<string>('');
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  const handleEditBlockContent = (id: string, newContent: string) => {
    if (!draft.blocks) return;
    const nextBlocks = draft.blocks.map((block) =>
      block.id === id ? { ...block, content: newContent } : block
    );
    const { parseBlocksToMarkdown } = require('@/lib/blockParser');
    const newMd = parseBlocksToMarkdown(nextBlocks);
    
    updateDraft({
      generatedContent: newMd,
      blocks: nextBlocks,
    });
  };

  const handleDeleteBlock = (id: string) => {
    if (!draft.blocks) return;
    const confirmDelete = window.confirm('Deseja excluir este bloco?');
    if (!confirmDelete) return;

    const nextBlocks = draft.blocks.filter((block) => block.id !== id);
    const { parseBlocksToMarkdown } = require('@/lib/blockParser');
    const newMd = parseBlocksToMarkdown(nextBlocks);
    
    updateDraft({
      generatedContent: newMd,
      blocks: nextBlocks,
    });
  };

  const handleMoveBlock = (idx: number, direction: 'up' | 'down') => {
    if (!draft.blocks) return;
    const nextBlocks = [...draft.blocks];
    const targetIdx = direction === 'up' ? idx - 1 : idx + 1;
    
    if (targetIdx < 0 || targetIdx >= nextBlocks.length) return;
    
    const temp = nextBlocks[idx];
    nextBlocks[idx] = nextBlocks[targetIdx];
    nextBlocks[targetIdx] = temp;
    
    const { parseBlocksToMarkdown } = require('@/lib/blockParser');
    const newMd = parseBlocksToMarkdown(nextBlocks);
    
    updateDraft({
      generatedContent: newMd,
      blocks: nextBlocks,
    });
  };

  const handleDragDropBlock = (draggedIdx: number, targetIdx: number) => {
    if (!draft.blocks) return;
    const nextBlocks = [...draft.blocks];
    const draggedBlock = nextBlocks[draggedIdx];
    nextBlocks.splice(draggedIdx, 1);
    nextBlocks.splice(targetIdx, 0, draggedBlock);

    const { parseBlocksToMarkdown } = require('@/lib/blockParser');
    const newMd = parseBlocksToMarkdown(nextBlocks);

    updateDraft({
      generatedContent: newMd,
      blocks: nextBlocks,
    });
  };

  const readTime = useMemo(() => estimateReadTime(draft.generatedContent), [draft.generatedContent]);
  const charCount = draft.generatedContent.length;
  const wordCount = draft.generatedContent.trim().split(/\s+/).filter(Boolean).length;

  const handleContentChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    updateDraft({
      generatedContent: e.target.value,
      estimatedReadTime: estimateReadTime(e.target.value),
    });
  };

  const triggerGeneration = async () => {
    setIsGenerating(true);
    setError('');
    setGeneratingPhase('Inicializando agentes...');
    setElapsedSeconds(0);
    updateDraft({ generatedContent: '' });

    // Elapsed timer
    const startTime = Date.now();
    const timer = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);

    try {
      const response = await fetch('/api/csm/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          topic: draft.topic,
          context: draft.context,
          format: 'blog',
          category: draft.category,
          language: draft.language,
          sessionId,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      if (!response.body) {
        throw new Error('Sem corpo de resposta do servidor de geracao.');
      }

      // Connection established: Python agent is now running Critic + Research phases
      setGeneratingPhase('Analisando pauta e pesquisando papers...');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let currentContent = '';

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
              currentContent += parsed.chunk;
              // Detect pipeline phase from streaming content
              if (!currentContent && parsed.chunk) {
                setGeneratingPhase('Escrevendo artigo...');
              }
              if (currentContent.length < 200) {
                setGeneratingPhase('Escrevendo artigo...');
              }
              updateDraft({
                generatedContent: currentContent,
                estimatedReadTime: estimateReadTime(currentContent),
              });
            } else if (parsed.type === 'replace') {
              currentContent = parsed.content;
              updateDraft({
                generatedContent: currentContent,
                estimatedReadTime: estimateReadTime(currentContent),
              });
            } else if (parsed.type === 'meta') {
              updateDraft({
                suggestedTitle: parsed.title,
                suggestedSlug: parsed.slug,
                estimatedReadTime: parsed.readTime,
              });
            } else if (parsed.type === 'error') {
              throw new Error(parsed.message);
            }
          } catch (e) {
            // Ignore parse errors on incomplete chunk lines
          }
        }
      }

      // Fallback Client-Side parsing (handles thinking blocks and META blocks)
      let finalContent = currentContent || '';
      // Strip LLM raw thinking blocks
      finalContent = finalContent.replace(/<think>[\s\S]*?<\/think>/g, '').trim();

      // Match META block anywhere in final content (removing $ and m flags for safety)
      const metaMatch = finalContent.match(/META:\s*(\{[^}]+\})/);
      let title = '';
      let slug = '';
      let readTime = 10;

      if (metaMatch) {
        try {
          const cleanedMeta = metaMatch[1].replace(/,\s*([}\]])/g, '$1');
          const meta = JSON.parse(cleanedMeta);
          title = meta.title || '';
          
          const slugify = (str: string) => str.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9\s-]/g, '').trim().replace(/\s+/g, '-').replace(/-+/g, '-').slice(0, 100);
          slug = meta.slug ? slugify(meta.slug) : (title ? slugify(title) : '');
          readTime = Number.isInteger(meta.readTime) ? meta.readTime : 10;
        } catch (e) {
          console.warn('[csm/generate] Client-side META parsing failed:', e);
        }
      }

      // Always strip the META: {...} block globally to guarantee it never leaks in the editor/rendered output
      const cleanedContent = finalContent.replace(/\n?META:\s*\{[^}]+\}\s*/g, '').trimEnd();

      const updateData: Partial<DraftState> = {
        generatedContent: cleanedContent
      };
      if (title) updateData.suggestedTitle = title;
      if (slug) updateData.suggestedSlug = slug;
      if (metaMatch) updateData.estimatedReadTime = readTime;

      updateDraft(updateData);
    } catch (err: any) {
      console.error('[GenerateTab] Generation failed:', err);
      setError(err.message || 'Falha na conexao ou geracao do artigo.');
    } finally {
      clearInterval(timer);
      setIsGenerating(false);
      setGeneratingPhase('');
    }
  };

  const isEmpty = !draft.generatedContent.trim();

  return (
    <div className={styles.container}>
      {/* Toolbar */}
      <div className={styles.toolbar}>
        <div className={styles.toolbarLeft}>
          <button onClick={onBack} className={styles.backBtn} type="button">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
              <path d="M19 12H5M12 5l-7 7 7 7" />
            </svg>
            Voltar
          </button>

          <div className={styles.paneToggle}>
            {(['editor', 'blocks', 'split', 'preview'] as const).map((pane) => (
              <button
                key={pane}
                onClick={() => setActivePane(pane)}
                className={`${styles.paneBtn} ${activePane === pane ? styles.paneBtnActive : ''}`}
                type="button"
                title={pane === 'editor' ? 'Apenas Editor' : pane === 'blocks' ? 'Blocos DSL' : pane === 'preview' ? 'Apenas Preview' : 'Split View'}
              >
                {pane === 'editor' && (
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                  </svg>
                )}
                {pane === 'blocks' && (
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
                    <rect x="3" y="3" width="7" height="9" rx="1" />
                    <rect x="14" y="3" width="7" height="5" rx="1" />
                    <rect x="14" y="12" width="7" height="9" rx="1" />
                    <rect x="3" y="16" width="7" height="5" rx="1" />
                  </svg>
                )}
                {pane === 'split' && (
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
                    <rect x="3" y="3" width="18" height="18" rx="2" />
                    <line x1="12" y1="3" x2="12" y2="21" />
                  </svg>
                )}
                {pane === 'preview' && (
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                )}
                <span className={styles.paneBtnLabel}>
                  {pane === 'editor' ? 'Editor' : pane === 'blocks' ? 'Blocos DSL' : pane === 'split' ? 'Split' : 'Preview'}
                </span>
              </button>
            ))}
          </div>
        </div>

        <div className={styles.toolbarRight}>
          {/* Stats */}
          <div className={styles.stats}>
            <span className={styles.stat}>
              <span className={styles.statVal}>{wordCount.toLocaleString()}</span>
              <span className={styles.statKey}>palavras</span>
            </span>
            <span className={styles.statSep} />
            <span className={styles.stat}>
              <span className={styles.statVal}>{charCount.toLocaleString()}</span>
              <span className={styles.statKey}>chars</span>
            </span>
            <span className={styles.statSep} />
            <span className={styles.stat}>
              <span className={styles.statVal}>~{readTime} min</span>
              <span className={styles.statKey}>leitura</span>
            </span>
          </div>

          {error && (
            <div className={styles.errorBanner} style={{ color: '#f87171', fontSize: '0.8rem', marginRight: '16px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              {error}
            </div>
          )}

          <button
            onClick={triggerGeneration}
            disabled={isGenerating}
            className={`${styles.generateBtn} ${isGenerating ? styles.generateBtnLoading : ''}`}
            type="button"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '10px 18px',
              borderRadius: '10px',
              background: isGenerating ? 'rgba(230, 126, 34, 0.2)' : 'linear-gradient(135deg, #e67e22, #f39c12)',
              color: isGenerating ? '#f39c12' : '#000',
              fontWeight: 'bold',
              border: 'none',
              cursor: isGenerating ? 'not-allowed' : 'pointer',
              marginRight: '12px',
              transition: 'all 0.2s ease-in-out',
            }}
          >
            {isGenerating ? (
              <>
                <span className={styles.btnSpinner} />
                Gerando...
              </>
            ) : isEmpty ? (
              <>
                Gerar com IA
              </>
            ) : (
              <>
                Regerar Artigo
              </>
            )}
          </button>

          <button
            onClick={onNext}
            disabled={isEmpty || isGenerating}
            className={styles.nextBtn}
            type="button"
          >
            Publicar
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      </div>

      {/* Suggested title/slug (Fully Editable) */}
      <div className={styles.suggestBar} style={{ display: 'flex', gap: '20px', padding: '10px 16px', background: 'rgba(255,255,255,0.02)', borderBottom: '1px solid rgba(255,255,255,0.05)', flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: '280px', display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span className={styles.suggestKey} style={{ color: '#94a3b8', fontSize: '0.72rem', fontWeight: 'bold', minWidth: '50px' }}>TÍTULO:</span>
          <input
            type="text"
            value={draft.suggestedTitle || ''}
            onChange={(e) => updateDraft({ suggestedTitle: e.target.value })}
            style={{
              flex: 1,
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.08)',
              color: '#ffffff',
              padding: '6px 10px',
              borderRadius: '6px',
              fontSize: '0.85rem',
              fontWeight: 600,
              outline: 'none',
            }}
            placeholder={draft.topic || "Digite o título do artigo..."}
          />
        </div>
        <div style={{ flex: 1, minWidth: '280px', display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span className={styles.suggestKey} style={{ color: '#94a3b8', fontSize: '0.72rem', fontWeight: 'bold', minWidth: '50px' }}>SLUG:</span>
          <input
            type="text"
            value={draft.suggestedSlug || ''}
            onChange={(e) => {
              const sanitized = e.target.value.toLowerCase().replace(/[^a-z0-9-_]+/g, '-');
              updateDraft({ suggestedSlug: sanitized });
            }}
            style={{
              flex: 1,
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.08)',
              color: '#fbbf24',
              fontFamily: 'monospace',
              padding: '6px 10px',
              borderRadius: '6px',
              fontSize: '0.85rem',
              outline: 'none',
            }}
            placeholder="url-amigavel-do-artigo"
          />
        </div>
      </div>

      {/* Editor / Preview area */}
      <div
        className={`${styles.editorArea} ${
          activePane === 'editor' ? styles.editorOnly :
          activePane === 'preview' ? styles.previewOnly :
          activePane === 'blocks' ? styles.previewOnly :
          styles.splitView
        }`}
      >
        {/* Editor pane */}
        {(activePane === 'editor' || activePane === 'split') && (
          <div className={styles.editorPane}>
            <div className={styles.paneHeader}>
              <span className={styles.paneHeaderLabel}>Markdown</span>
              <div className={styles.paneHeaderDots}>
                <span style={{ background: '#f87171' }} />
                <span style={{ background: '#fbbf24' }} />
                <span style={{ background: '#34d399' }} />
              </div>
            </div>
            <textarea
              className={styles.editor}
              value={draft.generatedContent}
              onChange={handleContentChange}
              placeholder={isGenerating ? "O redator técnico (Writing Agent) está gerando o artigo em tempo real... aguarde..." : "O conteúdo gerado pela IA aparecerá aqui. Você pode editar livremente..."}
              spellCheck={false}
              disabled={isGenerating}
            />
          </div>
        )}

        {/* Preview pane */}
        {(activePane === 'preview' || activePane === 'split') && (
          <div className={styles.previewPane}>
            <div className={styles.paneHeader}>
              <span className={styles.paneHeaderLabel}>Preview</span>
            </div>
            <div className={styles.previewScroll}>
              {isEmpty ? (
                <div className={styles.previewEmpty} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '300px', gap: '16px', padding: '40px', textAlign: 'center' }}>
                  {isGenerating ? (
                    <>
                      <div className={styles.spinner} style={{
                        width: '48px',
                        height: '48px',
                        border: '3px solid rgba(230, 126, 34, 0.1)',
                        borderTopColor: '#e67e22',
                        borderRadius: '50%',
                        animation: 'spin 1s linear infinite'
                      }} />
                      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
                      <p style={{ color: '#f39c12', fontSize: '1rem', fontWeight: 'bold', margin: 0 }}>{generatingPhase || 'Inicializando...'}</p>
                      <p style={{ color: '#94a3b8', fontSize: '0.85rem', margin: 0 }}>Pipeline: Critico &rarr; Pesquisa (arXiv) &rarr; Redacao</p>
                      <p style={{ color: '#64748b', fontSize: '0.8rem', margin: 0 }}>Tempo decorrido: {elapsedSeconds}s &mdash; pode levar 3-8 minutos</p>
                    </>
                  ) : (
                    <>
                      <h3 style={{ color: '#fff', fontSize: '1.1rem', margin: 0 }}>O rascunho do artigo está vazio</h3>
                      <p style={{ color: '#cbd5e1', fontSize: '0.85rem', maxWidth: '360px', margin: 0 }}>Deixe o time de agentes de marketing (Research + Writing) pesquisar papers no arXiv e redigir a primeira versão com gráficos Mermaid e equações LaTeX.</p>
                      <button
                        onClick={triggerGeneration}
                        className={styles.bigGenerateBtn}
                        type="button"
                        style={{
                          marginTop: '8px',
                          padding: '12px 24px',
                          borderRadius: '12px',
                          background: 'linear-gradient(135deg, #e67e22, #f39c12)',
                          color: '#000',
                          fontWeight: 'bold',
                          border: 'none',
                          cursor: 'pointer',
                          boxShadow: '0 4px 20px rgba(230, 126, 34, 0.3)',
                          transition: 'transform 0.2s, opacity 0.2s',
                        }}
                      >
                        Gerar Artigo com IA
                      </button>
                    </>
                  )}
                </div>
              ) : (
                <div style={{ backgroundColor: '#eae9e6', padding: '2rem 1rem', minHeight: '100%' }}>
                  <div className="max-w-3xl mx-auto bg-[#f8f7f4] shadow-[0_4px_20px_rgba(0,0,0,0.06)] rounded-2xl p-6 md:p-12 text-[#1e1e1e]">
                    {/* Simulated Blog Header */}
                    <header className="mb-8 pb-8 border-b border-black/[0.08]">
                      <span className="inline-block px-3 py-1 text-xs font-semibold rounded bg-orange-100 text-orange-600 mb-4 uppercase tracking-wider">
                        {draft.category === 'estatistica' ? 'Estatística' : draft.category === 'ml' ? 'Machine Learning' : 'Inteligência Artificial'}
                      </span>
                      <h1 className="text-3xl md:text-4xl font-bold text-gray-900 leading-tight">
                        {draft.suggestedTitle || draft.topic || 'Rascunho de Artigo Técnico'}
                      </h1>
                      <div className="mt-4 flex items-center gap-4 text-sm text-gray-500">
                        <span>{new Date().toLocaleDateString('pt-BR', { day: '2-digit', month: 'long', year: 'numeric' })}</span>
                        <span>•</span>
                        <span>{draft.estimatedReadTime || 10} min de leitura</span>
                      </div>
                    </header>

                    <RichArticleRenderer
                      content={draft.generatedContent}
                      className={styles.richPreview}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Blocks editor/viewer pane */}
        {activePane === 'blocks' && (
          <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '20px', padding: '16px 0', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(255,255,255,0.06)', paddingBottom: '12px' }}>
              <div>
                <h3 style={{ margin: 0, color: '#fff', fontSize: '1.05rem', fontWeight: 700 }}>📦 Estrutura DSL por Blocos</h3>
                <p style={{ margin: '2px 0 0 0', color: '#64748b', fontSize: '0.78rem' }}>Mova, edite ou remova blocos. Eles são convertidos de volta para o artigo automaticamente.</p>
              </div>
            </div>

            {(!draft.blocks || draft.blocks.length === 0) ? (
              <div style={{ color: '#64748b', textAlign: 'center', padding: '40px', background: 'rgba(255,255,255,0.02)', borderRadius: '12px', border: '1px dashed rgba(255,255,255,0.08)' }}>
                Nenhum bloco detectado. Escreva ou gere o artigo primeiro na aba Editor.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {draft.blocks.map((block, idx) => {
                  const isFirst = idx === 0;
                  const isLast = idx === draft.blocks!.length - 1;

                  return (
                    <div
                      key={block.id}
                      draggable
                      onDragStart={(e) => {
                        e.dataTransfer.setData('text/plain', idx.toString());
                        e.dataTransfer.effectAllowed = 'move';
                        e.currentTarget.style.opacity = '0.5';
                      }}
                      onDragEnd={(e) => {
                        e.currentTarget.style.opacity = '1';
                      }}
                      onDragOver={(e) => {
                        e.preventDefault();
                        e.currentTarget.style.borderColor = '#e67e22';
                      }}
                      onDragLeave={(e) => {
                        e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.05)';
                      }}
                      onDrop={(e) => {
                        e.preventDefault();
                        e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.05)';
                        const fromIdx = parseInt(e.dataTransfer.getData('text/plain'), 10);
                        if (!isNaN(fromIdx)) {
                          handleDragDropBlock(fromIdx, idx);
                        }
                      }}
                      style={{
                        background: 'rgba(255, 255, 255, 0.02)',
                        border: '1px solid rgba(255, 255, 255, 0.05)',
                        borderRadius: '12px',
                        padding: '14px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '10px',
                        cursor: 'grab',
                        transition: 'all 0.2s',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(255, 255, 255, 0.04)', paddingBottom: '8px' }}>
                        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                          <span style={{ cursor: 'grab', color: '#64748b', fontSize: '1rem', marginRight: '4px' }} title="Arraste para reordenar">
                            ☰
                          </span>
                          <span style={{ background: 'rgba(230, 126, 34, 0.15)', color: '#e67e22', border: '1px solid rgba(230,126,34,0.2)', fontSize: '0.65rem', fontWeight: 'bold', padding: '2px 6px', borderRadius: '4px', textTransform: 'uppercase' }}>
                            {block.type}
                          </span>
                          <span style={{ color: '#475569', fontSize: '0.7rem', fontFamily: 'monospace' }}>
                            #{block.id}
                          </span>
                        </div>
                        
                        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                          <button
                            onClick={() => handleDeleteBlock(block.id)}
                            style={{ background: 'transparent', border: 'none', color: '#f87171', cursor: 'pointer', fontSize: '0.85rem', marginLeft: '6px' }}
                            type="button"
                          >
                            🗑️ Deletar
                          </button>
                        </div>
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                          <textarea
                            value={block.content}
                            onChange={(e) => handleEditBlockContent(block.id, e.target.value)}
                            style={{ background: '#090d16', border: '1px solid rgba(255,255,255,0.08)', color: '#cbd5e1', padding: '10px', borderRadius: '8px', fontFamily: 'monospace', fontSize: '0.8rem', minHeight: '100px', resize: 'vertical', width: '100%' }}
                          />
                        </div>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                          <div style={{ background: '#ffffff', borderRadius: '8px', padding: '12px', minHeight: '100px', color: '#334155', overflowY: 'auto' }}>
                            <BlockItemRenderer block={block} />
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function BlockItemRenderer({ block }: { block: import('@/lib/blockParser').ArticleBlock }) {
  const { parseBlocksToMarkdown } = require('@/lib/blockParser');
  const md = parseBlocksToMarkdown([block]);
  return <RichArticleRenderer content={md} />;
}
