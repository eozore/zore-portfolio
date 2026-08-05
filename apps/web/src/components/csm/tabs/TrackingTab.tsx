/* ============================================================
   TrackingTab.tsx — Aba 4: Acompanhamento do pipeline
   Sem ação do usuário. Mostra status em tempo real do pipeline
   de produção (TTS, HeyGen, render, agendamento, publicação).
   ============================================================ */
'use client';

import { useState, useEffect } from 'react';
import type { DraftState } from '../CsmDashboard';

interface TrackingTabProps {
  draft: DraftState;
  sessionId: string;
  onBack: () => void;
}

interface PipelineStage {
  id: string;
  label: string;
  description: string;
  status: 'waiting' | 'running' | 'done' | 'error' | 'skipped';
  detail?: string;
  startedAt?: number;
  completedAt?: number;
}

interface ScheduledItem {
  platform: string;
  format: string;
  title: string;
  scheduledAt: string;
  status: string;
}

const STAGE_ORDER = ['tts', 'avatar', 'video_editor', 'publisher', 'scheduled'];
const STAGE_LABELS: Record<string, { label: string; description: string }> = {
  tts:          { label: 'Síntese de Voz',    description: 'ElevenLabs TTS gerando áudio para todos os segmentos' },
  avatar:        { label: 'Avatar HeyGen',     description: 'HeyGen gerando vídeos de avatar (segmentos sem slide)' },
  video_editor:  { label: 'Edição de Vídeo',  description: 'Playwright + FFmpeg compondo vídeo final' },
  publisher:     { label: 'Publicação',        description: 'Enviando para YouTube, LinkedIn, Instagram' },
  scheduled:     { label: 'Agendado',          description: 'Conteúdo na fila — scheduler publica automaticamente' },
};

const STATUS_COLORS: Record<string, string> = {
  waiting:  '#64748b',
  running:  '#f59e0b',
  done:     '#4ade80',
  error:    '#f87171',
  skipped:  '#475569',
};

const STATUS_ICONS: Record<string, string> = {
  waiting:  '○',
  running:  '⟳',
  done:     '✓',
  error:    '✗',
  skipped:  '–',
};

function formatDuration(ms: number): string {
  if (ms < 60_000) return `${Math.round(ms / 1000)}s`;
  return `${Math.round(ms / 60_000)}min`;
}

