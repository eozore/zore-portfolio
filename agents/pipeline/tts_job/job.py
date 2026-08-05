"""
agents/pipeline/tts_job/job.py
================================
TTSJob: processa Text-to-Speech via ElevenLabs Flash v2.5 para cada segmento
de áudio do manifesto.

Regra crítica:
  Segmentos com script == "" (slide puro) são completamente ignorados.
  Apenas segmentos com script != "" geram MP3 e custam créditos ElevenLabs.
"""

import asyncio
import logging
import re
import time
from typing import Literal

import requests
from google.cloud import storage

from shared.cost_tracker import CostTrackerService
from shared.firestore_client import FirestoreClient
from shared.models import Manifest, PackageApprovedMsg, Segment, TtsCompletedMsg
from shared.pubsub_client import PubSubClient
from shared.retry import ApiError, with_retry

logger = logging.getLogger(__name__)

ELEVENLABS_BASE_URL = "https://api.elevenlabs.io"
TTS_COMPLETED_TOPIC = "content-pipeline.tts-completed"


class ManifestParseError(Exception):
    pass


class CostLimitExceededError(Exception):
    pass


def _parse_manifest(html_content: str) -> Manifest:
    """Parseia manifesto HTML para dataclass Manifest via BeautifulSoup."""
    return Manifest._parse_from_html(html_content)


