'use client';

import { useState } from 'react';
import type { ContentStatus } from '../CsmDashboard';
import { CarouselMockup, LinkedInMockup, TeleprompterView, StoryMockup, VideoMockup, ImagePostMockup } from './SocialMockups';
import styles from './EditorialCalendar.module.css';

export interface CalendarItem {
  id: string;
  platform: 'linkedin' | 'youtube' | 'instagram' | 'threads' | 'facebook';
  format: 'image' | 'carousel' | 'reel' | 'story' | 'video' | 'poll' | 'shorts' | 'post_imagem';
  titleOrHook: string;
  copy: string;
  scheduledAt: string; // ISO
  status: ContentStatus;
  slides?: { slideNumber?: number; heading: string; body: string }[];
  hook3s?: string;
  visualCue?: string;
  imageDescription?: string;
  articleTitle?: string;
  videoUrl?: string;
  isGenerating?: boolean;
  progress?: number;
  onGenerateVideo?: () => void;
  avatarVideoUrl?: string;
  motionVideoUrl?: string;
  videoError?: string;
  onRetryMerge?: () => void;
  imageUrl?: string;
  onGenerateImage?: () => void;
}

interface EditorialCalendarProps {
  items: CalendarItem[];
  onUpdateItem: (id: string, partial: Partial<CalendarItem>) => void;
}

const DAYS = [
  { key: 1, label: 'Segunda' },
  { key: 2, label: 'Terça' },
  { key: 3, label: 'Quarta' },
  { key: 4, label: 'Quinta' },
  { key: 5, label: 'Sexta' },
  { key: 6, label: 'Sábado' },
  { key: 0, label: 'Domingo' },
];

