# Domain Entities — U-01: firestore-schema

> Referências: [unit-of-work.md](../../../inception/units-generation/unit-of-work.md) | [requirements.md](../../../inception/requirements-analysis/requirements.md) | [components.md](../../../inception/application-design/components.md) | [component-methods.md](../../../inception/application-design/component-methods.md) | [services.md](../../../inception/application-design/services.md) | [unit-of-work-story-map.md](../../../inception/units-generation/unit-of-work-story-map.md)

---

## TypeScript Types — `apps/web/src/types/pipeline.ts`

```typescript
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
  id:             StageId;
  label:          string;
  status:         StageStatus;
  retry_count:    number;       // 0-3
  max_retries:    number;       // sempre 3
  error_message?: string;
  error_type?:    'transient' | 'permanent';
  cost_real?:     number;       // R$ — definido quando completed
  cost_estimated?: number;      // R$ — estimativa inicial
  source?:        'pipeline' | 'manual';
  started_at?:    number;       // unix timestamp
  completed_at?:  number;
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
  status:   PublicationStatus;
  url?:     string;
  error?:   string;
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
  approval_data?: ApprovalData;
  scheduled_publish_at?: number; // unix timestamp UTC

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
  cost_limit:             number;  // R$ (default: 100)
  alert_threshold:        number;  // % (default: 80)
  exchange_rate_usd_brl:  number;  // default: 5.50
  schedule:               ScheduleConfig;
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
```

---

## Python Dataclasses — `agents/pipeline/shared/models.py`

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, Optional
from enum import Enum

# ── Enums ────────────────────────────────────────────────────────────────────

class ProjectStatus(str, Enum):
    CREATING              = "creating"
    AWAITING_APPROVAL     = "awaiting_approval"
    GENERATING_MEDIA      = "generating_media"
    AWAITING_PUBLICATION  = "awaiting_publication"
    PUBLISHING            = "publishing"
    PUBLISHED             = "published"
    ERROR                 = "error"

class StageStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    RETRYING  = "retrying"
    COMPLETED = "completed"
    ERROR     = "error"
    SKIPPED   = "skipped"

class StageId(str, Enum):
    TTS       = "tts"
    AVATAR    = "avatar"
    EDITOR    = "editor"
    PUBLISHER = "publisher"

class ChannelId(str, Enum):
    YOUTUBE        = "youtube"
    YOUTUBE_SHORT  = "youtube_short"
    INSTAGRAM_REEL = "instagram_reel"
    LINKEDIN       = "linkedin"
    THREADS        = "threads"
    BLOG           = "blog"
    FACEBOOK       = "facebook"

# ── Cost ─────────────────────────────────────────────────────────────────────

@dataclass
class CostBreakdown:
    total_real:      float = 0.0
    total_estimated: float = 0.0
    tts:    Optional[float] = None
    heygen: Optional[float] = None
    gemini: Optional[float] = None
    gcp:    Optional[float] = None

# ── Stage ────────────────────────────────────────────────────────────────────

@dataclass
class PipelineStage:
    id:              StageId
    label:           str
    status:          StageStatus = StageStatus.PENDING
    retry_count:     int = 0
    max_retries:     int = 3
    error_message:   Optional[str] = None
    error_type:      Optional[Literal["transient", "permanent"]] = None
    cost_real:       Optional[float] = None
    cost_estimated:  Optional[float] = None
    source:          Literal["pipeline", "manual"] = "pipeline"

# ── Avatar Lipsync ───────────────────────────────────────────────────────────

@dataclass
class LipsyncJob:
    lipsync_id: str
    status:     Literal["pending", "completed", "failed"] = "pending"
    video_url:  Optional[str] = None

@dataclass
class AvatarLipsyncJobs:
    horizontal: LipsyncJob
    vertical:   LipsyncJob

# ── Manifest Segment ─────────────────────────────────────────────────────────

@dataclass
class Segment:
    id:             str
    script:         str          # "" = slide puro (sem TTS/HeyGen)
    slide:          Optional[int]  # None = avatar puro (sem slide)
    beat:           str
    min_duration_s: float = 4.5
    pause_after_s:  float = 0.4

    @property
    def is_avatar_segment(self) -> bool:
        """True quando o segmento gera áudio e aciona HeyGen."""
        return bool(self.script)

    @property
    def is_slide_only(self) -> bool:
        """True quando o segmento é só slide (Playwright, zero HeyGen)."""
        return not self.script and self.slide is not None

