"""
agents/pipeline/avatar_job/job.py
====================================
AvatarJob: gera vídeos de avatar via HeyGen Video Generation API v3.

IMPORTANTE: Este job processa APENAS segmentos que precisam de avatar (sem slide).
Segmentos com slide são processados diretamente no video_editor_job (HTML + áudio TTS).

Fluxo:
  1. Recebe TtsCompletedMsg com heygen_segment_ids (segmentos sem slide)
  2. Para cada segmento em heygen_segment_ids:
     - Download do áudio do GCS
     - Upload para HeyGen Assets API → audio_asset_id
     - POST /v3/videos com character.avatar_id + voice.audio_asset_id
  3. Salva video_ids no Firestore + registra callback_id
  4. TERMINA — HeyGenCallbackHandler recebe o resultado via webhook

Se não houver segmentos HeyGen (todos são slide+áudio), o job:
  - Marca status como "completed"
  - Dispara AvatarCompletedMsg vazio para o video_editor_job
"""

import asyncio
import logging
import os
import time
from typing import Literal

import requests
from google.cloud import storage

from shared.cost_tracker import CostTrackerService
from shared.firestore_client import FirestoreClient
from shared.models import TtsCompletedMsg
from shared.pubsub_client import PubSubClient
from shared.retry import ApiError, with_retry

logger = logging.getLogger(__name__)

HEYGEN_BASE_URL = "https://api.heygen.com"

# Dimensões por target
DIMENSIONS: dict[str, dict] = {
    "horizontal": {"width": 1920, "height": 1080},
    "vertical":   {"width": 1080, "height": 1920},
}


class CostGateBlockedError(Exception):
    pass


