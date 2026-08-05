/* ================================================================
   CalendarTab.tsx — Visão semanal do planejamento editorial
   Popup editável por item (copy/hashtags/data+hora)
   ================================================================ */
'use client';

import { useState, useEffect, useCallback } from 'react';
import type { CalendarItem } from '@/app/api/csm/calendar/route';
import styles from './CalendarTab.module.css';

interface CalendarTabProps {
  sessionId: string;
}

// ── Paleta por plataforma ─────────────────────────────────────────────────────
const PLATFORM_CONFIG: Record<string, { icon: string; color: string; bg: string; border: string }> = {
  linkedin:          { icon: '💼', color: '#0a66c2', bg: 'rgba(10,102,194,.15)',  border: 'rgba(10,102,194,.5)'  },
  instagram:         { icon: '📷', color: '#e1306c', bg: 'rgba(225,48,108,.15)',  border: 'rgba(225,48,108,.5)'  },
  threads:           { icon: '🧵', color: '#eae4dc', bg: 'rgba(234,228,220,.10)', border: 'rgba(234,228,220,.3)' },
  facebook:          { icon: '👥', color: '#1877f2', bg: 'rgba(24,119,242,.15)',  border: 'rgba(24,119,242,.5)'  },
  youtube:           { icon: '▶️', color: '#ff0000', bg: 'rgba(255,0,0,.12)',     border: 'rgba(255,0,0,.4)'     },
  youtube_community: { icon: '🎬', color: '#ff6b35', bg: 'rgba(255,107,53,.12)',  border: 'rgba(255,107,53,.4)'  },
  youtube_shorts:    { icon: '🩳', color: '#ff0050', bg: 'rgba(255,0,80,.12)',    border: 'rgba(255,0,80,.4)'    },
};
const DEFAULT_PC = { icon: '📄', color: '#8a8378', bg: 'rgba(138,131,120,.1)', border: 'rgba(138,131,120,.3)' };

const STATUS_LABELS: Record<string, string> = {
  planned:              '⏳ Agendado',
  published:            '✅ Publicado',
  failed:               '❌ Falhou',
  generating_media:     '🎬 Gerando vídeo',
  awaiting_publication: '⏸ Aguardando',
  archived:             '📦 Arquivado',
};

// ── Helpers de data ───────────────────────────────────────────────────────────
function startOfWeek(d: Date): Date {
  const r = new Date(d);
  const day = r.getDay();
  r.setDate(r.getDate() - day);
  r.setHours(0, 0, 0, 0);
  return r;
}
function addDays(d: Date, n: number): Date {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
}
function fmtDate(d: Date): string {
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
}
function fmtDayName(d: Date): string {
  return d.toLocaleDateString('pt-BR', { weekday: 'short' }).replace('.', '').toUpperCase();
}
function isToday(d: Date): boolean {
  const t = new Date();
  return d.getDate() === t.getDate() && d.getMonth() === t.getMonth() && d.getFullYear() === t.getFullYear();
}
function toLocalDatetimeValue(iso: string): { date: string; time: string } {
  if (!iso) return { date: '', time: '' };
  try {
    const d = new Date(iso);
    const date = d.toISOString().slice(0, 10);
    const time = d.toTimeString().slice(0, 5);
    return { date, time };
  } catch {
    return { date: '', time: '' };
  }
}

// ── Horas visíveis ────────────────────────────────────────────────────────────
const HOURS = Array.from({ length: 18 }, (_, i) => i + 6); // 06h–23h
const DAYS_OF_WEEK = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];

