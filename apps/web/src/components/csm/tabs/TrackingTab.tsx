/* ============================================================
   TrackingTab.tsx — Aba 4: Acompanhamento do pipeline
   Sem ação do usuário. Mostra status em tempo real do pipeline
   de produção (TTS, HeyGen, render, agendamento, publicação).
   ============================================================ */
'use client';

import { useState, useEffect } from 'react';
import type { DraftState } from '../CsmDashboard';
import { computeHealth, elapsedLabel } from '@/lib/pipelineHealth';

interface TrackingTabProps {
  draft: DraftState;
  sessionId: string;
  onBack: () => void;
}

interface PipelineStage {
  id: string;
  label: string;
  description: string;
  status: 'waiting' | 'running' | 'stuck' | 'done' | 'error' | 'skipped';
  detail?: string;
  startedAt?: number;
  completedAt?: number;
}

/** Mapeia o id do stage na UI para a chave de tolerância em lib/pipelineHealth. */
const HEALTH_KIND: Record<string, string> = {
  tts: 'tts', avatar: 'avatar', video_editor: 'editor',
  vertical_cut: 'editor', publisher: 'publisher',
};

interface ScheduledItem {
  platform: string;
  format: string;
  title: string;
  scheduledAt: string;
  status: string;
}

/** O que o backend informa sobre o vídeo produzido. */
interface VideoStatus {
  horizontalReady: boolean;
  durationSeconds: number | null;
  avatarShare:     number | null;
  youtubeVideoId:  string | null;
  youtubeUrl:      string | null;
  verticalUrl:     string | null;
}

const STAGE_ORDER = ['tts', 'avatar', 'video_editor', 'publisher', 'vertical_cut', 'scheduled'];
const STAGE_LABELS: Record<string, { label: string; description: string }> = {
  tts:          { label: 'Síntese de Voz',    description: 'ElevenLabs gerando a locução de todos os segmentos' },
  avatar:        { label: 'Avatar HeyGen',     description: 'HeyGen gerando só os segmentos de avatar (~20% do vídeo)' },
  video_editor:  { label: 'Edição de Vídeo',  description: 'Alternando avatar e ilustração em tela cheia' },
  publisher:     { label: 'Publicação',        description: 'Sobe o vídeo longo no YouTube como privado' },
  vertical_cut:  { label: 'Corte Vertical',    description: 'Reel e Short recortados do vídeo longo — sob demanda' },
  scheduled:     { label: 'Agendado',          description: 'Conteúdo na fila — scheduler publica automaticamente' },
};

const STATUS_COLORS: Record<string, string> = {
  waiting:  '#8a8a8a',
  running:  '#2563eb',
  stuck:    '#d97706',
  done:     '#16a34a',
  error:    '#dc2626',
  skipped:  '#4a4a4a',
};

const STATUS_ICONS: Record<string, string> = {
  waiting:  '○',
  running:  '⟳',
  stuck:    '⏸',
  done:     '✓',
  error:    '✗',
  skipped:  '–',
};

const STATUS_TEXT_LABEL: Record<string, string> = {
  waiting: 'aguardando', running: 'em execução', stuck: 'travado — sem atualização', done: 'concluído', error: 'erro', skipped: '—',
};

function formatDuration(ms: number): string {
  if (ms < 60_000) return `${Math.round(ms / 1000)}s`;
  return `${Math.round(ms / 60_000)}min`;
}

/**
 * Os Cloud Run Jobs gravam status brutos no Firestore (pending, running,
 * completed, error, pending_callback...) — normaliza para o vocabulário de UI
 * (waiting, running, stuck, done, error, skipped) usado pelos mapas de cor/ícone.
 *
 * "stuck" é a diferença real: sem isso, um Job que travou por OOM ou perdeu a
 * mensagem Pub/Sub fica "running" com spinner girando pra sempre, e não tem
 * como o usuário saber se ainda está processando ou morreu silenciosamente.
 */