class AvatarJob:
    def __init__(
        self,
        firestore: FirestoreClient,
        pubsub: PubSubClient,
        heygen_api_key: str,
        gcs_bucket: str,
        callback_url: str,
        tenant_id: str = "default",
    ) -> None:
        self.firestore    = firestore
        self.pubsub       = pubsub
        self.heygen_key   = heygen_api_key
        self.gcs_bucket   = gcs_bucket
        self.callback_url = callback_url
        self.cost         = CostTrackerService(firestore, tenant_id)
        self.gcs          = storage.Client()

    async def run(self, msg: TtsCompletedMsg) -> None:
        """
        Processa apenas segmentos que precisam de HeyGen (avatar falando).
        Segmentos com slide são processados diretamente no video_editor_job.
        """
        project_id = msg.project_id

        # Idempotência
        project = await self.firestore.get_project(project_id)
        avatar_status = project["stages"]["avatar"]["status"]
        if avatar_status in ("completed", "pending_callback"):
            logger.info(
                "[AvatarJob] Avatar já em status '%s' para %s. Ignorando.",
                avatar_status, project_id,
            )
            return

        await self.firestore.update_stage(project_id, "avatar", {
            "status": "running",
            "started_at": int(time.time()),
        })

        try:
            # Filtra apenas segmentos que precisam de HeyGen (sem slide)
            heygen_segment_ids = getattr(msg, 'heygen_segment_ids', {}) or {}
            slide_audio_segment_ids = getattr(msg, 'slide_audio_segment_ids', {}) or {}
            
            # Conta apenas segmentos HeyGen para cost gate
            heygen_segment_count = sum(len(ids) for ids in heygen_segment_ids.values())
            
            if heygen_segment_count == 0:
                # Não há segmentos de avatar — pular HeyGen, ir direto para video_editor
                logger.info(
                    "[AvatarJob] Nenhum segmento precisa de HeyGen para %s. "
                    "Todos os %d segmentos são slide+áudio.",
                    project_id,
                    sum(len(ids) for ids in slide_audio_segment_ids.values()),
                )
                await self.firestore.update_stage(project_id, "avatar", {
                    "status": "completed",
                    "completed_at": int(time.time()),
                    "skipped_reason": "no_heygen_segments",
                    "slide_audio_paths": msg.audio_paths,  # salva para o video_editor
                    "slide_audio_segment_ids": slide_audio_segment_ids,
                })
                # Dispara video_editor diretamente via Pub/Sub
                from shared.models import AvatarCompletedMsg
                completed_msg = AvatarCompletedMsg(
                    project_id=project_id,
                    horizontal_video_paths=[],  # sem vídeos HeyGen
                    vertical_video_paths=[],
                    segment_ids=[],
                    vertical_segment_ids=[],
                    duration_seconds=0.0,
                    total_cost_usd=0.0,
                )
                AVATAR_COMPLETED_TOPIC = "content-pipeline.avatar-completed"
                self.pubsub.publish(AVATAR_COMPLETED_TOPIC, completed_msg)
                return

            # Cost gate — estima apenas pelos segmentos HeyGen
            total_duration_s = heygen_segment_count * 5.0  # estimativa conservadora
            estimated_cost   = await self.cost.estimate_heygen_cost(total_duration_s)
            config           = await self.firestore.get_pipeline_config("default")
            can_proceed      = await self.cost.check_cost_gate(
                project_id, estimated_cost, config.get("cost_limit", 100.0)
            )
            if not can_proceed:
                raise CostGateBlockedError(
                    f"Custo HeyGen bloqueado: estimado={estimated_cost:.2f} BRL"
                )

            # Avatar IDs de cada formato
            avatar_h_id = os.environ.get("HEYGEN_AVATAR_ID_HORIZONTAL", "32e2ad6b3e5a45bf8c61cbf7220912f4")
            avatar_v_id = os.environ.get("HEYGEN_AVATAR_ID_VERTICAL",   "d7fdce2942a244649820a0b5c989766f")
            avatar_ids  = {"horizontal": avatar_h_id, "vertical": avatar_v_id}

            # Salva slide_audio info no Firestore para o video_editor
            await self.firestore.update_stage(project_id, "avatar", {
                "slide_audio_paths": msg.audio_paths,
                "slide_audio_segment_ids": slide_audio_segment_ids,
            })

            # Processa cada segmento HeyGen individualmente
            for target in ("horizontal", "vertical"):
                heygen_ids_for_target = heygen_segment_ids.get(target, [])
                all_audio_paths = msg.audio_paths.get(target, [])
                
                if not heygen_ids_for_target:
                    logger.info("[AvatarJob] Sem segmentos HeyGen para target=%s, pulando.", target)
                    continue

                segment_videos: list[dict] = []

                # Mapeia seg_id → audio_path
                # O TTS gera áudios na ordem dos segmentos do manifesto
                # Precisamos filtrar apenas os que são HeyGen
                audio_path_map: dict[str, str] = {}
                for path in all_audio_paths:
                    seg_id = os.path.splitext(os.path.basename(path))[0]
                    audio_path_map[seg_id] = path

                for idx, seg_id in enumerate(heygen_ids_for_target):
                    seg_path = audio_path_map.get(seg_id)
                    if not seg_path:
                        logger.warning(
                            "[AvatarJob] Áudio não encontrado para seg_id=%s, pulando.", seg_id
                        )
                        continue

                    logger.info(
                        "[AvatarJob] Processando segmento HeyGen %d/%d: %s (target=%s)",
                        idx + 1, len(heygen_ids_for_target), seg_id, target,
                    )

                    try:
                        # 1. Baixar segmento do GCS para /tmp
                        local_audio = await self._download_segment_from_gcs(seg_path)

                        # 2. Upload individual por segmento para HeyGen Assets
                        audio_asset_id = await with_retry(
                            lambda p=local_audio: self._upload_to_heygen_assets(p),
                            max_retries=3, backoff=[1.0, 4.0, 16.0],
                            transient_errors=(429, 503),
                            project_id=project_id, stage_id="avatar",
                            firestore=self.firestore,
                        )
                        # Limpa arquivo local após upload
                        try:
                            os.remove(local_audio)
                        except OSError:
                            pass

                        logger.info(
                            "[AvatarJob] Upload OK: seg=%s asset_id=%s", seg_id, audio_asset_id
                        )

                        # 3. Gerar vídeo individual para este segmento
                        video_id = await with_retry(
                            lambda aid=audio_asset_id, av=avatar_ids[target], t=target, sid=seg_id: \
                                self._generate_avatar_video(aid, av, t, project_id, sid),
                            max_retries=3, backoff=[1.0, 4.0, 16.0],
                            transient_errors=(429, 503),
                            project_id=project_id, stage_id="avatar",
                            firestore=self.firestore,
                        )
                        logger.info(
                            "[AvatarJob] Vídeo criado: seg=%s video_id=%s", seg_id, video_id
                        )

                        segment_videos.append({
                            "seg_id":   seg_id,
                            "video_id": video_id,
                            "status":   "pending",
                            "video_url": None,
                        })

                    except Exception as seg_err:
                        logger.error(
                            "[AvatarJob] Falha no segmento %s: %s", seg_id, seg_err
                        )
                        segment_videos.append({
                            "seg_id":   seg_id,
                            "video_id": None,
                            "status":   "failed",
                            "video_url": None,
                            "error":    str(seg_err),
                        })

                    # Delay entre chamadas HeyGen para evitar rate limit
                    if idx < len(heygen_ids_for_target) - 1:
                        await asyncio.sleep(0.5)

                # Salva lista de segment_videos no Firestore por target
                await self.firestore.update_stage(project_id, "avatar", {
                    f"segment_videos.{target}": segment_videos,
                })
                logger.info(
                    "[AvatarJob] %d segmentos HeyGen enfileirados para %s (target=%s).",
                    len([s for s in segment_videos if s["status"] != "failed"]),
                    project_id, target,
                )

            await self.firestore.update_stage(project_id, "avatar", {
                "status": "pending_callback",
                "cost_estimated": estimated_cost,
            })
            logger.info(
                "[AvatarJob] Todos os segmentos HeyGen iniciados para %s. Aguardando callbacks.",
                project_id,
            )

        except CostGateBlockedError as exc:
            await self.firestore.update_stage(project_id, "avatar", {
                "status": "error",
                "error_message": str(exc),
                "error_type": "permanent",
            })
            raise
        except Exception as exc:
            await self.firestore.update_stage(project_id, "avatar", {
                "status": "error",
                "error_message": str(exc),
                "error_type": "transient",
            })
            raise

    async def _download_segment_from_gcs(self, gcs_uri: str) -> str:
        """Baixa um segmento de áudio do GCS para /tmp e retorna o path local."""
        bucket_name, blob_path = gcs_uri.replace("gs://", "").split("/", 1)
        filename    = os.path.basename(blob_path)
        local_path  = f"/tmp/{filename}"
        loop        = asyncio.get_event_loop()

        bucket = self.gcs.bucket(bucket_name)
        blob   = bucket.blob(blob_path)
        audio_bytes = await loop.run_in_executor(None, blob.download_as_bytes)

        with open(local_path, "wb") as f:
            f.write(audio_bytes)

        logger.debug("[AvatarJob] Download GCS: %s → %s (%d bytes)", gcs_uri, local_path, len(audio_bytes))
        return local_path

    async def _upload_to_heygen_assets(self, local_path: str) -> str:
        """POST /v3/assets (multipart/form-data) → retorna asset_id."""
        url  = f"{HEYGEN_BASE_URL}/v3/assets"
        H    = {"X-Api-Key": self.heygen_key}
        loop = asyncio.get_event_loop()

        def _upload() -> str:
            with open(local_path, "rb") as f:
                resp = requests.post(
                    url,
                    headers=H,
                    files={"file": (os.path.basename(local_path), f, "audio/mpeg")},
                    timeout=120,
                )
            if resp.status_code not in (200, 201):
                raise ApiError(resp.status_code, resp.text[:200])
            return resp.json()["data"]["asset_id"]

        return await loop.run_in_executor(None, _upload)

    async def _generate_avatar_video(
        self,
        audio_asset_id: str,
        avatar_id: str,
        target: Literal["horizontal", "vertical"],
        project_id: str,
        seg_id: str = "",
    ) -> str:
        """
        POST /v3/videos com voice.type="audio" + audio_asset_id.

        BUG2 fix: callback_id agora é "{project_id}__{target}__{seg_id}" para
        permitir ao heygen_callback resolver o segmento exato via Firestore.

        O callback é recebido via webhook no HeyGenCallbackHandler.
        """
        url  = f"{HEYGEN_BASE_URL}/v2/video/generate"
        H    = {"X-Api-Key": self.heygen_key, "Content-Type": "application/json"}
        dim  = DIMENSIONS[target]
        loop = asyncio.get_event_loop()

        # callback_id com seg_id para resolução granular no webhook
        callback_id = f"{project_id}__{target}__{seg_id}" if seg_id else f"{project_id}__{target}"

        payload = {
            "video_inputs": [{
                "character": {
                    "type": "avatar",
                    "avatar_id": avatar_id,
                    "avatar_style": "normal",
                },
                "voice": {
                    "type": "audio",
                    "audio_asset_id": audio_asset_id,
                },
            }],
            "dimension": dim,
            "caption": False,
            "callback_url": f"{self.callback_url}/heygen-video-callback",
            "callback_id": callback_id,
        }

        def _generate() -> str:
            resp = requests.post(url, headers=H, json=payload, timeout=60)
            if resp.status_code != 200:
                # Fallback para v3 se v2 falhar
                resp_v3 = requests.post(
                    f"{HEYGEN_BASE_URL}/v3/videos",
                    headers=H, json=payload, timeout=60,
                )
                if resp_v3.status_code not in (200, 201, 202):
                    raise ApiError(resp_v3.status_code, resp_v3.text[:300])
                data = resp_v3.json().get("data", resp_v3.json())
                return data.get("video_id") or data.get("id")
            return resp.json()["data"]["video_id"]

        return await loop.run_in_executor(None, _generate)
