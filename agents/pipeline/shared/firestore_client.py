"""
agents/pipeline/shared/firestore_client.py
===========================================
Wrapper do Firebase Admin SDK para operações da content pipeline.

Usa Application Default Credentials (ADC) — sem chaves explícitas no código.
Cloud Run usa automaticamente a service account do Job (pipeline-jobs-sa).
Todas as operações são async (AsyncClient).
"""

import logging
from typing import Any

from google.cloud import firestore
from google.cloud.firestore_v1 import AsyncClient

logger = logging.getLogger(__name__)

# Coleções Firestore
COLLECTION_CONTENT_PROJECTS: str = "content_projects"
COLLECTION_PIPELINE_CONFIG: str  = "pipeline_config"


class ProjectNotFoundError(Exception):
    """Raised quando um documento content_projects/{project_id} não existe."""
    pass


class FirestoreClient:
    """
    Wrapper do Firebase Admin SDK para operações da pipeline.

    Usa Application Default Credentials (ADC) — sem chaves explícitas no código.
    Todas as operações são async (AsyncClient).
    """

    def __init__(self, project_id: str) -> None:
        self._db: AsyncClient = firestore.AsyncClient(project=project_id)

    async def get_project(self, project_id: str) -> dict[str, Any]:
        """
        Lê documento content_projects/{project_id}.

        Returns:
            Dict com todos os campos do documento

        Raises:
            ProjectNotFoundError: se documento não existe
        """
        ref = self._db.collection(COLLECTION_CONTENT_PROJECTS).document(project_id)
        snap = await ref.get()
        if not snap.exists:
            raise ProjectNotFoundError(f"Projeto não encontrado: {project_id}")
        return snap.to_dict()  # type: ignore[return-value]

    async def update_project(
        self, project_id: str, updates: dict[str, Any]
    ) -> None:
        """
        Atualiza campos do documento content_projects/{project_id}.

        Usa merge=True (não sobrescreve campos não listados).
        """
        ref = self._db.collection(COLLECTION_CONTENT_PROJECTS).document(project_id)
        await ref.set(updates, merge=True)
        logger.debug(
            "[Firestore] update_project project=%s fields=%s",
            project_id,
            list(updates.keys()),
        )

    async def update_stage(
        self,
        project_id: str,
        stage_id: str,
        updates: dict[str, Any],
    ) -> None:
        """
        Atualiza campos de stages.{stage_id} no documento do projeto.

        Expande automaticamente para dot-notation do Firestore:
          update_stage(id, "tts", {"status": "running"})
          → {"stages.tts.status": "running"}
        """
        dot_updates = {f"stages.{stage_id}.{k}": v for k, v in updates.items()}
        ref = self._db.collection(COLLECTION_CONTENT_PROJECTS).document(project_id)
        await ref.update(dot_updates)
        logger.debug(
            "[Firestore] update_stage project=%s stage=%s fields=%s",
            project_id,
            stage_id,
            list(updates.keys()),
        )

    async def get_pipeline_config(self, tenant_id: str) -> dict[str, Any]:
        """
        Lê pipeline_config/{tenant_id}.

        Returns:
            Dict com cost_limit, exchange_rate_usd_brl, schedule, etc.
            Retorna defaults se documento não existe.
        """
        ref = self._db.collection(COLLECTION_PIPELINE_CONFIG).document(tenant_id)
        snap = await ref.get()
        if not snap.exists:
            logger.warning(
                "[Firestore] pipeline_config/%s não encontrado; usando defaults.",
                tenant_id,
            )
            return {
                "cost_limit": 100.0,
                "alert_threshold": 80.0,
                "exchange_rate_usd_brl": 5.50,
                "schedule": {},
            }
        return snap.to_dict()  # type: ignore[return-value]

    async def resolve_lipsync_to_project(
        self, lipsync_id: str
    ) -> tuple[str, str] | None:
        """
        Resolve lipsync_id → (project_id, orientation) via collection_group query.

        Query: db.collection_group("lipsync_jobs").where("lipsync_id", "==", lipsync_id).limit(1)

        Requer índice collection_group em firestore.indexes.json
        (fieldOverrides.lipsync_jobs.lipsync_id).

        Returns:
            Tuple (project_id, orientation) onde orientation = "horizontal" | "vertical"
            None se não encontrado
        """
        query = (
            self._db.collection_group("lipsync_jobs")
            .where("lipsync_id", "==", lipsync_id)
            .limit(1)
        )
        docs = await query.get()
        if not docs:
            logger.warning(
                "[Firestore] resolve_lipsync: lipsync_id=%s não encontrado.", lipsync_id
            )
            return None

        doc = docs[0]
        # Path: content_projects/{project_id}/stages/avatar/lipsync_jobs/{orientation}
        path_parts = doc.reference.path.split("/")
        project_id = path_parts[1]
        orientation = path_parts[-1]  # "horizontal" | "vertical"
        logger.debug(
            "[Firestore] resolve_lipsync: lipsync_id=%s → project=%s orientation=%s",
            lipsync_id,
            project_id,
            orientation,
        )
        return project_id, orientation