function normalizeStatus(stageId: string, raw: string | undefined, startedAtMs: number | undefined): PipelineStage['status'] {
  if (raw === 'skipped') return 'skipped';
  if (!raw || raw === 'pending' || raw === 'waiting') return 'waiting';
  const health = computeHealth(raw, startedAtMs, HEALTH_KIND[stageId] ?? 'default');
  if (health === 'idle') return 'waiting';
  return health; // 'running' | 'stuck' | 'done' | 'error'
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
  const [projectId, setProjectId] = useState<string | null>(null);
  const [retryingStage, setRetryingStage] = useState<string | null>(null);
  const [retryMsg, setRetryMsg] = useState<{ stage: string; text: string; ok: boolean } | null>(null);
  const [video, setVideo] = useState<VideoStatus | null>(null);
  const [derivingVertical, setDerivingVertical] = useState(false);
  const [deriveMsg, setDeriveMsg] = useState<{ text: string; ok: boolean } | null>(null);

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
              status:      normalizeStatus(id, data.stages[id]?.status, data.stages[id]?.started_at),
              detail:      data.stages[id]?.detail,
              startedAt:   data.stages[id]?.started_at,
              completedAt: data.stages[id]?.completed_at,
            }))
          );
        }

        if (data.projectId) setProjectId(data.projectId);
        if (data.video) setVideo(data.video as VideoStatus);

        if (data.scheduledItems) {
          setScheduledItems(data.scheduledItems);
        }

        // O polling só para quando não há mais nada em movimento. Antes ele
        // parava assim que o publisher terminava — e o corte vertical, que
        // acontece depois, nunca aparecia atualizado na tela.
        const publisherDone = data.stages?.publisher?.status === 'completed' ||
                              data.stages?.scheduled?.status === 'completed';
        const verticalState = data.stages?.vertical_cut?.status;
        const verticalIdle  = !verticalState ||
                              ['completed', 'error'].includes(String(verticalState));
        if (publisherDone && verticalIdle) setIsComplete(true);

      } catch { /* silent */ }
    };

    poll(); // poll imediato
    const interval = setInterval(poll, 15_000);
    return () => clearInterval(interval);
  }, [sessionId, isComplete]);

  const articleUrl = draft.publishedArticleUrl;
  const title      = draft.suggestedTitle || draft.pauta?.titulo || 'Artigo';

  // O backend detecta sozinho qual stage está com erro e retoma só a partir
  // dali (stages já concluídos não são refeitos — ver /api/csm/calendar/retry).
  const firstErrorStage = stages.find((s) => s.status === 'error');

  const handleRetryStage = async () => {
    if (!projectId || retryingStage) return;
    setRetryingStage(firstErrorStage?.id ?? 'unknown');
    setRetryMsg(null);
    try {
      const res = await fetch('/api/csm/calendar/retry', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: projectId, collection: 'content_projects' }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      setRetryMsg({ stage: firstErrorStage?.id ?? '', text: data.message ?? 'Retomado com sucesso.', ok: true });
      setIsComplete(false); // volta a pollar
    } catch (err) {
      setRetryMsg({
        stage: firstErrorStage?.id ?? '',
        text: err instanceof Error ? err.message : 'Falha ao retomar',
        ok: false,
      });
    } finally {
      setRetryingStage(null);
    }
  };

  // O pacote de conteúdos é derivado do vídeo do YouTube, então só faz sentido
  // depois que ele existe e está no canal. Publicar antes era o que produzia
  // Reels sem relação nenhuma com o vídeo — e, no ciclo de 16/08, vídeos
  // curtos indo ao ar enquanto o longo nem tinha sido montado.
  const videoReady    = Boolean(video?.horizontalReady && video?.youtubeVideoId);
  const verticalStage = stages.find((s) => s.id === 'vertical_cut');
  const verticalBusy  = derivingVertical || verticalStage?.status === 'running';
  const verticalDone  = Boolean(video?.verticalUrl);

  const handleDeriveVertical = async () => {
    if (!projectId || verticalBusy) return;
    setDerivingVertical(true);
    setDeriveMsg(null);
    try {
      const res = await fetch('/api/csm/derive-vertical', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ projectId }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok && res.status !== 202) throw new Error(data.error || `HTTP ${res.status}`);
      setDeriveMsg({
        text: 'Corte vertical enfileirado — Reel e Short saem do mesmo arquivo.',
        ok: true,
      });
      setIsComplete(false); // volta a pollar para acompanhar o corte
    } catch (err) {
      setDeriveMsg({
        text: err instanceof Error ? err.message : 'Falha ao enfileirar o corte vertical',
        ok: false,
      });
    } finally {
      setDerivingVertical(false);
    }
  };

  return (
    <div style={{ maxWidth: '760px', margin: '0 auto', padding: '32px 16px', color: '#1e1e1e' }}>
      <button onClick={onBack} style={{ background: 'transparent', border: '1px solid rgba(30,30,30,0.12)', color: '#6b6b6b', padding: '8px 16px', borderRadius: '8px', cursor: 'pointer', marginBottom: '24px', fontSize: '0.85rem' }}>
        ← Revisão
      </button>

      {/* Header */}
      <div style={{ marginBottom: '32px' }}>
        <div style={{ fontSize: '0.72rem', letterSpacing: '0.1em', color: '#8a8a8a', textTransform: 'uppercase', marginBottom: '6px' }}>
          pipeline de produção
        </div>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#1e1e1e', margin: 0 }}>{title}</h1>
        {articleUrl && (
          <a href={articleUrl} target="_blank" rel="noopener noreferrer"
            style={{ color: '#7c3aed', fontSize: '0.85rem', textDecoration: 'underline', marginTop: '4px', display: 'inline-block' }}>
            {articleUrl}
          </a>
        )}
        {lastPolled && (
          <div style={{ color: '#4a4a4a', fontSize: '0.72rem', marginTop: '4px' }}>
            Última atualização: {lastPolled.toLocaleTimeString('pt-BR')} · atualiza a cada 15s
          </div>
        )}
      </div>

      {/* Vídeo do YouTube + liberação do pacote de conteúdos derivados */}
      {video?.horizontalReady && (
        <div style={{
          border: '1px solid rgba(30,30,30,0.12)', borderRadius: '12px',
          padding: '20px', marginBottom: '28px', background: 'rgba(124,58,237,0.04)',
        }}>
          <div style={{ fontSize: '0.72rem', letterSpacing: '0.1em', color: '#8a8a8a', textTransform: 'uppercase', marginBottom: '8px' }}>
            vídeo do youtube
          </div>
          <div style={{ fontSize: '0.9rem', color: '#1e1e1e', marginBottom: '4px' }}>
            {video.durationSeconds ? `${Math.round(video.durationSeconds / 60)} min` : 'pronto'}
            {video.avatarShare !== null && ` · ${Math.round(video.avatarShare * 100)}% de avatar, o resto em ilustração`}
          </div>

          {video.youtubeUrl ? (
            <>
              <a href={video.youtubeUrl} target="_blank" rel="noopener noreferrer"
                style={{ color: '#7c3aed', fontSize: '0.85rem', textDecoration: 'underline' }}>
                {video.youtubeUrl}
              </a>
              <p style={{ fontSize: '0.8rem', color: '#4a4a4a', margin: '12px 0 0' }}>
                O vídeo subiu como <strong>privado</strong>. Assista, torne público no
                YouTube Studio e então gere o pacote — Reel e Short são recortes deste
                mesmo vídeo, sem nova geração de avatar.
              </p>
            </>
          ) : (
            <p style={{ fontSize: '0.8rem', color: '#4a4a4a', margin: '8px 0 0' }}>
              Aguardando o upload para o YouTube terminar.
            </p>
          )}

          {verticalDone ? (
            <div style={{ fontSize: '0.85rem', color: '#15803d', marginTop: '14px' }}>
              ✓ Peça vertical pronta (Reel + Short saem do mesmo arquivo).
            </div>
          ) : (
            <button
              onClick={handleDeriveVertical}
              disabled={!videoReady || verticalBusy}
              title={videoReady ? undefined : 'Disponível depois que o vídeo estiver no YouTube'}
              style={{
                marginTop: '14px', padding: '10px 18px', borderRadius: '8px',
                border: 'none', fontSize: '0.85rem', fontWeight: 600,
                background: videoReady && !verticalBusy ? '#7c3aed' : 'rgba(30,30,30,0.12)',
                color: videoReady && !verticalBusy ? '#fff' : '#6b6b6b',
                cursor: videoReady && !verticalBusy ? 'pointer' : 'not-allowed',
              }}
            >
              {verticalBusy ? 'Cortando…' : 'Gerar pacote de conteúdos'}
            </button>
          )}

          {deriveMsg && (
            <div style={{ marginTop: '10px', fontSize: '0.8rem', color: deriveMsg.ok ? '#15803d' : '#b91c1c' }}>
              {deriveMsg.text}
            </div>
          )}
        </div>
      )}

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
                {!isLast && <div style={{ width: '2px', flex: 1, background: 'rgba(30,30,30,0.06)', minHeight: '32px' }} />}
              </div>

              {/* Stage info */}
              <div style={{ flex: 1, paddingBottom: isLast ? 0 : '24px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '2px' }}>
                  <span style={{ fontWeight: 700, color: stage.status === 'waiting' ? '#8a8a8a' : '#1e1e1e', fontSize: '0.95rem' }}>
                    {stage.label}
                  </span>
                  {duration && (
                    <span style={{ fontSize: '0.72rem', color: '#16a34a', background: 'rgba(22,163,74,0.1)', padding: '2px 6px', borderRadius: '4px' }}>
                      {duration}
                    </span>
                  )}
                  {stage.status === 'running' && (
                    <span style={{ fontSize: '0.72rem', color: '#d97706', background: 'rgba(245,158,11,0.1)', padding: '2px 6px', borderRadius: '4px', animation: 'pulse 1.5s ease-in-out infinite' }}>
                      em execução
                    </span>
                  )}
                </div>
                <div style={{ fontSize: '0.8rem', color: '#8a8a8a' }}>{stage.description}</div>
                {stage.detail && (
                  <div style={{ fontSize: '0.78rem', color: stage.status === 'error' ? '#dc2626' : '#6b6b6b', marginTop: '4px', background: 'rgba(30,30,30,0.03)', padding: '6px 10px', borderRadius: '6px', fontFamily: 'monospace' }}>
                    {stage.detail}
                  </div>
                )}
                {stage.status === 'error' && firstErrorStage?.id === stage.id && projectId && (
                  <div style={{ marginTop: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <button
                      onClick={handleRetryStage}
                      disabled={!!retryingStage}
                      style={{
                        fontSize: '0.75rem', fontWeight: 700, padding: '6px 14px', borderRadius: '8px',
                        border: '1px solid rgba(220,38,38,0.35)', background: 'rgba(220,38,38,0.1)',
                        color: '#dc2626', cursor: retryingStage ? 'wait' : 'pointer',
                      }}
                    >
                      {retryingStage ? 'Retomando…' : `↺ Retomar a partir de "${stage.label}"`}
                    </button>
                    <span style={{ fontSize: '0.7rem', color: '#8a8a8a' }}>
                      Reprocessa só este asset — o que já foi feito antes não é refeito.
                    </span>
                  </div>
                )}
                {retryMsg && retryMsg.stage === stage.id && (
                  <div style={{ marginTop: '6px', fontSize: '0.75rem', color: retryMsg.ok ? '#16a34a' : '#dc2626' }}>
                    {retryMsg.ok ? '✓ ' : '✗ '}{retryMsg.text}
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

      {/* Plano da semana — persistido no draft na aprovação */}
      {(draft.publishPlan?.length ?? 0) > 0 && (
        <div style={{ marginTop: '32px' }}>
          <div style={{ fontSize: '0.72rem', letterSpacing: '0.1em', color: '#8a8a8a', textTransform: 'uppercase', marginBottom: '12px' }}>
            plano da semana · publicação automática de hora em hora
          </div>
          <div style={{ background: '#ffffff', border: '1px solid rgba(30,30,30,0.1)', borderRadius: '12px', padding: '14px 18px' }}>
            {draft.publishPlan!.map((day) => (
              <div key={day.day} style={{ marginBottom: '10px' }}>
                <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#e67e22', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: '4px' }}>
                  Dia {day.day} · {new Date(day.date).toLocaleDateString('pt-BR', { weekday: 'short', day: '2-digit', month: '2-digit' })}
                </div>
                {day.items.map((item, i) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', padding: '4px 0', borderBottom: '1px solid rgba(30,30,30,0.05)', fontSize: '0.8rem' }}>
                    <span style={{ color: '#1e1e1e', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <b style={{ color: '#6b6b6b', fontWeight: 600 }}>{item.platform}</b> · {item.title || item.format}
                    </span>
                    <span style={{ color: '#6b6b6b', flexShrink: 0, fontFamily: 'monospace' }}>
                      {new Date(item.scheduledAt).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Conteúdo agendado */}
      {scheduledItems.length > 0 && (
        <div style={{ marginTop: '32px' }}>
          <div style={{ fontSize: '0.72rem', letterSpacing: '0.1em', color: '#8a8a8a', textTransform: 'uppercase', marginBottom: '12px' }}>
            fila de publicação
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {scheduledItems.slice(0, 10).map((item, i) => (
              <div key={i} style={{ background: 'rgba(30,30,30,0.03)', border: '1px solid rgba(30,30,30,0.06)', borderRadius: '10px', padding: '12px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: '0.85rem', color: '#1e1e1e' }}>{item.title?.slice(0, 60) || item.format}</div>
                  <div style={{ fontSize: '0.72rem', color: '#8a8a8a', marginTop: '2px' }}>{item.platform} · {item.format}</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '0.78rem', color: '#6b6b6b' }}>
                    {item.scheduledAt ? new Date(item.scheduledAt).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '–'}
                  </div>
                  <div style={{ fontSize: '0.7rem', color: item.status === 'aprovado' ? '#16a34a' : '#8a8a8a', marginTop: '2px' }}>
                    {item.status}
                  </div>
                </div>
              </div>
            ))}
          </div>
          {scheduledItems.length > 10 && (
            <div style={{ color: '#8a8a8a', fontSize: '0.78rem', textAlign: 'center', marginTop: '8px' }}>
              +{scheduledItems.length - 10} itens na fila
            </div>
          )}
        </div>
      )}

      {/* Estado de conclusão */}
      {isComplete && (
        <div style={{ marginTop: '32px', padding: '20px', background: 'rgba(22,163,74,0.08)', border: '1px solid rgba(22,163,74,0.2)', borderRadius: '12px', textAlign: 'center' }}>
          <div style={{ fontSize: '1.5rem', marginBottom: '8px' }}>🎉</div>
          <div style={{ fontWeight: 800, color: '#16a34a', fontSize: '1rem', marginBottom: '4px' }}>Pipeline Concluído</div>
          <div style={{ color: '#6b6b6b', fontSize: '0.85rem' }}>
            O conteúdo está sendo publicado automaticamente pelo scheduler.
            O vídeo do YouTube sai primeiro, depois todos os demais apontam para ele.
          </div>
        </div>
      )}
    </div>
  );
}