export default function EditorialCalendar({ items, onUpdateItem }: EditorialCalendarProps) {
  const [selectedPlatform, setSelectedPlatform] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [activeModalId, setActiveModalId] = useState<string | null>(null);

  const filteredItems = items.filter((item) => {
    if (selectedPlatform !== 'all' && item.platform !== selectedPlatform) return false;
    if (selectedStatus !== 'all' && item.status !== selectedStatus) return false;
    return true;
  });

  const getDayKey = (isoString: string) => {
    try {
      return new Date(isoString).getDay();
    } catch {
      return 1;
    }
  };

  const activeItem = items.find((i) => i.id === activeModalId);

  return (
    <div className={styles.calendarLayout}>
      {/* Filter Toolbar */}
      <div className={styles.filterBar}>
        <div className={styles.filterPills}>
          <span style={{ color: '#fff', fontWeight: 'bold', fontSize: '0.85rem', alignSelf: 'center', marginRight: '8px' }}>
            Plataforma:
          </span>
          {['all', 'linkedin', 'youtube', 'instagram'].map((plat) => (
            <button
              key={plat}
              onClick={() => setSelectedPlatform(plat)}
              className={`${styles.pill} ${selectedPlatform === plat ? styles.pillActive : ''}`}
            >
              {plat === 'all' ? 'Todas' : plat.toUpperCase()}
            </button>
          ))}
        </div>

        <div className={styles.filterPills}>
          <span style={{ color: '#fff', fontWeight: 'bold', fontSize: '0.85rem', alignSelf: 'center', marginRight: '8px' }}>
            Status:
          </span>
          {[
            { id: 'all', label: 'Todos' },
            { id: 'em_revisao', label: 'Em Revisão' },
            { id: 'aprovado', label: 'Aprovado' },
            { id: 'rejeitado', label: 'Rejeitado' },
          ].map(({ id, label }) => (
            <button
              key={id}
              onClick={() => setSelectedStatus(id)}
              className={`${styles.pill} ${selectedStatus === id ? styles.pillActive : ''}`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Weekly Grid */}
      <div className={styles.grid}>
        {DAYS.map(({ key, label }) => {
          const dayItems = filteredItems.filter((i) => getDayKey(i.scheduledAt) === key);

          return (
            <div key={label} className={styles.dayCol}>
              <div className={styles.dayTitle}>
                <span>{label}</span>
                <span className={styles.dayCount}>{dayItems.length}</span>
              </div>

              {dayItems.map((item) => (
                <div
                  key={item.id}
                  onClick={() => setActiveModalId(item.id)}
                  className={styles.itemCard}
                >
                  <div className={styles.cardHeadRow}>
                    <span className={styles.platformTag}>{item.platform}</span>
                    <span
                      className={`${styles.statusDot} ${
                        item.status === 'aprovado'
                          ? styles.status_aprovado
                          : item.status === 'rejeitado'
                          ? styles.status_rejeitado
                          : styles.status_em_revisao
                      }`}
                      title={item.status}
                    />
                  </div>
                  <div className={styles.cardTitle}>{item.titleOrHook}</div>
                  <div style={{ fontSize: '0.7rem', color: '#64748b', marginTop: '4px' }}>
                    Agendado: {item.scheduledAt ? new Date(item.scheduledAt).toLocaleTimeString().slice(0, 5) : '12:00'}
                  </div>
                </div>
              ))}
            </div>
          );
        })}
      </div>

      {/* Live Curation Drawer / Modal */}
      {activeItem && (
        <div className={styles.modalOverlay} onClick={() => setActiveModalId(null)}>
          <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
            {/* Left Preview Column */}
            <div className={styles.modalPreviewCol}>
              {activeItem.format === 'carousel' && activeItem.slides ? (
                <CarouselMockup slides={activeItem.slides} />
              ) : activeItem.platform === 'linkedin' ? (
                <LinkedInMockup hook={activeItem.titleOrHook} copy={activeItem.copy} articleTitle={activeItem.articleTitle} />
              ) : activeItem.format === 'story' ? (
                <StoryMockup copy={activeItem.copy} pollOrQuestion={activeItem.titleOrHook} />
              ) : (activeItem.format === 'reel' || activeItem.format === 'shorts') ? (
                <VideoMockup
                  title={activeItem.titleOrHook}
                  script={activeItem.copy}
                  hook3s={activeItem.hook3s}
                  videoUrl={activeItem.videoUrl}
                  isGenerating={activeItem.isGenerating}
                  progress={activeItem.progress}
                  onGenerateVideo={activeItem.onGenerateVideo}
                  avatarVideoUrl={activeItem.avatarVideoUrl}
                  motionVideoUrl={activeItem.motionVideoUrl}
                  videoError={activeItem.videoError}
                  onRetryMerge={activeItem.onRetryMerge}
                />
              ) : activeItem.format === 'post_imagem' ? (
                <ImagePostMockup
                  title={activeItem.titleOrHook}
                  imageDescription={activeItem.imageDescription || ''}
                  copy={activeItem.copy}
                  imageUrl={activeItem.imageUrl}
                  isGenerating={activeItem.isGenerating}
                  progress={activeItem.progress}
                  onGenerateImage={activeItem.onGenerateImage}
                />
              ) : (
                <TeleprompterView hook3s={activeItem.hook3s} cue={activeItem.visualCue} script={activeItem.copy} />
              )}
            </div>

            {/* Right Editor Column */}
            <div className={styles.modalEditCol}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: '#f5a962', fontWeight: 'bold', fontSize: '0.85rem', textTransform: 'uppercase' }}>
                  Curadoria & Edição: {activeItem.platform} ({activeItem.format})
                </span>
                <button className={styles.closeBtn} onClick={() => setActiveModalId(null)}>✕ Fechar</button>
              </div>

              <input
                type="text"
                value={activeItem.titleOrHook}
                onChange={(e) => onUpdateItem(activeItem.id, { titleOrHook: e.target.value })}
                style={{ background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.15)', color: '#fff', padding: '12px', borderRadius: '10px', fontSize: '1rem', fontWeight: 'bold' }}
                placeholder="Gancho / Título principal"
              />

              <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                <span style={{ color: '#cbd5e1', fontSize: '0.85rem' }}>Agendamento:</span>
                <input
                  type="datetime-local"
                  value={activeItem.scheduledAt ? activeItem.scheduledAt.slice(0, 16) : ''}
                  onChange={(e) => onUpdateItem(activeItem.id, { scheduledAt: new Date(e.target.value).toISOString() })}
                  style={{ background: 'rgba(0,0,0,0.5)', border: '1px solid rgba(255,255,255,0.2)', color: '#fff', padding: '8px 12px', borderRadius: '8px' }}
                />
              </div>

              <div>
                <span style={{ color: '#cbd5e1', fontSize: '0.85rem', display: 'block', marginBottom: '8px' }}>
                  Status de Publicação (Apenas aprovados vão para o banco):
                </span>
                <div className={styles.statusToolbar}>
                  <button
                    onClick={() => onUpdateItem(activeItem.id, { status: 'em_revisao' })}
                    className={`${styles.statusBtn} ${activeItem.status === 'em_revisao' ? styles.statusBtnActiveRev : ''}`}
                  >
                    Em Revisão
                  </button>
                  <button
                    onClick={() => onUpdateItem(activeItem.id, { status: 'aprovado' })}
                    className={`${styles.statusBtn} ${activeItem.status === 'aprovado' ? styles.statusBtnActiveApr : ''}`}
                  >
                    Aprovar
                  </button>
                  <button
                    onClick={() => onUpdateItem(activeItem.id, { status: 'rejeitado' })}
                    className={`${styles.statusBtn} ${activeItem.status === 'rejeitado' ? styles.statusBtnActiveRej : ''}`}
                  >
                    Rejeitar
                  </button>
                </div>
              </div>

              <textarea
                value={activeItem.copy}
                onChange={(e) => onUpdateItem(activeItem.id, { copy: e.target.value })}
                style={{ flex: 1, minHeight: '200px', background: 'rgba(0,0,0,0.6)', border: '1px solid rgba(255,255,255,0.12)', color: '#e2e8f0', padding: '16px', borderRadius: '12px', fontFamily: 'monospace', lineHeight: 1.6 }}
                placeholder="Texto / Legenda / Roteiro..."
              />

              <div style={{ display: 'flex', gap: '12px', marginTop: '12px' }}>
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(activeItem.copy);
                    alert('Conteúdo copiado com sucesso!');
                  }}
                  style={{
                    flex: 1,
                    background: '#1e293b',
                    color: '#fff',
                    border: '1px solid #475569',
                    padding: '10px',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    fontWeight: 'bold',
                    fontSize: '0.85rem'
                  }}
                >
                  📋 Copiar Texto (Copy)
                </button>

                {activeItem.videoUrl && (
                  <a
                    href={activeItem.videoUrl}
                    download={`video_${activeItem.id}.mp4`}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      flex: 1,
                      background: 'linear-gradient(135deg, #10b981, #059669)',
                      color: '#fff',
                      padding: '10px',
                      borderRadius: '8px',
                      textAlign: 'center',
                      textDecoration: 'none',
                      fontWeight: 'bold',
                      fontSize: '0.85rem'
                    }}
                  >
                    ⬇️ Baixar Vídeo Final
                  </a>
                )}

                {activeItem.imageUrl && (
                  <a
                    href={activeItem.imageUrl}
                    download={`imagem_${activeItem.id}.png`}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      flex: 1,
                      background: 'linear-gradient(135deg, #10b981, #059669)',
                      color: '#fff',
                      padding: '10px',
                      borderRadius: '8px',
                      textAlign: 'center',
                      textDecoration: 'none',
                      fontWeight: 'bold',
                      fontSize: '0.85rem'
                    }}
                  >
                    ⬇️ Baixar Imagem PNG
                  </a>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