export default function TrackingTab({ draft, sessionId, onBack }: TrackingTabProps) {
  const [stages, setStages] = useState<PipelineStage[]>(
    STAGE_ORDER.map((id) => ({
      id,
      ...STAGE_LABELS[id],
      status: 'waiting',
    }))
  );
  const [scheduledItems, setScheduledItems] = useState<ScheduledItem[]>([]);
  const [lastPolled, setLastPolled] = useState<Date | null>(null);
  const [isComplete, setIsComplete] = useState(false);

  // Poll /api/csm/pipeline-status a cada 15s
  useEffect(() => {
    if (!sessionId || isComplete) return;

    const poll = async () => {
      try {
        const res = await fetch(`/api/csm/pipeline-status?sessionId=${sessionId}`);
        if (!res.ok) return;
        const data = await res.json();
        setLastPolled(new Date());

        if (data.stages) {
          setStages(
            STAGE_ORDER.map((id) => ({
              id,
              ...STAGE_LABELS[id],
              status:      data.stages[id]?.status ?? 'waiting',
              detail:      data.stages[id]?.detail,
              startedAt:   data.stages[id]?.started_at,
              completedAt: data.stages[id]?.completed_at,
            }))
          );
        }

        if (data.scheduledItems) {
          setScheduledItems(data.scheduledItems);
        }

        // Pipeline completo quando publisher ou scheduled está done
        const publisherDone = data.stages?.publisher?.status === 'completed' ||
                              data.stages?.scheduled?.status === 'completed';
        if (publisherDone) setIsComplete(true);

      } catch { /* silent */ }
    };

    poll(); // poll imediato
    const interval = setInterval(poll, 15_000);
    return () => clearInterval(interval);
  }, [sessionId, isComplete]);

  const articleUrl = draft.publishedArticleUrl;
  const title      = draft.suggestedTitle || draft.pauta?.titulo || 'Artigo';

  return (
    <div style={{ maxWidth: '760px', margin: '0 auto', padding: '32px 16px', color: '#eae4dc' }}>
      <button onClick={onBack} style={{ background: 'transparent', border: '1px solid rgba(255,255,255,0.12)', color: '#94a3b8', padding: '8px 16px', borderRadius: '8px', cursor: 'pointer', marginBottom: '24px', fontSize: '0.85rem' }}>
        ← Revisão
      </button>

      {/* Header */}
      <div style={{ marginBottom: '32px' }}>
        <div style={{ fontSize: '0.72rem', letterSpacing: '0.1em', color: '#64748b', textTransform: 'uppercase', marginBottom: '6px' }}>
          pipeline de produção
        </div>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#fff', margin: 0 }}>{title}</h1>
        {articleUrl && (
          <a href={articleUrl} target="_blank" rel="noopener noreferrer"
            style={{ color: '#7c3aed', fontSize: '0.85rem', textDecoration: 'underline', marginTop: '4px', display: 'inline-block' }}>
            {articleUrl}
          </a>
        )}
        {lastPolled && (
          <div style={{ color: '#475569', fontSize: '0.72rem', marginTop: '4px' }}>
            Última atualização: {lastPolled.toLocaleTimeString('pt-BR')} · atualiza a cada 15s
          </div>
        )}
      </div>

      {/* Pipeline stages */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0' }}>
        {stages.map((stage, idx) => {
          const color    = STATUS_COLORS[stage.status];
          const icon     = STATUS_ICONS[stage.status];
          const isLast   = idx === stages.length - 1;
          const duration = stage.startedAt && stage.completedAt
            ? formatDuration(stage.completedAt - stage.startedAt)
            : undefined;

          return (
            <div key={stage.id} style={{ display: 'flex', gap: '16px', position: 'relative' }}>
              {/* Timeline line */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: '32px' }}>
                <div style={{
                  width: '32px', height: '32px', borderRadius: '50%',
                  background: `rgba(${stage.status === 'done' ? '74,222,128' : stage.status === 'running' ? '245,158,11' : stage.status === 'error' ? '248,113,113' : '71,85,105'},0.15)`,
                  border: `2px solid ${color}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: '0.9rem', color,
                  animation: stage.status === 'running' ? 'spin 1s linear infinite' : undefined,
                }}>
                  {icon}
                </div>
                {!isLast && <div style={{ width: '2px', flex: 1, background: 'rgba(255,255,255,0.06)', minHeight: '32px' }} />}
              </div>

              {/* Stage info */}
              <div style={{ flex: 1, paddingBottom: isLast ? 0 : '24px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '2px' }}>
                  <span style={{ fontWeight: 700, color: stage.status === 'waiting' ? '#64748b' : '#fff', fontSize: '0.95rem' }}>
                    {stage.label}
                  </span>
                  {duration && (
                    <span style={{ fontSize: '0.72rem', color: '#4ade80', background: 'rgba(74,222,128,0.1)', padding: '2px 6px', borderRadius: '4px' }}>
                      {duration}
                    </span>
                  )}
                  {stage.status === 'running' && (
                    <span style={{ fontSize: '0.72rem', color: '#f59e0b', background: 'rgba(245,158,11,0.1)', padding: '2px 6px', borderRadius: '4px', animation: 'pulse 1.5s ease-in-out infinite' }}>
                      em execução
                    </span>
                  )}
                </div>
                <div style={{ fontSize: '0.8rem', color: '#64748b' }}>{stage.description}</div>
                {stage.detail && (
                  <div style={{ fontSize: '0.78rem', color: stage.status === 'error' ? '#f87171' : '#94a3b8', marginTop: '4px', background: 'rgba(255,255,255,0.03)', padding: '6px 10px', borderRadius: '6px', fontFamily: 'monospace' }}>
                    {stage.detail}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse { 0%,100% { opacity:1 } 50% { opacity:0.5 } }
      `}</style>

      {/* Conteúdo agendado */}
      {scheduledItems.length > 0 && (
        <div style={{ marginTop: '32px' }}>
          <div style={{ fontSize: '0.72rem', letterSpacing: '0.1em', color: '#64748b', textTransform: 'uppercase', marginBottom: '12px' }}>
            fila de publicação
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {scheduledItems.slice(0, 10).map((item, i) => (
              <div key={i} style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '10px', padding: '12px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: '0.85rem', color: '#fff' }}>{item.title?.slice(0, 60) || item.format}</div>
                  <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: '2px' }}>{item.platform} · {item.format}</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
                    {item.scheduledAt ? new Date(item.scheduledAt).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '–'}
                  </div>
                  <div style={{ fontSize: '0.7rem', color: item.status === 'aprovado' ? '#4ade80' : '#64748b', marginTop: '2px' }}>
                    {item.status}
                  </div>
                </div>
              </div>
            ))}
          </div>
          {scheduledItems.length > 10 && (
            <div style={{ color: '#64748b', fontSize: '0.78rem', textAlign: 'center', marginTop: '8px' }}>
              +{scheduledItems.length - 10} itens na fila
            </div>
          )}
        </div>
      )}

      {/* Estado de conclusão */}
      {isComplete && (
        <div style={{ marginTop: '32px', padding: '20px', background: 'rgba(74,222,128,0.08)', border: '1px solid rgba(74,222,128,0.2)', borderRadius: '12px', textAlign: 'center' }}>
          <div style={{ fontSize: '1.5rem', marginBottom: '8px' }}>🎉</div>
          <div style={{ fontWeight: 800, color: '#4ade80', fontSize: '1rem', marginBottom: '4px' }}>Pipeline Concluído</div>
          <div style={{ color: '#94a3b8', fontSize: '0.85rem' }}>
            O conteúdo está sendo publicado automaticamente pelo scheduler.
            O vídeo do YouTube sai primeiro, depois todos os demais apontam para ele.
          </div>
        </div>
      )}
    </div>
  );
}
