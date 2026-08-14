/**
 * pipelineHealth.ts — Detecção de "travado" para qualquer etapa assíncrona
 * (geração de pacote, TTS, avatar, editor, publisher).
 *
 * O problema que isso resolve: um stage em "running"/"pending" nunca vira
 * "erro" sozinho quando o Cloud Run Job trava, cai por OOM sem gravar
 * error_message, ou uma mensagem Pub/Sub se perde — ele fica "rodando" para
 * sempre aos olhos do Firestore. Sem um limite de tempo, a UI mostra um
 * spinner indefinido e o usuário não tem como saber se ainda está
 * processando ou se já morreu silenciosamente.
 */

export type HealthStatus = 'idle' | 'running' | 'stuck' | 'done' | 'error';

/** Minutos de tolerância por tipo de etapa antes de marcar como travado. */
export const STUCK_THRESHOLD_MINUTES: Record<string, number> = {
  package: 8,      // geração de artigo/roteiro/pacote via LLM
  tts: 15,         // síntese de voz por segmento
  avatar: 40,       // HeyGen renderiza de forma assíncrona via webhook — mais lento
  editor: 20,       // Playwright + FFmpeg compondo o vídeo final
  publisher: 15,    // upload para YouTube/Instagram/LinkedIn
  default: 20,
};

/**
 * @param rawStatus    status bruto vindo do Firestore (running, pending, completed, error...)
 * @param startedAtMs  epoch ms de quando a etapa começou (undefined se nunca começou)
 * @param stageKind    usado para escolher o limite de tolerância
 * @param now          injetável para testes
 */
export function computeHealth(
  rawStatus: string | undefined,
  startedAtMs: number | undefined,
  stageKind: keyof typeof STUCK_THRESHOLD_MINUTES | string = 'default',
  now: number = Date.now(),
): HealthStatus {
  const normalized = (rawStatus || '').toLowerCase();

  if (normalized === 'error' || normalized === 'failed') return 'error';
  if (normalized === 'completed' || normalized === 'done' || normalized === 'published' || normalized === 'ready') return 'done';

  const isActive = normalized === 'running' || normalized === 'processing' || normalized === 'pending' || normalized === 'pending_callback' || normalized === 'generating';
  if (!isActive) return 'idle';

  if (!startedAtMs) return 'running'; // ativo mas sem timestamp — não dá pra medir, assume ok
  const thresholdMs = (STUCK_THRESHOLD_MINUTES[stageKind] ?? STUCK_THRESHOLD_MINUTES.default) * 60_000;
  return now - startedAtMs > thresholdMs ? 'stuck' : 'running';
}

export function elapsedLabel(startedAtMs: number | undefined, now: number = Date.now()): string {
  if (!startedAtMs) return '';
  const minutes = Math.floor((now - startedAtMs) / 60_000);
  if (minutes < 1) return 'agora mesmo';
  if (minutes < 60) return `há ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `há ${hours}h`;
  return `há ${Math.floor(hours / 24)}d`;
}
