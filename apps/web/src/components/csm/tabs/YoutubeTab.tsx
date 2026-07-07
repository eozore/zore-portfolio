/* ============================================================
   YoutubeTab.tsx — Aba 4: Editor de Roteiro de Vídeo do YouTube
   ============================================================ */
'use client';

import { useState, useMemo } from 'react';
import type { DraftState } from '../CsmDashboard';
import styles from './YoutubeTab.module.css';
import RichArticleRenderer from '../RichArticleRenderer';
import { parseMarkdownToScenes, parseScenesToMarkdown, type ScriptScene } from '@/lib/scriptParser';

interface YoutubeTabProps {
  draft: DraftState;
  updateDraft: (partial: Partial<DraftState>) => void;
  onBack: () => void;
  onNext: () => void;
  sessionId: string;
}

export default function YoutubeTab({ draft, updateDraft, onBack, onNext, sessionId }: YoutubeTabProps) {
  const [activePane, setActivePane] = useState<'editor' | 'preview' | 'split' | 'scenes'>('split');
  const [isGeneratingScript, setIsGeneratingScript] = useState(false);
  const [isGeneratingCampaign, setIsGeneratingCampaign] = useState(false);
  
  // HeyGen video generation state
  const [isGeneratingVideo, setIsGeneratingVideo] = useState(false);
  const [videoProgress, setVideoProgress] = useState(0);
  const [generatedVideoUrl, setGeneratedVideoUrl] = useState((draft as any).youtubeScriptVideoUrl || '');
  const [error, setError] = useState('');

  const scriptContent = draft.youtubeScript || '';
  const charCount = scriptContent.length;
  const wordCount = scriptContent.trim().split(/\s+/).filter(Boolean).length;

  const scenes = useMemo(() => {
    return draft.youtubeScenes && draft.youtubeScenes.length > 0
      ? draft.youtubeScenes
      : parseMarkdownToScenes(scriptContent);
  }, [draft.youtubeScenes, scriptContent]);

  const handleContentChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    updateDraft({
      youtubeScript: e.target.value,
    });
  };

  const handleUpdateScene = (id: string, updatedFields: Partial<ScriptScene>) => {
    const nextScenes = scenes.map(s => s.id === id ? { ...s, ...updatedFields } : s);
    const newMd = parseScenesToMarkdown(nextScenes);
    updateDraft({
      youtubeScript: newMd,
      youtubeScenes: nextScenes,
    });
  };

  const handleAddScene = (index: number) => {
    const newScene: ScriptScene = {
      id: Math.random().toString(36).slice(2, 9),
      section: scenes[index]?.section || 'TEORIA',
      visualCue: 'CENA: Victor falando para a câmera',
      spokenText: 'Nova fala da cena.',
    };
    const nextScenes = [...scenes];
    nextScenes.splice(index + 1, 0, newScene);
    const newMd = parseScenesToMarkdown(nextScenes);
    updateDraft({
      youtubeScript: newMd,
      youtubeScenes: nextScenes,
    });
  };

  const handleDeleteScene = (id: string) => {
    if (scenes.length <= 1) return;
    const nextScenes = scenes.filter(s => s.id !== id);
    const newMd = parseScenesToMarkdown(nextScenes);
    updateDraft({
      youtubeScript: newMd,
      youtubeScenes: nextScenes,
    });
  };

  const handleMoveScene = (index: number, direction: 'up' | 'down') => {
    const targetIndex = direction === 'up' ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= scenes.length) return;
    const nextScenes = [...scenes];
    const temp = nextScenes[index];
    nextScenes[index] = nextScenes[targetIndex];
    nextScenes[targetIndex] = temp;
    const newMd = parseScenesToMarkdown(nextScenes);
    updateDraft({
      youtubeScript: newMd,
      youtubeScenes: nextScenes,
    });
  };

  const handleGenerateVideo = async () => {
    if (!scriptContent) return;
    setIsGeneratingVideo(true);
    setVideoProgress(10);
    setError('');

    try {
      const res = await fetch('/api/csm/heygen', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          script: scriptContent,
          format: 'landscape',
          avatarProfile: 'horizontal',
          id: 'yt-long-video'
        })
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Erro ao gerar vídeo no HeyGen');

      const videoId = data.videoId;
      setVideoProgress(25);

      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await fetch(`/api/csm/heygen?videoId=${videoId}`);
          const statusData = await statusRes.json();

          if (!statusRes.ok) {
            clearInterval(pollInterval);
            throw new Error(statusData.error || 'Erro no processamento');
          }

          if (statusData.status === 'completed') {
            clearInterval(pollInterval);
            setGeneratedVideoUrl(statusData.videoUrl);
            setIsGeneratingVideo(false);
            setVideoProgress(100);
            updateDraft({
              youtubeScriptVideoUrl: statusData.videoUrl
            } as any);
          } else if (statusData.status === 'failed') {
            clearInterval(pollInterval);
            setIsGeneratingVideo(false);
            setError(`HeyGen failed: ${statusData.error || 'Erro desconhecido'}`);
          } else {
            setVideoProgress(statusData.progress || Math.min(95, videoProgress + 15));
          }
        } catch (err: any) {
          clearInterval(pollInterval);
          setIsGeneratingVideo(false);
          setError(err.message || 'Erro ao consultar status');
        }
      }, 3000);
    } catch (err: any) {
      setIsGeneratingVideo(false);
      setError(err.message || 'Erro de comunicação com o HeyGen');
    }
  };

  const triggerScriptGeneration = async () => {
    setIsGeneratingScript(true);
    setError('');
    updateDraft({ youtubeScript: '' });

    try {
      const response = await fetch('/api/csm/youtube', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          title: draft.suggestedTitle || draft.topic || 'Video sem titulo',
          content: draft.generatedContent,
          category: draft.category,
          language: draft.language,
          sessionId,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      if (!response.body) {
        throw new Error('Sem corpo de resposta do servidor de roteirização.');
      }

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
              updateDraft({ youtubeScript: currentContent });
            } else if (parsed.type === 'error') {
              throw new Error(parsed.message);
            }
          } catch (e) {
            // Ignore parse errors on incomplete chunk lines
          }
        }
      }

      // Fallback Client-Side META block parsing for YouTube Script
      const finalContent = currentContent || '';
      const metaMatch = finalContent.match(/META:\s*(\{[^}]+\})\s*$/m);
      if (metaMatch) {
        try {
          const cleanedMeta = metaMatch[1].replace(/,\s*([}\]])/g, '$1');
          const meta = JSON.parse(cleanedMeta);
          
          const cleanedContent = finalContent.replace(/\n?META:\s*\{[^}]+\}\s*$/m, '').trimEnd();
          
          updateDraft({
            youtubeScript: cleanedContent
          });
        } catch (e) {
          console.warn('[csm/youtube] Client-side META parsing failed:', e);
        }
      }
    } catch (err: any) {
      console.error('[YoutubeTab] Generation failed:', err);
      setError(err.message || 'Falha na conexão ou geração do roteiro.');
    } finally {
      setIsGeneratingScript(false);
    }
  };

  const triggerCampaignGeneration = async () => {
    setIsGeneratingCampaign(true);
    setError('');

    try {
      const res = await fetch('/api/csm/repurpose', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: draft.suggestedTitle || draft.topic || 'Campanha Sem Titulo',
          slug: draft.suggestedSlug || (draft.suggestedTitle ? draft.suggestedTitle.toLowerCase().replace(/[^a-z0-9]+/g, '-') : 'campanha'),
          content: draft.generatedContent,
          youtubeScript: draft.youtubeScript,
          category: draft.category,
          language: draft.language,
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Erro ao derivar campanha omnicanal');

      updateDraft({ repurposedData: data });
      onNext();
    } catch (err: any) {
      console.error('[YoutubeTab] Campaign repurpose failed:', err);
      setError(err.message || 'Erro ao derivar mídias sociais.');
    } finally {
      setIsGeneratingCampaign(false);
    }
  };

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
          
          <button
            onClick={triggerScriptGeneration}
            disabled={isGeneratingScript || isGeneratingCampaign || isGeneratingVideo}
            className={styles.generateBtn}
            type="button"
          >
            {isGeneratingScript ? (
              <>
                <span className={styles.btnSpinner} />
                Gerando Roteiro...
              </>
            ) : scriptContent ? (
              'Refazer Roteiro com IA 🔄'
            ) : (
              'Gerar Roteiro do YouTube 🎬'
            )}
          </button>

          {scriptContent && (
            <button
              onClick={handleGenerateVideo}
              disabled={isGeneratingScript || isGeneratingCampaign || isGeneratingVideo}
              className={styles.generateBtn}
              style={{
                background: isGeneratingVideo ? 'rgba(124, 58, 237, 0.2)' : 'linear-gradient(135deg, #7c3aed, #5b21b6)',
                boxShadow: isGeneratingVideo ? 'none' : '0 4px 12px rgba(124, 58, 237, 0.3)',
                color: '#fff',
                marginLeft: '8px'
              }}
              type="button"
            >
              {isGeneratingVideo ? (
                <>
                  <span className={styles.btnSpinner} style={{ borderTopColor: '#7c3aed' }} />
                  HeyGen ({videoProgress}%)
                </>
              ) : generatedVideoUrl ? (
                'Vídeo HeyGen Pronto ✓'
              ) : (
                'Gerar Vídeo no HeyGen ⚡'
              )}
            </button>
          )}
        </div>

        {/* View Toggles */}
        <div className={styles.paneToggle}>
          {(['editor', 'preview', 'split', 'scenes'] as const).map(pane => (
            <button
              key={pane}
              onClick={() => setActivePane(pane)}
              className={`${styles.paneBtn} ${activePane === pane ? styles.paneBtnActive : ''}`}
              type="button"
            >
              <span className={styles.paneBtnLabel}>
                {pane === 'editor' && '💻 Código'}
                {pane === 'preview' && '👁️ Preview'}
                {pane === 'split' && '🥞 Dividido'}
                {pane === 'scenes' && '🎬 Cenas DSL'}
              </span>
            </button>
          ))}
        </div>

        {/* Stats & Next */}
        <div className={styles.toolbarRight}>
          <div className={styles.stats}>
            <div className={styles.stat}>
              <span className={styles.statVal}>{wordCount.toLocaleString()}</span>
              <span className={styles.statKey}>Palavras</span>
            </div>
            <div className={styles.statSep} />
            <div className={styles.stat}>
              <span className={styles.statVal}>{charCount.toLocaleString()}</span>
              <span className={styles.statKey}>Caracteres</span>
            </div>
          </div>

          <button
            onClick={triggerCampaignGeneration}
            disabled={!scriptContent || isGeneratingScript || isGeneratingCampaign || isGeneratingVideo}
            className={styles.nextBtn}
            type="button"
          >
            {isGeneratingCampaign ? (
              <>
                <span className={styles.btnSpinner} />
                Gerando Mídias...
              </>
            ) : (
              <>
                Avançar para Mídias Sociais
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" width="14" height="14">
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </>
            )}
          </button>
        </div>
      </div>

      {error && <div className={styles.errorBox}>{error}</div>}

      {/* Editor & Preview Area */}
      <div className={`${styles.editorArea} ${
        activePane === 'split' ? styles.splitView :
        activePane === 'editor' ? styles.editorOnly : styles.previewOnly
      }`}>
        {/* Left: Editor */}
        {(activePane === 'editor' || activePane === 'split') && (
          <div className={styles.editorPane}>
            <div className={styles.paneHeader}>
              <span className={styles.paneHeaderLabel}>Roteiro do YouTube (Markdown)</span>
              <div className={styles.paneHeaderDots}>
                <span style={{ backgroundColor: '#ff5f56' }} />
                <span style={{ backgroundColor: '#ffbd2e' }} />
                <span style={{ backgroundColor: '#27c93f' }} />
              </div>
            </div>
            <textarea
              value={scriptContent}
              onChange={handleContentChange}
              placeholder="Clique em 'Gerar Roteiro do YouTube' para começar a criar..."
              className={styles.editor}
              disabled={isGeneratingScript || isGeneratingCampaign || isGeneratingVideo}
            />
          </div>
        )}

        {/* Right: Preview */}
        {(activePane === 'preview' || activePane === 'split') && (
          <div className={styles.previewPane}>
            <div className={styles.paneHeader}>
              <span className={styles.paneHeaderLabel}>Preview do Roteiro</span>
            </div>
            <div className={styles.previewScroll}>
              {scriptContent ? (
                <div style={{ backgroundColor: '#eae9e6', padding: '2rem 1rem', minHeight: '100%' }}>
                  <div className="max-w-3xl mx-auto bg-[#f8f7f4] shadow-[0_4px_20px_rgba(0,0,0,0.06)] rounded-2xl p-6 md:p-12 text-[#1e1e1e]">
                    {/* Simulated Script Header */}
                    <header className="mb-8 pb-8 border-b border-black/[0.08]">
                      <span className="inline-block px-3 py-1 text-xs font-semibold rounded bg-red-100 text-red-600 mb-4 uppercase tracking-wider">
                        🎬 ROTEIRO DO YOUTUBE
                      </span>
                      <h1 className="text-3xl font-bold text-gray-900 leading-tight">
                        {draft.suggestedTitle || draft.topic || 'Sem Título'}
                      </h1>
                      <div className="mt-4 flex items-center gap-4 text-sm text-gray-500">
                        <span>Canal Victor Zoré</span>
                        <span>•</span>
                        <span>{wordCount.toLocaleString()} palavras</span>
                      </div>
                    </header>
                    
                    {generatedVideoUrl && (
                      <div style={{ marginBottom: '20px', borderRadius: '12px', overflow: 'hidden', border: '1px solid rgba(0,0,0,0.1)' }}>
                        <video src={generatedVideoUrl} controls style={{ width: '100%', maxHeight: '360px' }} />
                      </div>
                    )}
                    
                    <RichArticleRenderer content={scriptContent} />
                  </div>
                </div>
              ) : (
                <div className={styles.previewEmpty}>
                  🎬
                  <p>Aguardando a geração do roteiro.<br />O preview formatado com blocos de edição e formulas matemáticas será renderizado aqui.</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Scenes DSL pane */}
        {activePane === 'scenes' && (
          <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '20px', padding: '16px', overflowY: 'auto', background: '#eae9e6' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(0,0,0,0.08)', paddingBottom: '12px' }}>
              <div>
                <h3 style={{ margin: 0, color: '#1e1e1e', fontSize: '1.05rem', fontWeight: 700 }}>🎬 Roteiro Modular por Cenas</h3>
                <p style={{ margin: '2px 0 0 0', color: '#4b5563', fontSize: '0.78rem' }}>Visualize e edite as falas (HeyGen) e indicações de tela (Motion Graphics) de forma independente.</p>
              </div>
            </div>

            {scenes.length === 0 ? (
              <div style={{ color: '#6b6b6b', textAlign: 'center', padding: '40px', background: 'rgba(255,255,255,0.5)', borderRadius: '12px', border: '1px dashed rgba(30,30,30,0.15)' }}>
                Nenhuma cena detectada. Escreva ou gere o roteiro primeiro no Editor de Código.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxWidth: '800px', margin: '0 auto', width: '100%' }}>
                {scenes.map((scene, idx) => {
                  return (
                    <div
                      key={scene.id}
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
                        e.preventDefault();
                        e.currentTarget.style.borderColor = 'rgba(0,0,0,0.08)';
                      }}
                      onDrop={(e) => {
                        e.preventDefault();
                        e.currentTarget.style.borderColor = 'rgba(0,0,0,0.08)';
                        const fromIdx = parseInt(e.dataTransfer.getData('text/plain'), 10);
                        if (!isNaN(fromIdx) && fromIdx !== idx) {
                          const nextScenes = [...scenes];
                          const draggedScene = nextScenes[fromIdx];
                          nextScenes.splice(fromIdx, 1);
                          nextScenes.splice(idx, 0, draggedScene);
                          const newMd = parseScenesToMarkdown(nextScenes);
                          updateDraft({
                            youtubeScript: newMd,
                            youtubeScenes: nextScenes,
                          });
                        }
                      }}
                      style={{
                        background: '#ffffff',
                        border: '1px solid rgba(0,0,0,0.08)',
                        borderRadius: '12px',
                        padding: '16px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '12px',
                        boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
                        cursor: 'grab',
                        transition: 'all 0.2s',
                      }}
                    >
                      {/* Card Header */}
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(0,0,0,0.06)', paddingBottom: '8px' }}>
                        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                          <span style={{ cursor: 'grab', color: '#64748b', fontSize: '1rem', marginRight: '4px' }} title="Arraste para reordenar">
                            ☰
                          </span>
                          <span style={{ background: 'rgba(230, 126, 34, 0.12)', color: '#d35400', fontSize: '0.65rem', fontWeight: 'bold', padding: '2px 6px', borderRadius: '4px', textTransform: 'uppercase' }}>
                            {scene.section}
                          </span>
                          <span style={{ color: '#94a3b8', fontSize: '0.7rem', fontFamily: 'monospace' }}>
                            Cena #{idx + 1} ({scene.id})
                          </span>
                        </div>
                        
                        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                          <button
                            onClick={() => handleAddScene(idx)}
                            style={{ background: 'transparent', border: 'none', color: '#10b981', cursor: 'pointer', fontSize: '0.85rem' }}
                            type="button"
                            title="Adicionar cena após"
                          >
                            ➕ Nova
                          </button>
                          <button
                            onClick={() => handleDeleteScene(scene.id)}
                            style={{ background: 'transparent', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: '0.85rem' }}
                            type="button"
                            title="Excluir cena"
                          >
                            🗑️
                          </button>
                        </div>
                      </div>

                      {/* Card Content Inputs */}
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        <div>
                          <label style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 'bold', display: 'block', marginBottom: '4px' }}>Direção / Visual Cue (Motion Graphic)</label>
                          <input
                            type="text"
                            value={scene.visualCue}
                            onChange={(e) => handleUpdateScene(scene.id, { visualCue: e.target.value })}
                            style={{ background: '#f8f7f4', border: '1px solid rgba(30,30,30,0.1)', color: '#1e1e1e', padding: '8px 12px', borderRadius: '6px', fontSize: '0.85rem', width: '100%', fontWeight: 500 }}
                          />
                        </div>

                        <div>
                          <label style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase', fontWeight: 'bold', display: 'block', marginBottom: '4px' }}>Fala / Narração (HeyGen Speech)</label>
                          <textarea
                            value={scene.spokenText}
                            onChange={(e) => handleUpdateScene(scene.id, { spokenText: e.target.value })}
                            style={{ background: '#f8f7f4', border: '1px solid rgba(30,30,30,0.1)', color: '#1e1e1e', padding: '10px 12px', borderRadius: '6px', fontSize: '0.85rem', width: '100%', minHeight: '80px', resize: 'vertical' }}
                          />
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
