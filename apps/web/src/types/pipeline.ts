// ── Status Types ──────────────────────────────────────────────────────────────

export type ProjectStatus =
  | 'creating'              // CMO Agent está gerando o pacote
  | 'awaiting_approval'     // Aguardando aprovação do Victor para produção
  | 'generating_media'      // TTS + Avatar + VideoEditor rodando
  | 'awaiting_publication'  // Mídia pronta, aguardando aprovação de publicação
  | 'publishing'            // Publisher Service ativo
  | 'published'             // Todos os canais publicados
  | 'error';                // Algum job falhou após retries

export type StageStatus =
  | 'pending'    // Não iniciado
  | 'running'    // Job em execução (primeira tentativa)
  | 'retrying'   // Retry automático em andamento (sistema, sem CTA manual)
  | 'completed'  // Concluído com sucesso
  | 'error'      // Falhou após retries esgotados
  | 'skipped';   // Pulado manualmente por Victor

export type StageId = 'tts' | 'avatar' | 'editor' | 'publisher';

export type ChannelId =
  | 'youtube' | 'youtube_short' | 'instagram_reel'
  | 'linkedin' | 'threads' | 'blog' | 'facebook';

export type PublicationStatus =
  | 'published' | 'failed' | 'skipped' | 'skipped_duplicate' | 'throttled';

// ── Cost Types ─────────────────────────────────────────────────────────────────

export interface CostBreakdown {
  tts?:    number;  // R$ ElevenLabs
  heygen?: number;  // R$ HeyGen Lipsync
  gemini?: number;  // R$ Gemini
  gcp?:    number;  // R$ GCP infra
  total_real:      number;
  total_estimated: number;
}

// ── Stage Types ─────────────────────────────────────────────────────────────────

export interface PipelineStage {
  id:              StageId;
  label:           string;
  status:          StageStatus;
  retry_count:     number;       // 0-3
  max_retries:     number;       // sempre 3
  error_message?:  string;
  error_type?:     'transient' | 'permanent';
  cost_real?:      number;       // R$ — definido quando completed
  cost_estimated?: number;       // R$ — estimativa inicial
  source?:         'pipeline' | 'manual';
  started_at?:     number;       // unix timestamp
  completed_at?:   number;
}

// ── Avatar Lipsync Tracking ────────────────────────────────────────────────────

export interface LipsyncJob {
  lipsync_id: string;
  status:     'pending' | 'completed' | 'failed';
  video_url:  string | null;
}

export interface AvatarLipsyncJobs {
  horizontal: LipsyncJob;
  vertical:   LipsyncJob;
}

// ── Publication Result ─────────────────────────────────────────────────────────

export interface PublicationResult {
  status:        PublicationStatus;
  url?:          string;
  error?:        string;
  published_at?: number;
}

export type Publications = Partial<Record<ChannelId, PublicationResult>>;

// ── Cost Block ────────────────────────────────────────────────────────────────

export interface CostBlocked {
  blocked:        true;
  blocked_stage:  StageId;
  current_cost:   number;
  estimated_next: number;
  limit:          number;
  blocked_at:     number;
}

// ── Approval Data ─────────────────────────────────────────────────────────────

export interface ApprovalData {
  approved_by:       string;
  approved_at:       number;
  estimated_cost:    CostBreakdown;
  manifest_version:  number;
  channels_approved: ChannelId[];
  ai_disclosure:     true;
}

// ── Main Document: content_projects/{project_id} ──────────────────────────────

export interface ContentProject {
  id:           string;
  title:        string;
  status:       ProjectStatus;
  manifest_url: string;          // GCS URI do pacote HTML
  created_at:   number;
  created_by:   string;

  // Aprovação para produção (preenchido após gate 1)
  approval_data?:         ApprovalData;
  scheduled_publish_at?:  number; // unix timestamp UTC

  // Etapas do pipeline
  stages: {
    tts:       PipelineStage & { audio_paths?: string[] };
    avatar:    PipelineStage & { lipsync_jobs?: AvatarLipsyncJobs };
    editor:    PipelineStage & { horizontal_url?: string; vertical_url?: string };
    publisher: PipelineStage;
  };

  // Custo acumulado
  cost_breakdown: CostBreakdown;
  cost_blocked?:  CostBlocked;

  // Resultados de publicação
  publications?: Publications;

  // Canais aprovados para publicação (gate 2)
  channels_approved?: ChannelId[];
}

// ── Config Collections ────────────────────────────────────────────────────────

export interface ScheduleConfig {
  seg?: string | null;  // "18:00" ou null
  ter?: string | null;
  qua?: string | null;
  qui?: string | null;
  sex?: string | null;
  sab?: string | null;
  dom?: string | null;
}

export interface PipelineConfig {
  cost_limit:            number;  // R$ (default: 100)
  alert_threshold:       number;  // % (default: 80)
  exchange_rate_usd_brl: number;  // default: 5.50
  schedule:              ScheduleConfig;
}

export interface OAuthToken {
  value_secret_name: string;  // nome do secret no Secret Manager
  expires_at:        number;  // unix timestamp
}

export interface ChannelConfig {
  enabled:      boolean;
  max_per_day:  number;
  schedule?:    string | null;  // sobrescreve schedule global
  oauth_token?: OAuthToken;
}

// ── Firestore Collection Paths ────────────────────────────────────────────────
// content_projects/{project_id}
// pipeline_config/{tenantId}
// channel_config/{tenantId}/{channel_id}
