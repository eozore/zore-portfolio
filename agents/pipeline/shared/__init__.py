"""
agents/pipeline/shared
======================
Módulo compartilhado pelos Cloud Run Jobs da content pipeline éozoré.

Exports públicos:
  - models:          Dataclasses, Enums e contratos de mensagens Pub/Sub
  - retry:           with_retry, ApiError
  - cost_tracker:    CostTrackerService
  - firestore_client: FirestoreClient, ProjectNotFoundError
  - pubsub_client:   PubSubClient, get_secret
"""

from shared.models import (
    ProjectStatus,
    StageStatus,
    StageId,
    ChannelId,
    CostBreakdown,
    PipelineStage,
    LipsyncJob,
    AvatarLipsyncJobs,
    Segment,
    Manifest,
    PipelineConfig,
    PackageApprovedMsg,
    TtsCompletedMsg,
    AvatarCompletedMsg,
    VideoReadyMsg,
)
from shared.retry import with_retry, ApiError
from shared.cost_tracker import CostTrackerService
from shared.firestore_client import FirestoreClient, ProjectNotFoundError
from shared.pubsub_client import PubSubClient, get_secret

__all__ = [
    # models — enums
    "ProjectStatus",
    "StageStatus",
    "StageId",
    "ChannelId",
    # models — dataclasses
    "CostBreakdown",
    "PipelineStage",
    "LipsyncJob",
    "AvatarLipsyncJobs",
    "Segment",
    "Manifest",
    "PipelineConfig",
    # models — Pub/Sub message contracts
    "PackageApprovedMsg",
    "TtsCompletedMsg",
    "AvatarCompletedMsg",
    "VideoReadyMsg",
    # retry
    "with_retry",
    "ApiError",
    # cost tracker
    "CostTrackerService",
    # firestore
    "FirestoreClient",
    "ProjectNotFoundError",
    # pubsub / secrets
    "PubSubClient",
    "get_secret",
]
