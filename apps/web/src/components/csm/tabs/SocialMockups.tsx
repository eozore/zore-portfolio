'use client';

import { useState } from 'react';
import styles from './SocialMockups.module.css';

interface Slide {
  slideNumber?: number;
  heading: string;
  body: string;
}

export function CarouselMockup({ slides }: { slides: Slide[] }) {
  const [activeIdx, setActiveIdx] = useState(0);
  const total = slides?.length || 0;
  const current = slides?.[activeIdx] || { heading: 'Slide Vazio', body: 'Nenhum conteúdo definido' };

  return (
    <div className={styles.mockupContainer}>
      <div className={styles.phoneFrame}>
        <div className={styles.phoneNotch} />
        
        <div className={styles.phoneHeader}>
          <div className={styles.avatar}>VZ</div>
          <div className={styles.handle}>éozoré.ai</div>
        </div>

        <div className={styles.carouselContent}>
          <div className={styles.slideCounter}>{activeIdx + 1} / {Math.max(1, total)}</div>
          <div className={styles.slideHeading}>{current.heading}</div>
          <div className={styles.slideBody}>{current.body}</div>
        </div>

        <div className={styles.slideNav}>
          <button
            onClick={() => setActiveIdx((i) => Math.max(0, i - 1))}
            disabled={activeIdx === 0}
            className={styles.navBtn}
          >
            ← Anterior
          </button>
          <button
            onClick={() => setActiveIdx((i) => Math.min(total - 1, i + 1))}
            disabled={activeIdx >= total - 1}
            className={styles.navBtn}
          >
            Próximo →
          </button>
        </div>
      </div>
    </div>
  );
}

export function LinkedInMockup({ hook, copy, articleTitle }: { hook: string; copy: string; articleTitle?: string }) {
  const fullText = `${hook}\n\n${copy}`;

  return (
    <div className={styles.mockupContainer}>
      <div className={styles.linkedinCard}>
        <div className={styles.liHeader}>
          <div className={styles.liAvatar}>VZ</div>
          <div>
            <div className={styles.liName}>Victor Zore</div>
            <div className={styles.liTitle}>Tech Lead GenAI & ML Architect • UFSCar</div>
          </div>
        </div>

        <div className={styles.liCopy}>{fullText}</div>

        {articleTitle && (
          <div className={styles.liLinkCard}>
            <div className={styles.liLinkImage}>
              éozoré • Artigo Técnico
            </div>
            <div className={styles.liLinkText}>
              <div className={styles.liLinkTitle}>{articleTitle}</div>
              <div className={styles.liLinkDomain}>eozore.com • 5 min de leitura</div>
            </div>
          </div>
        )}

        <div className={styles.liFooter}>
          <span>Gostei</span>
          <span>Comentar</span>
          <span>Compartilhar</span>
          <span>Enviar</span>
        </div>
      </div>
    </div>
  );
}

export function TeleprompterView({ hook3s, cue, script }: { hook3s?: string; cue?: string; script: string }) {
  return (
    <div className={styles.teleprompter}>
      <span className={styles.prompterBadge}>STUDIO TELEPROMPTER VIEW</span>
      
      {hook3s && (
        <div className={styles.cueBox}>
          <strong>HOOK 3 SEG:</strong> &quot;{hook3s}&quot;
        </div>
      )}

      {cue && (
        <div className={styles.cueBox} style={{ borderColor: '#38bdf8', color: '#38bdf8' }}>
          <strong>VISUAL CUE:</strong> {cue}
        </div>
      )}

      <div className={styles.scriptText}>{script}</div>
    </div>
  );
}

