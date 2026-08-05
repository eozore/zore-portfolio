# -*- coding: utf-8 -*-
"""
lifecycle_job/job.py — Sprint 4 / G6
======================================
Cloud Run Job que arquiva assets de projetos publicados há mais de
LIFECYCLE_RETENTION_DAYS dias (padrão: 60).

Fluxo por projeto expirado:
  1. Lista todos os blobs GCS em projects/{project_id}/
  2. Compacta em <project_id>.tar.gz no bucket de archive (Nearline/Coldline)
  3. Remove os blobs do bucket quente (media)
  4. Atualiza status no Firestore: 'archived', archived_at = now
  5. Idem para itens de social_queue vinculados ao projeto

Sem LLM. Sem Pub/Sub. Job síncrono executado pelo Cloud Scheduler diariamente.
"""

from __future__ import annotations

import io
import logging
import os
import tarfile
import tempfile
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger("lifecycle_job.job")

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "vazfy-417019")


class LifecycleJob:
    def __init__(
        self,
        media_bucket:   str,
        archive_bucket: str,
        retention_days: int = 60,
        dry_run:        bool = False,
    ) -> None:
        self.media_bucket   = media_bucket
        self.archive_bucket = archive_bucket
        self.retention_days = retention_days
        self.dry_run        = dry_run

        from google.cloud import storage as gcs_storage
        self._gcs = gcs_storage.Client()

        from google.cloud import firestore
        self._db = firestore.Client(project=GCP_PROJECT_ID)

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self) -> dict:
        """
        Executa o ciclo completo de archival.

        Returns:
            dict com total_expired, archived, skipped, failed, dry_run
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
        logger.info(
            "Scanning content_projects published before %s (dry_run=%s)...",
            cutoff.isoformat(), self.dry_run,
        )

        expired_projects = self._query_expired_projects(cutoff)
        logger.info("Found %d expired project(s).", len(expired_projects))

        results = {"total_expired": len(expired_projects), "archived": 0, "skipped": 0, "failed": 0, "dry_run": self.dry_run}

        for project in expired_projects:
            project_id = project.get("project_id") or project.get("id", "")
            if not project_id:
                logger.warning("Project without project_id, skipping: %s", project)
                results["skipped"] += 1
                continue

            try:
                self._archive_project(project_id, project)
                results["archived"] += 1
                logger.info("Archived: %s", project_id)
            except Exception as exc:
                logger.exception("Failed to archive %s: %s", project_id, exc)
                results["failed"] += 1

        # Also process social_queue items older than retention_days
        expired_queue = self._query_expired_social_queue(cutoff)
        logger.info("Found %d expired social_queue item(s).", len(expired_queue))
        for item in expired_queue:
            try:
                self._archive_social_item(item)
                results["archived"] += 1
            except Exception as exc:
                logger.exception("Failed to archive social item %s: %s", item.get("id"), exc)
                results["failed"] += 1

        return results

    # ── Firestore queries ─────────────────────────────────────────────────────

    def _query_expired_projects(self, cutoff: datetime) -> list[dict]:
        """Retorna projetos com published_at < cutoff e status != 'archived'."""
        try:
            docs = (
                self._db.collection("content_projects")
                .where("status", "not-in", ["archived", "generating_media"])
                .limit(200)
                .get()
            )
            expired = []
            for doc in docs:
                data = doc.to_dict()
                data["id"] = doc.id
                published_at = data.get("published_at")
                if published_at and self._is_expired(published_at, cutoff):
                    expired.append(data)
            return expired
        except Exception as exc:
            logger.error("Failed to query content_projects: %s", exc)
            return []

    def _query_expired_social_queue(self, cutoff: datetime) -> list[dict]:
        """Retorna itens de social_queue com published_at < cutoff."""
        try:
            docs = (
                self._db.collection("social_queue")
                .where("status", "==", "published")
                .limit(500)
                .get()
            )
            expired = []
            for doc in docs:
                data = doc.to_dict()
                data["id"] = doc.id
                published_at = data.get("published_at")
                if published_at and self._is_expired(published_at, cutoff):
                    # Inclui apenas se tiver asset_urls para arquivar
                    if data.get("asset_urls") or data.get("image_url"):
                        expired.append(data)
            return expired
        except Exception as exc:
            logger.error("Failed to query social_queue: %s", exc)
            return []

    @staticmethod
    def _is_expired(published_at: object, cutoff: datetime) -> bool:
        """Converte published_at (ISO string ou datetime) e compara com cutoff."""
        try:
            if isinstance(published_at, datetime):
                dt = published_at if published_at.tzinfo else published_at.replace(tzinfo=timezone.utc)
            else:
                s = str(published_at).rstrip("Z")
                dt = datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
            return dt < cutoff
        except Exception:
            return False

    # ── Archival logic ────────────────────────────────────────────────────────

    def _archive_project(self, project_id: str, project_data: dict) -> None:
        """
        Arquiva todos os assets de um projeto:
          1. Lista blobs em projects/{project_id}/
          2. Cria .tar.gz no bucket archive
          3. Remove do bucket quente
          4. Atualiza Firestore
        """
        prefix  = f"projects/{project_id}/"
        archive_blob_name = f"archive/{project_id}.tar.gz"

        media_bkt   = self._gcs.bucket(self.media_bucket)
        archive_bkt = self._gcs.bucket(self.archive_bucket)

        blobs = list(media_bkt.list_blobs(prefix=prefix))
        if not blobs:
            logger.info("No GCS assets found for %s — marking archived anyway.", project_id)
            if not self.dry_run:
                self._mark_archived(
                    collection="content_projects",
                    doc_id=project_id,
                    archive_path=f"gs://{self.archive_bucket}/{archive_blob_name}",
                )
            return

        logger.info("Archiving %d blob(s) for project %s...", len(blobs), project_id)

        if self.dry_run:
            for b in blobs:
                logger.info("[DRY RUN] Would archive: gs://%s/%s", self.media_bucket, b.name)
            return

        # Compacta em .tar.gz na memória
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
            for blob in blobs:
                data = blob.download_as_bytes()
                info = tarfile.TarInfo(name=blob.name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))

        tar_buffer.seek(0)
        archive_blob = archive_bkt.blob(archive_blob_name)
        archive_blob.upload_from_file(
            tar_buffer,
            content_type="application/gzip",
        )
        archive_blob.update_storage_class("NEARLINE")
        logger.info("Uploaded archive: gs://%s/%s", self.archive_bucket, archive_blob_name)

        # Remove blobs do bucket quente
        for blob in blobs:
            blob.delete()
            logger.debug("Deleted: gs://%s/%s", self.media_bucket, blob.name)

        # Atualiza Firestore
        self._mark_archived(
            collection="content_projects",
            doc_id=project_id,
            archive_path=f"gs://{self.archive_bucket}/{archive_blob_name}",
        )

    def _archive_social_item(self, item: dict) -> None:
        """Remove imagens de posts sociais publicados e marca como archived."""
        doc_id = item.get("id", "")
        if not doc_id:
            return

        asset_urls: list[str] = list(filter(None, [
            *(item.get("asset_urls") or []),
            item.get("image_url"),
        ]))

        if self.dry_run:
            logger.info("[DRY RUN] Would archive social item %s (%d assets)", doc_id, len(asset_urls))
            return

        # Para assets GCS (gs:// URIs), deleta do bucket quente
        for url in asset_urls:
            if url.startswith(f"gs://{self.media_bucket}/"):
                blob_name = url.replace(f"gs://{self.media_bucket}/", "")
                try:
                    self._gcs.bucket(self.media_bucket).blob(blob_name).delete()
                    logger.debug("Deleted social asset: %s", url)
                except Exception as exc:
                    logger.warning("Could not delete social asset %s: %s", url, exc)

        self._mark_archived(collection="social_queue", doc_id=doc_id)

    def _mark_archived(
        self,
        collection: str,
        doc_id:     str,
        archive_path: Optional[str] = None,
    ) -> None:
        """Atualiza status no Firestore para 'archived'."""
        now = datetime.now(timezone.utc).isoformat()
        update: dict = {"status": "archived", "archived_at": now}
        if archive_path:
            update["archive_path"] = archive_path

        self._db.collection(collection).document(doc_id).update(update)
        logger.debug("Marked %s/%s as archived.", collection, doc_id)
