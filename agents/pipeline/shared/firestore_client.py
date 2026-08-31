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

    async def enfileirar_curto(
        self, doc: dict, colecao: str = "social_queue",
    ) -> None:
        """Grava uma peça na fila agendada."""
        await self._db.collection(colecao).add(doc)

    async def horarios_ocupados(
        self, colecao: str = "social_queue",
    ) -> set[tuple[str, str]]:
        """
        (plataforma, hora cheia) das peças ainda não publicadas.

        Mesmo critério do agendador do cmo_agent: o conflito que importa é
        duas peças do MESMO canal na mesma hora. A granularidade é a hora
        porque frames de story saem de minuto em minuto e são uma peça só.
        """
        ocupados: set[tuple[str, str]] = set()
        try:
            q = self._db.collection(colecao).where("status", "==", "planned")
            async for d in q.stream():
                data = d.to_dict() or {}
                p = data.get("platform") or ""
                w = data.get("scheduled_at") or data.get("scheduledAt") or ""
                if p and isinstance(w, str) and w:
                    ocupados.add((p, w[:13]))
        except Exception:
            # Falha aberto: sem a leitura o curto pode coincidir com outra
            # peça, o que é bem melhor do que não ser agendado.
            logger.exception("[firestore] não consegui ler a agenda atual")
        return ocupados

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

    # ── Quota mensal por tenant ──────────────────────────────────────────────
    # Doc separado do pipeline_config/{tenant_id} principal (que é reescrito
    # inteiro por configs manuais) — um contador de gasto merece sua própria
    # subcoleção, incrementada atomicamente por múltiplos jobs concorrentes do
    # mesmo tenant sem risco de leitura-e-escrita pisar uma na outra.

    def _monthly_usage_ref(self, tenant_id: str, yyyymm: str):
        return (
            self._db.collection(COLLECTION_PIPELINE_CONFIG)
            .document(tenant_id)
            .collection("usage_monthly")
            .document(yyyymm)
        )

    async def get_tenant_monthly_spend(self, tenant_id: str, yyyymm: str) -> float:
        """Gasto em BRL do tenant no mês (formato yyyymm = 'YYYY-MM')."""
        snap = await self._monthly_usage_ref(tenant_id, yyyymm).get()
        if not snap.exists:
            return 0.0
        return float((snap.to_dict() or {}).get("spent_brl", 0.0))

    async def add_tenant_spend(self, tenant_id: str, yyyymm: str, amount_brl: float) -> None:
        """
        Incrementa o gasto do mês atomicamente via firestore.Increment — não
        um read-modify-write manual, que perderia incrementos quando dois jobs
        do mesmo tenant (ex.: dois segmentos de TTS em paralelo) escrevem ao
        mesmo tempo.
        """
        if amount_brl <= 0:
            return
        await self._monthly_usage_ref(tenant_id, yyyymm).set(
            {"spent_brl": firestore.Increment(amount_brl)}, merge=True
        )
        logger.debug(
            "[Firestore] tenant=%s mês=%s +%.4f BRL", tenant_id, yyyymm, amount_brl
        )

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