export default function CalendarTab({ sessionId }: CalendarTabProps) {
  const [items, setItems]           = useState<CalendarItem[]>([]);
  const [isLoading, setIsLoading]   = useState(true);
  const [error, setError]           = useState<string | null>(null);
  const [weekStart, setWeekStart]   = useState<Date>(() => startOfWeek(new Date()));
  const [view, setView]             = useState<'week' | 'list'>('week');
  const [selected, setSelected]     = useState<CalendarItem | null>(null);
  const [editCopy, setEditCopy]     = useState('');
  const [editHashtags, setEditHashtags] = useState('');
  const [editDate, setEditDate]     = useState('');
  const [editTime, setEditTime]     = useState('');
  const [isSaving, setIsSaving]     = useState(false);
  const [saveMsg, setSaveMsg]       = useState('');

  const [isRetrying, setIsRetrying]     = useState(false);
  const [retryMsg, setRetryMsg]         = useState('');

  // ── Carrega itens ─────────────────────────────────────────────────────────
  const loadItems = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const from = weekStart.toISOString();
      const to   = addDays(weekStart, view === 'list' ? 90 : 7).toISOString();
      const res  = await fetch(`/api/csm/calendar?from=${from}&to=${to}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setItems(data.items ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao carregar calendário');
    } finally {
      setIsLoading(false);
    }
  }, [weekStart, view]);

  useEffect(() => { loadItems(); }, [loadItems]);

  // ── Navegação de semana ───────────────────────────────────────────────────
  const prevWeek = () => setWeekStart((w) => addDays(w, -7));
  const nextWeek = () => setWeekStart((w) => addDays(w, 7));
  const goToday  = () => setWeekStart(startOfWeek(new Date()));

  // ── Retry ────────────────────────────────────────────────────────────────
  const handleRetry = async (item: CalendarItem) => {
    if (isRetrying) return;
    setIsRetrying(true);
    setRetryMsg('');
    try {
      const res = await fetch('/api/csm/calendar/retry', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: item.id, collection: item.collection }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? `HTTP ${res.status}`);
      setRetryMsg('✓ ' + (data.message ?? 'Retry disparado'));
      // Atualiza o item local para refletir o novo status
      setItems((prev) => prev.map((it) =>
        it.id === item.id
          ? { ...it, status: item.collection === 'social_queue' ? 'planned' : 'generating_media' as any }
          : it
      ));
      if (selected?.id === item.id) {
        setSelected((prev) => prev ? { ...prev, status: item.collection === 'social_queue' ? 'planned' : 'generating_media' as any } : prev);
      }
      setTimeout(() => setRetryMsg(''), 3000);
    } catch (err) {
      setRetryMsg(`❌ ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setIsRetrying(false);
    }
  };

  // ── Abre popup ────────────────────────────────────────────────────────────
  const openItem = (item: CalendarItem) => {
    setSelected(item);
    setEditCopy(item.copy);
    setEditHashtags(item.hashtags.join(' '));
    const { date, time } = toLocalDatetimeValue(item.scheduled_at);
    setEditDate(date);
    setEditTime(time);
    setSaveMsg('');
  };

  // ── Salva edição ──────────────────────────────────────────────────────────
  const handleSave = async () => {
    if (!selected || !selected.editable) return;
    setIsSaving(true);
    setSaveMsg('');
    try {
      const scheduled_at = editDate && editTime
        ? new Date(`${editDate}T${editTime}:00`).toISOString()
        : selected.scheduled_at;

      const updates: Record<string, unknown> = { scheduled_at };
      if (selected.collection === 'social_queue') {
        updates['copy']     = editCopy;
        updates['hashtags'] = editHashtags.split(/\s+/).filter(Boolean);
      }

      const res = await fetch('/api/csm/calendar', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: selected.id, collection: selected.collection, updates }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? `HTTP ${res.status}`);

      // Atualiza item na lista local
      if (data.item) {
        setItems((prev) => prev.map((it) => it.id === selected.id ? data.item : it));
      }
      setSaveMsg('✓ Salvo');
      setTimeout(() => { setSaveMsg(''); setSelected(null); }, 1200);
    } catch (err) {
      setSaveMsg(`Erro: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setIsSaving(false);
    }
  };

  // ── Organiza itens por dia × hora (para visão semanal) ────────────────────
  const weekDays = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));

  const getItemsAt = (day: Date, hour: number): CalendarItem[] => {
    return items.filter((it) => {
      if (!it.scheduled_at) return false;
      try {
        const d = new Date(it.scheduled_at);
        return (
          d.getFullYear() === day.getFullYear() &&
          d.getMonth() === day.getMonth() &&
          d.getDate() === day.getDate() &&
          d.getHours() === hour
        );
      } catch { return false; }
    });
  };

  // Agrupa por dia para visão de lista
  const groupByDay = (): Record<string, CalendarItem[]> => {
    const g: Record<string, CalendarItem[]> = {};
    items.forEach((it) => {
      if (!it.scheduled_at) return;
      const key = it.scheduled_at.slice(0, 10);
      (g[key] = g[key] || []).push(it);
    });
    return g;
  };

  const pc = (platform: string) => PLATFORM_CONFIG[platform] ?? DEFAULT_PC;

  const weekLabel = `${fmtDate(weekStart)} – ${fmtDate(addDays(weekStart, 6))}`;

  return (
    <div className={styles.container}>
      {/* ── Header ─────────────────────────────────────────────── */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <div className={styles.kicker}>planejamento editorial</div>
          <h1 className={styles.title}>Calendário de Publicações</h1>
        </div>
        <div className={styles.controls}>
          <button className={styles.navBtn} onClick={prevWeek} title="Semana anterior">‹</button>
          <span className={styles.weekLabel}>{weekLabel}</span>
          <button className={styles.navBtn} onClick={nextWeek} title="Próxima semana">›</button>
          <button className={styles.todayBtn} onClick={goToday}>Hoje</button>
          <div className={styles.viewToggle}>
            <button
              className={`${styles.viewBtn} ${view === 'week' ? styles.viewBtnActive : ''}`}
              onClick={() => setView('week')}
            >Semana</button>
            <button
              className={`${styles.viewBtn} ${view === 'list' ? styles.viewBtnActive : ''}`}
              onClick={() => setView('list')}
            >Lista</button>
          </div>
          <button className={styles.navBtn} onClick={loadItems} title="Recarregar">↻</button>
        </div>
      </div>

      {/* ── Legenda ─────────────────────────────────────────────── */}
      <div className={styles.legend}>
        {Object.entries(PLATFORM_CONFIG).map(([key, cfg]) => (
          <div key={key} className={styles.legendItem}>
            <div className={styles.legendDot} style={{ background: cfg.color }} />
            <span>{cfg.icon} {key.replace('_', ' ')}</span>
          </div>
        ))}
      </div>

      {/* ── Loading / Error ─────────────────────────────────────── */}
      {isLoading && (
        <div className={styles.loadingState}>
          <div className={styles.spinner} />
          <span>Carregando planejamento...</span>
        </div>
      )}
      {error && !isLoading && (
        <div style={{ padding: '20px', color: '#e06555', fontFamily: 'JetBrains Mono, monospace', fontSize: '0.8rem' }}>
          ⚠ {error} <button onClick={loadItems} style={{ marginLeft: 12, color: '#e8873a', background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'inherit' }}>Tentar novamente</button>
        </div>
      )}

      {/* ── Visão semanal ───────────────────────────────────────── */}
      {!isLoading && !error && view === 'week' && (
        <div className={styles.weekGrid}>
          {/* Cabeçalho hora vazio */}
          <div className={styles.timeCol}>
            <div className={styles.timeHeader} />
            {HOURS.map((h) => (
              <div key={h} className={styles.timeSlot}>
                <span className={styles.timeLabel}>{String(h).padStart(2, '0')}h</span>
              </div>
            ))}
          </div>

          {/* Colunas de dia */}
          {weekDays.map((day, di) => (
            <div key={di}>
              <div className={`${styles.dayHeader} ${isToday(day) ? styles.isToday : ''}`}>
                <span className={styles.dayName}>{fmtDayName(day)}</span>
                <span className={styles.dayNum}>{day.getDate()}</span>
              </div>
              {HOURS.map((hour) => {
                const cellItems = getItemsAt(day, hour);
                return (
                  <div key={hour} className={`${styles.cell} ${isToday(day) ? styles.isToday : ''}`}>
                    {cellItems.slice(0, 2).map((it, idx) => {
                      const cfg = pc(it.platform);
                      return (
                        <div
                          key={it.id}
                          className={styles.eventCard}
                          style={{
                            top: `${2 + idx * 30}px`,
                            background: cfg.bg,
                            borderColor: cfg.border,
                            color: cfg.color,
                          }}
                          onClick={() => openItem(it)}
                          title={it.title}
                        >
                          <span className={styles.eventIcon}>{cfg.icon}</span>
                          <span className={styles.eventTitle}>{it.title || it.copy?.slice(0, 30)}</span>
                          <div
                            className={styles.statusDot}
                            style={{
                              background: it.status === 'published' ? '#5fce8a'
                                : it.status === 'failed' ? '#e06555'
                                : it.status === 'planned' ? '#6aa7e8'
                                : '#f5b56a',
                              marginLeft: 'auto',
                            }}
                          />
                        </div>
                      );
                    })}
                    {cellItems.length > 2 && (
                      <div style={{ position: 'absolute', bottom: 2, right: 4, fontSize: '0.6rem', color: '#8a8378', fontFamily: 'JetBrains Mono, monospace' }}>
                        +{cellItems.length - 2}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      )}

      {/* ── Visão de lista ──────────────────────────────────────── */}
      {!isLoading && !error && view === 'list' && (
        <div className={styles.listView}>
          {Object.keys(groupByDay()).length === 0 && (
            <div style={{ padding: '40px 20px', textAlign: 'center', color: '#4a4f5a', fontFamily: 'JetBrains Mono, monospace', fontSize: '0.78rem' }}>
              Nenhum conteúdo agendado neste período.
            </div>
          )}
          {Object.entries(groupByDay())
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([dateKey, dayItems]) => (
              <div key={dateKey} className={styles.listDay}>
                <div className={styles.listDayHeader}>
                  {new Date(dateKey + 'T12:00:00').toLocaleDateString('pt-BR', {
                    weekday: 'long', day: '2-digit', month: 'long',
                  })}
                </div>
                {dayItems
                  .sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at))
                  .map((it) => {
                    const cfg = pc(it.platform);
                    const timeStr = it.scheduled_at ? new Date(it.scheduled_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : '--:--';
                    return (
                      <div key={it.id} className={styles.listItem} onClick={() => openItem(it)}>
                        <span className={styles.listTime}>{timeStr}</span>
                        <span className={styles.listIcon}>{cfg.icon}</span>
                        <div className={styles.listBody}>
                          <div className={styles.listTitle}>{it.title || it.copy?.slice(0, 60) || '(sem título)'}</div>
                          <div className={styles.listMeta}>{it.platform} · {it.format}</div>
                        </div>
                        <span
                          className={styles.listStatusBadge}
                          style={{ color: it.status === 'published' ? '#5fce8a' : it.status === 'failed' ? '#e06555' : it.status === 'planned' ? '#6aa7e8' : '#f5b56a', borderColor: 'currentColor' }}
                        >
                          {STATUS_LABELS[it.status] ?? it.status}
                        </span>
                        {/* Retry inline — clicável sem abrir popup */}
                        {(it.status === 'failed' ||
                          (it.collection === 'content_projects' &&
                            Object.values(it.pipeline_stages ?? {}).some((s: any) => s?.status === 'error'))
                        ) && (
                          <button
                            className={styles.retryBtn}
                            style={{ padding: '4px 12px', fontSize: '0.72rem' }}
                            onClick={(e) => { e.stopPropagation(); handleRetry(it); }}
                            disabled={isRetrying}
                            title="Reiniciar a partir do ponto de falha"
                          >
                            ↺ Retry
                          </button>
                        )}
                      </div>
                    );
                  })}
              </div>
            ))}
        </div>
      )}

      {/* ── Popup de prévia / edição ────────────────────────────── */}
      {selected && (
        <div className={styles.overlay} onClick={(e) => { if (e.target === e.currentTarget) setSelected(null); }}>
          <div className={styles.popup} role="dialog" aria-modal="true" aria-label="Editar publicação">
            <button className={styles.popupClose} onClick={() => setSelected(null)}>×</button>

            {/* Platform badge */}
            <div className={styles.popupPlatformBadge} style={{ color: pc(selected.platform).color, borderColor: pc(selected.platform).border, background: pc(selected.platform).bg }}>
              {pc(selected.platform).icon} {selected.platform.replace('_', ' ')}
            </div>

            <div className={styles.popupTitle}>{selected.title || selected.copy?.slice(0, 80) || '(sem título)'}</div>
            <div className={styles.popupMeta}>
              <span><b>Formato:</b> {selected.format}</span>
              <span><b>Status:</b> {STATUS_LABELS[selected.status] ?? selected.status}</span>
              {selected.article_slug && <span><b>Artigo:</b> {selected.article_slug}</span>}
            </div>

            {/* Preview mídia */}
            {(selected.preview_url || selected.video_url) ? (
              <div className={styles.popupPreview}>
                {selected.preview_url
                  ? <img src={selected.preview_url} alt="preview" />
                  : <div className={styles.popupPreviewPlaceholder}>🎬 Vídeo gerado<br /><span style={{ fontSize: '0.65rem' }}>Abrir na plataforma após publicação</span></div>}
              </div>
            ) : selected.collection === 'content_projects' ? (
              <div className={styles.popupPreview}>
                <div className={styles.popupPreviewPlaceholder}>
                  {selected.status === 'generating_media' ? '⏳ Vídeo em geração...' : '🎬 Vídeo finalizado'}
                  {selected.pipeline_stages && (
                    <div className={styles.pipelineStatus} style={{ marginTop: 12, justifyContent: 'center' }}>
                      {Object.entries(selected.pipeline_stages).map(([stage, s]) => (
                        <span key={stage} className={styles.pipelineStage} style={{
                          color: s.status === 'completed' ? '#5fce8a' : s.status === 'error' ? '#e06555' : '#f5b56a',
                          borderColor: 'currentColor',
                          background: 'rgba(255,255,255,0.04)',
                        }}>
                          {s.status === 'completed' ? '✓' : s.status === 'error' ? '✗' : '⟳'} {stage}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ) : null}

            {/* Nota de imutabilidade */}
            {selected.video_url && (
              <div className={styles.immutableNote}>
                🔒 Vídeo e imagens já produzidos não podem ser alterados. Apenas texto, hashtags e agendamento são editáveis.
              </div>
            )}

            {/* Campos editáveis */}
            {selected.editable ? (
              <>
                {selected.collection === 'social_queue' && (
                  <>
                    <div className={styles.fieldGroup}>
                      <div className={styles.fieldLabel}>
                        Copy <span className={styles.fieldLabelHint}>— texto que será publicado</span>
                      </div>
                      <textarea
                        className={styles.textarea}
                        value={editCopy}
                        onChange={(e) => setEditCopy(e.target.value)}
                        rows={5}
                      />
                    </div>
                    <div className={styles.fieldGroup}>
                      <div className={styles.fieldLabel}>
                        Hashtags <span className={styles.fieldLabelHint}>— separadas por espaço</span>
                      </div>
                      <input
                        className={styles.input}
                        value={editHashtags}
                        onChange={(e) => setEditHashtags(e.target.value)}
                        placeholder="#ia #machinelearning #eozore"
                      />
                    </div>
                  </>
                )}

                <div className={styles.fieldGroup}>
                  <div className={styles.fieldLabel}>Data e Hora de Publicação</div>
                  <div className={styles.datetimeRow}>
                    <input type="date" className={styles.input} value={editDate} onChange={(e) => setEditDate(e.target.value)} />
                    <input type="time" className={styles.input} value={editTime} onChange={(e) => setEditTime(e.target.value)} />
                  </div>
                </div>
              </>
            ) : (
              <div className={styles.immutableNote}>
                Este item tem status &ldquo;{selected.status}&rdquo; e não pode ser editado.
              </div>
            )}

            <div className={styles.popupActions}>
              <button className={styles.cancelBtn} onClick={() => setSelected(null)}>Fechar</button>
              {/* Retry — aparece quando status é failed ou error (vídeo) */}
              {(selected.status === 'failed' ||
                (selected.collection === 'content_projects' &&
                  Object.values(selected.pipeline_stages ?? {}).some((s: any) => s?.status === 'error'))
              ) && (
                <button
                  className={styles.retryBtn}
                  onClick={() => handleRetry(selected)}
                  disabled={isRetrying}
                  title="Reinicia a partir do ponto de falha — texto volta para a fila, vídeo reinicia o stage com erro"
                >
                  {isRetrying ? <><span className={styles.savingSpinner} />Executando...</> : '↺ Retry'}
                </button>
              )}
              {retryMsg && (
                <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '0.72rem', color: retryMsg.startsWith('✓') ? '#5fce8a' : '#e06555' }}>
                  {retryMsg}
                </span>
              )}
              {selected.editable && (
                <button className={styles.saveBtn} onClick={handleSave} disabled={isSaving}>
                  {isSaving && <span className={styles.savingSpinner} />}
                  {saveMsg || (isSaving ? 'Salvando...' : 'Salvar')}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
