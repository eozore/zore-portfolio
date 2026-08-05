"""
agents/pipeline/shared/models.py
=================================
Dataclasses, Enums e contratos de mensagens Pub/Sub para a content pipeline.

Todos os tipos espelham exatamente os TypeScript types em
apps/web/src/types/pipeline.ts — nenhuma divergência de campo permitida.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


# ── Enums ─────────────────────────────────────────────────────────────────────


class ProjectStatus(str, Enum):
    CREATING             = "creating"
    AWAITING_APPROVAL    = "awaiting_approval"
    GENERATING_MEDIA     = "generating_media"
    AWAITING_PUBLICATION = "awaiting_publication"
    PUBLISHING           = "publishing"
    PUBLISHED            = "published"
    ERROR                = "error"


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


# ── Cost ──────────────────────────────────────────────────────────────────────


@dataclass
class CostBreakdown:
    total_real:      float = 0.0
    total_estimated: float = 0.0
    tts:    Optional[float] = None  # R$ ElevenLabs
    heygen: Optional[float] = None  # R$ HeyGen Lipsync
    gemini: Optional[float] = None  # R$ Gemini
    gcp:    Optional[float] = None  # R$ GCP infra


# ── Stage ─────────────────────────────────────────────────────────────────────


@dataclass
class PipelineStage:
    id:             StageId
    label:          str
    status:         StageStatus             = StageStatus.PENDING
    retry_count:    int                     = 0
    max_retries:    int                     = 3
    error_message:  Optional[str]           = None
    error_type:     Optional[Literal["transient", "permanent"]] = None
    cost_real:      Optional[float]         = None
    cost_estimated: Optional[float]         = None
    source:         Literal["pipeline", "manual"] = "pipeline"
    started_at:     Optional[int]           = None  # unix timestamp
    completed_at:   Optional[int]           = None  # unix timestamp


# ── Avatar Lipsync ────────────────────────────────────────────────────────────


@dataclass
class LipsyncJob:
    lipsync_id: str
    status:     Literal["pending", "completed", "failed"] = "pending"
    video_url:  Optional[str] = None


@dataclass
class AvatarLipsyncJobs:
    horizontal: LipsyncJob
    vertical:   LipsyncJob


# ── Manifest Segment ──────────────────────────────────────────────────────────


@dataclass
class Segment:
    id:             str
    script:         str           # "" = slide puro (sem TTS/HeyGen)
    beat:           str
    slide:          Optional[int] = None  # None = avatar puro (sem slide)
    min_duration_s: float         = 4.5
    pause_after_s:  float         = 0.4

    @property
    def needs_tts(self) -> bool:
        """True quando o segmento precisa de áudio TTS (tem script)."""
        return bool(self.script)

    @property
    def needs_heygen(self) -> bool:
        """
        True quando o segmento precisa de vídeo HeyGen (avatar falando).
        Apenas segmentos com script E sem slide vão para o HeyGen.
        Segmentos com slide usam o HTML renderizado + áudio TTS direto.
        """
        return bool(self.script) and self.slide is None

    @property
    def is_slide_with_audio(self) -> bool:
        """
        True quando o segmento é slide + áudio (renderizar HTML + colar TTS).
        Não passa pelo HeyGen — o vídeo é o slide animado com áudio.
        """
        return bool(self.script) and self.slide is not None

    @property
    def is_slide_only(self) -> bool:
        """True quando o segmento é só slide (Playwright, sem áudio)."""
        return not self.script and self.slide is not None

    @property
    def is_avatar_segment(self) -> bool:
        """DEPRECATED: use needs_heygen ou needs_tts."""
        return bool(self.script)


# ── Manifest ──────────────────────────────────────────────────────────────────


@dataclass
class Manifest:
    version:  int
    video_id: str
    title:    str
    language: str
    youtube:  dict[str, Any]   # deck + resolution + segments
    reels:    list[dict[str, Any]]

    @classmethod
    def _parse_from_html(cls, html_content: str) -> "Manifest":
        """
        Extrai o JSON do manifesto do elemento <script type="application/json">
        dentro do HTML gerado pelo CMO Agent.

        Raises:
            ValueError: se o script tag não for encontrado ou JSON inválido
        """
        soup = BeautifulSoup(html_content, "lxml")
        script_tag = soup.find("script", {"type": "application/json"})
        if not script_tag:
            raise ValueError(
                "Manifesto inválido: elemento <script type=\"application/json\"> não encontrado."
            )
        raw = script_tag.string
        if not raw:
            raise ValueError("Manifesto inválido: script tag vazio.")
        data: dict[str, Any] = json.loads(raw)
        return cls(
            version=data["version"],
            video_id=data["video_id"],
            title=data["title"],
            language=data["language"],
            youtube=data["youtube"],
            reels=data.get("reels", []),
        )

    def get_avatar_segments(
        self, target: Literal["horizontal", "vertical"]
    ) -> list[Segment]:
        """
        DEPRECATED: use get_tts_segments ou get_heygen_segments.
        Retorna segmentos com script != '' — os que geram áudio TTS.
        """
        segs_raw = self._get_raw_segments(target)
        return [Segment(**s) for s in segs_raw if s.get("script")]

    def get_tts_segments(
        self, target: Literal["horizontal", "vertical"]
    ) -> list[Segment]:
        """Retorna segmentos que precisam de áudio TTS (script != '')."""
        segs_raw = self._get_raw_segments(target)
        return [Segment(**s) for s in segs_raw if s.get("script")]

    def get_heygen_segments(
        self, target: Literal["horizontal", "vertical"]
    ) -> list[Segment]:
        """
        Retorna segmentos que precisam de vídeo HeyGen (avatar falando).
        Apenas segmentos com script E sem slide.
        """
        segs_raw = self._get_raw_segments(target)
        return [
            Segment(**s)
            for s in segs_raw
            if s.get("script") and s.get("slide") is None
        ]

    def get_slide_with_audio_segments(
        self, target: Literal["horizontal", "vertical"]
    ) -> list[Segment]:
        """
        Retorna segmentos que são slide + áudio (renderizar HTML + colar TTS).
        Segmentos com script E com slide.
        """
        segs_raw = self._get_raw_segments(target)
        return [
            Segment(**s)
            for s in segs_raw
            if s.get("script") and s.get("slide") is not None
        ]

    def get_slide_only_segments(
        self, target: Literal["horizontal", "vertical"]
    ) -> list[Segment]:
        """Retorna segmentos com script == '' — renderizados pelo Playwright sem áudio."""
        segs_raw = self._get_raw_segments(target)
        return [
            Segment(**s)
            for s in segs_raw
            if not s.get("script") and s.get("slide") is not None
        ]

    def _get_raw_segments(
        self, target: Literal["horizontal", "vertical"]
    ) -> list[dict[str, Any]]:
        if target == "horizontal":
            return self.youtube.get("segments", [])
        # vertical: primeiro reel com reel_id == "reel-01"
        for reel in self.reels:
            if reel.get("reel_id") == "reel-01":
                return reel.get("segments", [])
        logger.warning("Reel 'reel-01' não encontrado; retornando lista vazia.")
        return []


# ── Pipeline Config ───────────────────────────────────────────────────────────


@dataclass
class PipelineConfig:
    cost_limit:            float = 100.0
    alert_threshold:       float = 80.0
    exchange_rate_usd_brl: float = 5.50
    schedule:              dict[str, Any] = field(default_factory=dict)


# ── Pub/Sub Message Contracts ─────────────────────────────────────────────────


@dataclass
class PackageApprovedMsg:
    """Publicado por CMO Agent → consumido por tts-job."""
    project_id:        str
    manifest_gcs_path: str
    channels_approved: list[str]
    approved_at:       str   # ISO 8601
    cost_limit:        float


@dataclass
class TtsCompletedMsg:
    """
    Publicado por tts-job → consumido por avatar-job.
    
    audio_paths contém TODOS os segmentos com script (TTS gerado).
    heygen_segment_ids indica quais segmentos precisam ir para o HeyGen
    (apenas os que têm script E não têm slide).
    slide_audio_segment_ids indica quais segmentos são slide + áudio
    (vão direto para o video_editor sem passar pelo HeyGen).
    """
    project_id:             str
    audio_paths:            dict[str, list[str]]  # {"horizontal": [...], "vertical": [...]}
    total_cost_usd:         float
    segment_count:          int
    # Novos campos para distinguir tipos de segmento
    heygen_segment_ids:     dict[str, list[str]] = field(default_factory=dict)  # segmentos que vão para HeyGen
    slide_audio_segment_ids: dict[str, list[str]] = field(default_factory=dict)  # segmentos de slide + áudio


@dataclass
class AvatarCompletedMsg:
    """
    Publicado por heygen-callback → consumido por video-editor-job.

    BUG2 fix: cada segmento gera um vídeo HeyGen individual.
    horizontal_video_paths e vertical_video_paths são listas ordenadas
    de GCS paths, na mesma ordem dos segmentos com script != '' no manifesto.
    segment_ids lista os IDs dos segmentos horizontais (ex: yt-01, yt-03...).
    vertical_segment_ids lista os IDs dos segmentos verticais (ex: r1-01, r1-02...).
    """
    project_id:              str
    horizontal_video_paths:  list[str]   # ["gs://.../horizontal_yt-01.mp4", ...]
    vertical_video_paths:    list[str]   # ["gs://.../vertical_r1-01.mp4", ...]
    segment_ids:             list[str]   # ["yt-01", "yt-03", ...]  (horizontais)
    vertical_segment_ids:    list[str]   # ["r1-01", "r1-02", ...]  (verticais)
    duration_seconds:        float
    total_cost_usd:          float


@dataclass
class VideoReadyMsg:
    """Publicado por video-editor-job → consumido por publisher."""
    project_id:       str
    horizontal_final: str
    vertical_final:   str
    duration_seconds: float
    trigger:          Literal["scheduled", "immediate"]