export function StoryMockup({ copy, pollOrQuestion }: { copy: string; pollOrQuestion?: string }) {
  return (
    <div className={styles.mockupContainer}>
      <div className={styles.phoneFrame} style={{ height: '620px', background: 'linear-gradient(180deg, #1e1b4b, #0f172a)' }}>
        <div className={styles.phoneNotch} />
        
        <div className={styles.phoneHeader}>
          <div className={styles.avatar}>VZ</div>
          <div className={styles.handle}>éozoré • Story Rascunho</div>
        </div>

        <div className={styles.carouselContent} style={{ justifyContent: 'center', textAlign: 'center' }}>
          <div className={styles.slideHeading} style={{ fontSize: '1.25rem' }}>{copy}</div>

          {pollOrQuestion && (
            <div className={styles.pollBox}>
              <div className={styles.pollQ}>ENQUETE INTERATIVA</div>
              <div className={styles.pollOpt}>Sim, concordo 100%</div>
              <div className={styles.pollOpt}>Prefiro ver o código antes</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

interface VideoMockupProps {
  title: string;
  script: string;
  hook3s?: string;
  videoUrl?: string;
  isGenerating?: boolean;
  progress?: number;
  onGenerateVideo?: () => void;
  avatarVideoUrl?: string;
  motionVideoUrl?: string;
  videoError?: string;
  onRetryMerge?: () => void;
}

export function VideoMockup({
  title,
  script,
  hook3s,
  videoUrl,
  isGenerating,
  progress = 0,
  onGenerateVideo,
  avatarVideoUrl,
  motionVideoUrl,
  videoError,
  onRetryMerge,
}: VideoMockupProps) {
  return (
    <div className={styles.mockupContainer}>
      <div className={styles.phoneFrame} style={{ height: '660px' }}>
        <div className={styles.phoneNotch} />
        
        <div className={styles.phoneHeader} style={{ background: 'rgba(0,0,0,0.4)', zIndex: 3 }}>
          <div className={styles.avatar}>VZ</div>
          <div className={styles.handle}>éozoré • Vídeo AI</div>
        </div>

        <div className={styles.videoContainer}>
          {videoUrl ? (
            <video src={videoUrl} controls autoPlay loop muted playsInline className={styles.videoElement} />
          ) : videoError ? (
            <div className={styles.heygenStatusBox}>
              <div style={{ color: '#ef4444', fontSize: '2rem', marginBottom: '8px' }}>⚠️</div>
              <div className={styles.heygenStatusText} style={{ color: '#ef4444', fontSize: '0.85rem' }}>A fusão de vídeo falhou.</div>
              <p style={{ fontSize: '0.7rem', color: '#94a3b8', margin: '4px 16px 12px', lineHeight: 1.3 }}>{videoError}</p>
              {onRetryMerge && (
                <button
                  onClick={onRetryMerge}
                  style={{
                    background: 'linear-gradient(135deg, #f59e0b, #d97706)',
                    color: '#fff',
                    border: 'none',
                    padding: '8px 16px',
                    borderRadius: '8px',
                    fontWeight: 'bold',
                    fontSize: '0.8rem',
                    cursor: 'pointer',
                    boxShadow: '0 4px 10px rgba(245, 158, 11, 0.2)'
                  }}
                >
                  🔄 Retentar Fusão de Vídeo
                </button>
              )}
            </div>
          ) : isGenerating ? (
            <div className={styles.heygenStatusBox}>
              <div style={{ color: '#7c3aed', fontSize: '2rem', animation: 'spin 2s linear infinite' }}>⚙️</div>
              <div className={styles.heygenStatusText}>
                {progress < 100 && avatarVideoUrl === undefined ? '1/3: Renderizando avatar realista no HeyGen...' : 
                 progress < 100 && motionVideoUrl === undefined ? '2/3: Compilando animações de motion overlay...' :
                 '3/3: Mesclando vídeo final com FFmpeg chroma key...'}
              </div>
              <div>{progress}% concluído</div>
              <div className={styles.heygenProgressBar}>
                <div className={styles.heygenProgressFill} style={{ width: `${progress}%` }} />
              </div>
            </div>
          ) : (
            <div className={styles.heygenStatusBox}>
              <div style={{ color: '#94a3b8', fontSize: '1.5rem', marginBottom: '12px' }}>🎬 Roteiro de Vídeo</div>
              <p style={{ fontSize: '0.8rem', color: '#64748b', margin: '0 16px 20px', lineHeight: 1.4 }}>
                Pronto para gerar o vídeo de avatar do Victor Zore usando inteligência artificial no HeyGen.
              </p>
              {onGenerateVideo && (
                <button
                  onClick={onGenerateVideo}
                  style={{
                    background: 'linear-gradient(135deg, #7c3aed, #a855f7)',
                    color: '#fff',
                    border: 'none',
                    padding: '10px 20px',
                    borderRadius: '8px',
                    fontWeight: 'bold',
                    fontSize: '0.85rem',
                    cursor: 'pointer',
                    boxShadow: '0 4px 12px rgba(124, 58, 237, 0.3)',
                    transition: 'transform 0.2s',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.transform = 'scale(1.05)')}
                  onMouseLeave={(e) => (e.currentTarget.style.transform = 'scale(1)')}
                >
                  ⚡ Gerar Vídeo no HeyGen
                </button>
              )}
            </div>
          )}

          <div className={styles.videoOverlay}>
            <div className={styles.videoOverlayContent}>
              <div className={styles.videoOverlayHandle}>@eozore.ai</div>
              <div className={styles.videoCaptionText}>{title}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function ImagePostMockup({
  title,
  imageDescription,
  copy,
  imageUrl,
  isGenerating,
  progress,
  onGenerateImage,
}: {
  title: string;
  imageDescription: string;
  copy: string;
  imageUrl?: string;
  isGenerating?: boolean;
  progress?: number;
  onGenerateImage?: () => void;
}) {
  return (
    <div className={styles.mockupContainer} style={{ flexDirection: 'column', alignItems: 'stretch', gap: '16px' }}>
      {/* 1:1 Canvas */}
      <div className={styles.imageCanvas}>
        {imageUrl ? (
          <img src={imageUrl} alt={title} style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '12px' }} />
        ) : isGenerating ? (
          <div className={styles.heygenStatusBox}>
            <div style={{ color: '#7c3aed', fontSize: '2rem', animation: 'spin 2s linear infinite' }}>⚙️</div>
            <div className={styles.heygenStatusText} style={{ fontSize: '0.8rem', marginTop: '12px' }}>Gerando imagem via HTML template...</div>
          </div>
        ) : (
          <div className={styles.canvasInner}>
            <div className={styles.canvasLogo}>ÉOZORÉ • IA</div>
            <div className={styles.canvasTitle}>{title}</div>
            <div className={styles.canvasSub}>Visual explicativo</div>
            
            <div className={styles.canvasVisualDescriptor}>
              <strong>💡 Diretriz Visual para IA/Designer:</strong>
              <p style={{ margin: '6px 0 0 0', fontStyle: 'italic', fontSize: '0.7rem', lineHeight: 1.4 }}>
                {imageDescription}
              </p>
            </div>

            {onGenerateImage && (
              <button
                onClick={onGenerateImage}
                style={{
                  background: 'linear-gradient(135deg, #7c3aed, #a855f7)',
                  color: '#fff',
                  border: 'none',
                  padding: '8px 16px',
                  borderRadius: '8px',
                  fontWeight: 'bold',
                  fontSize: '0.8rem',
                  cursor: 'pointer',
                  marginTop: '16px',
                  boxShadow: '0 4px 10px rgba(124, 58, 237, 0.2)'
                }}
              >
                🖼️ Gerar Imagem HTML
              </button>
            )}
          </div>
        )}
      </div>

      {/* Caption post details */}
      <div className={styles.imagePostCaptionBox}>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '8px' }}>
          <div className={styles.avatar} style={{ width: '24px', height: '24px', fontSize: '0.65rem' }}>VZ</div>
          <strong style={{ color: '#fff', fontSize: '0.85rem' }}>Victor Zore</strong>
        </div>
        <div className={styles.imagePostCaption}>{copy}</div>
      </div>
    </div>
  );
}