class TTSJob:
    def __init__(
        self,
        firestore: FirestoreClient,
        pubsub: PubSubClient,
        elevenlabs_api_key: str,
        voice_id: str,
        gcs_bucket: str,
        tenant_id: str = "default",
    ) -> None:
        self.firestore  = firestore
        self.pubsub     = pubsub
        self.api_key    = elevenlabs_api_key
        self.voice_id   = voice_id
        self.gcs_bucket = gcs_bucket
        self.cost       = CostTrackerService(firestore, tenant_id)
        self.gcs        = storage.Client()

    async def run(self, msg: PackageApprovedMsg) -> None:
        """Entry point principal do Job."""
        project_id = msg.project_id

        # Idempotência
        project = await self.firestore.get_project(project_id)
        if project["stages"]["tts"]["status"] == "completed":
            logger.info("[TTSJob] TTS já concluído para %s. Ignorando.", project_id)
            return

        await self.firestore.update_stage(project_id, "tts", {
            "status": "running",
            "started_at": int(time.time()),
        })

        try:
            manifest = await self._load_manifest(msg.manifest_gcs_path)
            audio_paths, heygen_segment_ids, slide_audio_segment_ids = await self._process_all_targets(
                project_id, manifest, msg.cost_limit
            )

            segment_count = sum(len(p) for p in audio_paths.values())
            total_cost_usd = self._calculate_total_cost_usd(manifest)

            await self.firestore.update_stage(project_id, "tts", {
                "status": "completed",
                "completed_at": int(time.time()),
                "cost_real": total_cost_usd,
            })

            completed_msg = TtsCompletedMsg(
                project_id=project_id,
                audio_paths=audio_paths,
                total_cost_usd=total_cost_usd,
                segment_count=segment_count,
                heygen_segment_ids=heygen_segment_ids,
                slide_audio_segment_ids=slide_audio_segment_ids,
            )
            self.pubsub.publish(TTS_COMPLETED_TOPIC, completed_msg)
            logger.info(
                "[TTSJob] Concluído: %d segmentos (HeyGen: %d, SlideAudio: %d) project=%s",
                segment_count,
                sum(len(ids) for ids in heygen_segment_ids.values()),
                sum(len(ids) for ids in slide_audio_segment_ids.values()),
                project_id,
            )

        except CostLimitExceededError as exc:
            await self.firestore.update_stage(project_id, "tts", {
                "status": "error",
                "error_message": str(exc),
                "error_type": "permanent",
            })
            raise
        except Exception as exc:
            error_type = "permanent" if isinstance(exc, ApiError) and exc.status_code in (401, 403) else "transient"
            await self.firestore.update_stage(project_id, "tts", {
                "status": "error",
                "error_message": str(exc),
                "error_type": error_type,
            })
            raise

    async def _load_manifest(self, gcs_path: str) -> Manifest:
        """Lê manifesto HTML do GCS e parseia."""
        bucket_name, blob_path = gcs_path.replace("gs://", "").split("/", 1)
        bucket = self.gcs.bucket(bucket_name)
        blob   = bucket.blob(blob_path)
        loop = asyncio.get_event_loop()
        content = await loop.run_in_executor(None, blob.download_as_text)
        return _parse_manifest(content)

    async def _process_all_targets(
        self,
        project_id: str,
        manifest: Manifest,
        cost_limit: float,
    ) -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str, list[str]]]:
        """
        Processa TTS para horizontal e vertical.
        Gera áudio para TODOS os segmentos com script (get_tts_segments).
        
        Retorna:
            - audio_paths: todos os áudios gerados por target
            - heygen_segment_ids: IDs dos segmentos que vão para HeyGen (sem slide)
            - slide_audio_segment_ids: IDs dos segmentos de slide + áudio
        """
        audio_paths: dict[str, list[str]] = {"horizontal": [], "vertical": []}
        heygen_segment_ids: dict[str, list[str]] = {"horizontal": [], "vertical": []}
        slide_audio_segment_ids: dict[str, list[str]] = {"horizontal": [], "vertical": []}

        for target in ("horizontal", "vertical"):
            # Usa get_tts_segments para pegar TODOS os segmentos com script
            segments = manifest.get_tts_segments(target)
            logger.info(
                "[TTSJob] target=%s: %d segmentos de áudio (todos com script)",
                target, len(segments),
            )
            for segment in segments:
                gcs_path = await self._process_segment(
                    project_id, segment, target, cost_limit
                )
                audio_paths[target].append(gcs_path)
                
                # Classifica o segmento
                if segment.needs_heygen:
                    # Segmento sem slide → vai para HeyGen (avatar)
                    heygen_segment_ids[target].append(segment.id)
                elif segment.is_slide_with_audio:
                    # Segmento com slide → vai direto para video_editor
                    slide_audio_segment_ids[target].append(segment.id)

        return audio_paths, heygen_segment_ids, slide_audio_segment_ids

    async def _process_segment(
        self,
        project_id: str,
        segment: Segment,
        target: Literal["horizontal", "vertical"],
        cost_limit: float,
    ) -> str:
        """Cost gate → TTS → GCS upload para um segmento."""
        config = await self.firestore.get_pipeline_config("default")
        limit = cost_limit or config.get("cost_limit", 100.0)
        estimated = await self.cost.estimate_tts_cost(len(segment.script))
        can_proceed = await self.cost.check_cost_gate(project_id, estimated, limit)
        if not can_proceed:
            raise CostLimitExceededError(
                f"Custo excede teto para segment={segment.id} project={project_id}"
            )

        audio_bytes = await with_retry(
            lambda: self._call_elevenlabs(segment.script),
            max_retries=3,
            backoff=[1.0, 4.0, 16.0],
            transient_errors=(429, 503),
            project_id=project_id,
            stage_id="tts",
            firestore=self.firestore,
        )

        gcs_path = f"gs://{self.gcs_bucket}/projects/{project_id}/audio/{target}/{segment.id}.mp3"
        await self._upload_to_gcs(audio_bytes, gcs_path)

        cost_usd = len(segment.script) * 0.00005
        await self.cost.update_actual_cost(project_id, "tts", cost_usd)

        return gcs_path

    async def _call_elevenlabs(self, text: str) -> bytes:
        """POST /v1/text-to-speech/{voice_id} com eleven_flash_v2_5."""
        url = f"{ELEVENLABS_BASE_URL}/v1/text-to-speech/{self.voice_id}"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": "eleven_flash_v2_5",
            "output_format": "mp3_44100_128",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(url, json=payload, headers=headers, timeout=60),
        )
        if response.status_code != 200:
            raise ApiError(response.status_code, response.text[:200])
        return response.content

    async def _upload_to_gcs(self, audio_bytes: bytes, gcs_uri: str) -> None:
        """Upload bytes MP3 para GCS."""
        bucket_name, blob_path = gcs_uri.replace("gs://", "").split("/", 1)
        bucket = self.gcs.bucket(bucket_name)
        blob   = bucket.blob(blob_path)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: blob.upload_from_string(audio_bytes, content_type="audio/mpeg"),
        )
        logger.debug("[TTSJob] Uploaded: %s", gcs_uri)

    def _calculate_total_cost_usd(self, manifest: Manifest) -> float:
        """Calcula custo total de todos os segmentos com script (TTS)."""
        total_chars = 0
        for target in ("horizontal", "vertical"):
            for seg in manifest.get_tts_segments(target):
                total_chars += len(seg.script)
        return round(total_chars * 0.00005, 6)