@dataclass
class Manifest:
    version:  int
    video_id: str
    title:    str
    language: str
    youtube:  dict   # deck + resolution + segments
    reels:    list[dict]

    def get_avatar_segments(self, target: Literal["horizontal", "vertical"]) -> list[Segment]:
        """Retorna apenas segmentos com script != '' — os que geram custo HeyGen."""
        segs_raw = self.youtube["segments"] if target == "horizontal" else \
                   next(r["segments"] for r in self.reels if r.get("reel_id") == "reel-01")
        return [Segment(**s) for s in segs_raw if s.get("script")]

    def get_slide_only_segments(self, target: Literal["horizontal", "vertical"]) -> list[Segment]:
        """Retorna segmentos com script == '' — renderizados pelo Playwright."""
        segs_raw = self.youtube["segments"] if target == "horizontal" else \
                   next(r["segments"] for r in self.reels if r.get("reel_id") == "reel-01")
        return [Segment(**s) for s in segs_raw if not s.get("script") and s.get("slide") is not None]

# ── Pipeline Config ──────────────────────────────────────────────────────────

@dataclass
class PipelineConfig:
    cost_limit:            float = 100.0
    alert_threshold:       float = 80.0
    exchange_rate_usd_brl: float = 5.50
    schedule:              dict = field(default_factory=dict)

# ── Pub/Sub Message Contracts ────────────────────────────────────────────────

@dataclass
class PackageApprovedMsg:
    project_id:        str
    manifest_gcs_path: str
    channels_approved: list[str]
    approved_at:       str
    cost_limit:        float

@dataclass
class TtsCompletedMsg:
    project_id:    str
    audio_paths:   dict  # {"horizontal": [...], "vertical": [...]}
    total_cost_usd: float
    segment_count:  int

@dataclass
class AvatarCompletedMsg:
    project_id:             str
    horizontal_video_path:  str
    vertical_video_path:    str
    duration_seconds:       float
    total_cost_usd:         float

@dataclass
class VideoReadyMsg:
    project_id:       str
    horizontal_final: str
    vertical_final:   str
    duration_seconds: float
    trigger:          Literal["scheduled", "immediate"]
```

---

## Firestore Rules — `firestore.rules`

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {

    // content_projects: leitura/escrita apenas via Firebase Admin SDK (server-side)
    match /content_projects/{projectId} {
      allow read, write: if false;  // apenas Admin SDK
    }

    // pipeline_config: leitura/escrita apenas via Admin SDK
    match /pipeline_config/{tenantId} {
      allow read, write: if false;
    }

    // channel_config: leitura/escrita apenas via Admin SDK
    match /channel_config/{tenantId}/{channelId} {
      allow read, write: if false;
    }

    // agent_configurations: leitura/escrita apenas via Admin SDK
    match /agent_configurations/{doc} {
      allow read, write: if false;
    }

    // Coleções existentes (articles, csm_sessions): mantêm regras atuais
    match /articles/{articleId} {
      allow read: if true;
      allow write: if false;
    }
  }
}
```

---

## Firestore Indexes — `firestore.indexes.json`

```json
{
  "indexes": [
    {
      "collectionGroup": "content_projects",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "status", "order": "ASCENDING" },
        { "fieldPath": "created_at", "order": "DESCENDING" }
      ]
    },
    {
      "collectionGroup": "content_projects",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "status", "order": "ASCENDING" },
        { "fieldPath": "channels_approved", "arrayConfig": "CONTAINS" },
        { "fieldPath": "approval_data.approved_at", "order": "ASCENDING" }
      ]
    }
  ],
  "fieldOverrides": [
    {
      "collectionGroup": "lipsync_jobs",
      "fieldPath": "lipsync_id",
      "indexes": [
        { "order": "ASCENDING", "queryScope": "COLLECTION_GROUP" }
      ]
    }
  ]
}
```

**Nota:** O índice `collection_group` em `lipsync_jobs.lipsync_id` é obrigatório para o HeyGenCallbackHandler resolver `lipsync_id → project_id`.
