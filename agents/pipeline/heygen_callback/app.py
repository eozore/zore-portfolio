"""
agents/pipeline/heygen_callback/app.py
==========================================
HeyGen Callback Handler — Cloud Run Service (FastAPI).

Recebe dois tipos de webhook HeyGen:
  POST /heygen-callback       — callback do Lipsync API (legado, mantido por compatibilidade)
  POST /heygen-video-callback — callback do Video Generation API v2/v3 (novo fluxo sem delay)

Lógica crítica (ambos os endpoints):
  - Só publica avatar_completed no Pub/Sub quando AMBOS horizontal E vertical completam.
  - Falha de qualquer um → stages.avatar.status = "error" imediatamente.
  - Sempre retorna HTTP 200 para evitar retry automático do HeyGen.
  - O callback_id no Video Generation é "{project_id}__{orientation}" — usado para resolver sem Firestore query.
"""

import asyncio
import logging
import os
import time
from typing import Optional

import httpx
from fastapi import FastAPI, Header, HTTPException
from google.cloud import storage
from pydantic import BaseModel

from shared.firestore_client import FirestoreClient
from shared.models import AvatarCompletedMsg
from shared.pubsub_client import PubSubClient, get_secret

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="HeyGen Callback Handler")

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "vazfy-417019")
GCS_BUCKET     = os.environ.get("GCS_BUCKET", "vazfy-417019-pipeline-media")
TENANT_ID      = os.environ.get("TENANT_ID", "default")

AVATAR_COMPLETED_TOPIC = "content-pipeline.avatar-completed"

_firestore: Optional[FirestoreClient] = None
_pubsub: Optional[PubSubClient]       = None
_gcs: Optional[storage.Client]        = None
_callback_token: Optional[str]        = None


class HeyGenVideoCallbackPayload(BaseModel):
    """Payload do webhook do Video Generation API (callback_id = project_id__orientation)."""
    event_type: Optional[str] = None   # "avatar_video.success" | "avatar_video.fail"
    video_id:   Optional[str] = None
    callback_id: Optional[str] = None  # "{project_id}__{orientation}"
    video_url:  Optional[str] = None
    error:      Optional[str] = None
    status:     Optional[str] = None   # "completed" | "failed"


class HeyGenLipsyncCallbackPayload(BaseModel):
    """Payload do webhook do Lipsync API (legado)."""
    lipsync_id: Optional[str] = None
    status:     Optional[str] = None
    video_url:  Optional[str] = None
    error:      Optional[str] = None


class CallbackResponse(BaseModel):
    ok: bool
    message: Optional[str] = None


@app.on_event("startup")
async def startup() -> None:
    global _firestore, _pubsub, _gcs, _callback_token
    _firestore = FirestoreClient(GCP_PROJECT_ID)
    _pubsub    = PubSubClient(GCP_PROJECT_ID)
    _gcs       = storage.Client()
    try:
        _callback_token = get_secret("heygen-callback-token", GCP_PROJECT_ID)
    except Exception:
        logger.warning("[HeyGenCallback] Token não encontrado — autenticação desabilitada em dev.")
        _callback_token = None
    logger.info("[HeyGenCallback] Serviço iniciado. project=%s", GCP_PROJECT_ID)


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}


@app.post("/heygen-video-callback", response_model=CallbackResponse)
async def heygen_video_callback(
    payload: HeyGenVideoCallbackPayload,
    x_heygen_token: Optional[str] = Header(default=None, alias="X-HeyGen-Token"),
) -> CallbackResponse:
    """
    Callback do Video Generation API v2/v3.

    BUG2 fix: callback_id agora é "{project_id}__{target}__{seg_id}".
    Cada segmento individual chega aqui separadamente.
    Quando TODOS os segmentos de AMBOS os targets completarem → publica avatar_completed.
    """
    if _callback_token and x_heygen_token != _callback_token:
        raise HTTPException(status_code=401, detail="Token inválido")

    status = payload.status or (
        "completed" if payload.event_type == "avatar_video.success"
        else "failed" if payload.event_type == "avatar_video.fail"
        else "unknown"
    )

    callback_id = payload.callback_id or ""
    video_url   = payload.video_url
    video_id    = payload.video_id

    logger.info(
        "[HeyGenCallback] Video callback: callback_id=%s status=%s video_id=%s",
        callback_id, status, video_id,
    )

    # BUG2 fix: callback_id formato "{project_id}__{target}__{seg_id}"
    parts = callback_id.split("__")
    if len(parts) < 2:
        logger.warning("[HeyGenCallback] callback_id sem formato esperado: %s", callback_id)
        return CallbackResponse(ok=False, message="callback_id inválido")

    project_id  = parts[0]
    orientation = parts[1]   # "horizontal" | "vertical"
    seg_id      = parts[2] if len(parts) >= 3 else None

    return await _process_segment_result(
        project_id=project_id,
        orientation=orientation,
        seg_id=seg_id,
        status=status,
        video_url=video_url,
        error=payload.error,
    )


@app.post("/heygen-callback", response_model=CallbackResponse)
async def heygen_lipsync_callback(
    payload: HeyGenLipsyncCallbackPayload,
    x_heygen_token: Optional[str] = Header(default=None, alias="X-HeyGen-Token"),
) -> CallbackResponse:
    """
    Callback do Lipsync API (mantido para compatibilidade).
    Também recebe callbacks do Video Generation API que usem este endpoint.
    """
    if _callback_token and x_heygen_token != _callback_token:
        raise HTTPException(status_code=401, detail="Token inválido")

    lipsync_id = payload.lipsync_id or ""
    status     = payload.status or "unknown"

    logger.info("[HeyGenCallback] Lipsync/video callback: id=%s status=%s", lipsync_id, status)

    # Tentar resolver via Firestore collection_group
    result = await _firestore.resolve_lipsync_to_project(lipsync_id)
    if not result:
        logger.warning("[HeyGenCallback] ID não encontrado: %s", lipsync_id)
        return CallbackResponse(ok=False, message=f"ID {lipsync_id} não encontrado")

    project_id, orientation = result

    return await _process_segment_result(
        project_id=project_id,
        orientation=orientation,
        seg_id=None,  # legado: sem seg_id
        status=status,
        video_url=payload.video_url,
        error=payload.error,
    )


async def _process_segment_result(
    project_id: str,
    orientation: str,
    seg_id: Optional[str],
    status: str,
    video_url: Optional[str],
    error: Optional[str],
) -> CallbackResponse:
    """
    BUG2 fix: processa o resultado de geração de 1 segmento individual.

    Lógica:
      1. Localiza o segmento em segment_videos.{orientation}[i] pelo seg_id
      2. Se completed: baixa vídeo, salva no GCS, atualiza status do segmento
      3. Se failed: marca o segmento como failed (não cancela os outros)
      4. Verifica se TODOS os segmentos de AMBOS os targets completaram
      5. Se sim: monta listas e publica AvatarCompletedMsg
    """

    # Falha do segmento
    if status == "failed":
        if seg_id:
            # Atualiza apenas o segmento falho — os outros continuam
            await _update_segment_status(project_id, orientation, seg_id, "failed", None)
        else:
            # Fallback legado: marca o stage inteiro como erro
            await _firestore.update_stage(project_id, "avatar", {
                "status": "error",
                "error_message": f"HeyGen falhou para {orientation}: {error}",
                "error_type": "transient",
            })
        logger.error(
            "[HeyGenCallback] Segmento FALHOU: project=%s orientation=%s seg=%s",
            project_id, orientation, seg_id,
        )
        return CallbackResponse(ok=False, message=f"Segmento {seg_id} falhou")

    # Sucesso do segmento
    if status == "completed" and video_url:
        # Nome do arquivo no GCS inclui seg_id para unicidade
        suffix = f"_{seg_id}" if seg_id else f"_{orientation}"
        gcs_path = await _download_and_store_video(
            project_id=project_id,
            orientation=orientation,
            video_url=video_url,
            suffix=suffix,
        )
        if seg_id:
            await _update_segment_status(project_id, orientation, seg_id, "completed", gcs_path)
        else:
            # Fallback legado (sem seg_id): compatibilidade com lipsync_jobs
            await _firestore.update_stage(project_id, "avatar", {
                f"lipsync_jobs.{orientation}.status": "completed",
                f"lipsync_jobs.{orientation}.video_url": gcs_path,
            })
        logger.info("[HeyGenCallback] Segmento OK: seg=%s gcs=%s", seg_id, gcs_path)

    # Verifica se todos os segmentos completaram
    return await _check_and_publish_if_complete(project_id)


async def _update_segment_status(
    project_id: str,
    orientation: str,
    seg_id: str,
    new_status: str,
    video_url: Optional[str],
) -> None:
    """Atualiza o status de um segmento individual no Firestore."""
    project        = await _firestore.get_project(project_id)
    segment_videos = project["stages"]["avatar"].get("segment_videos", {})
    segs           = segment_videos.get(orientation, [])

    for seg in segs:
        if seg.get("seg_id") == seg_id:
            seg["status"]    = new_status
            seg["video_url"] = video_url
            break

    await _firestore.update_stage(project_id, "avatar", {
        f"segment_videos.{orientation}": segs,
    })


async def _check_and_publish_if_complete(project_id: str) -> CallbackResponse:
    """
    Verifica se todos os segmentos de ambos targets completaram.
    Se sim, monta as listas e publica AvatarCompletedMsg.
    """
    project        = await _firestore.get_project(project_id)
    segment_videos = project["stages"]["avatar"].get("segment_videos", {})

    # Verifica se temos segmentos para ambos os targets
    h_segs = segment_videos.get("horizontal", [])
    v_segs = segment_videos.get("vertical",   [])

    # Considera um target "done" se todos seus segmentos estão completed ou failed
    def _all_resolved(segs: list) -> bool:
        return bool(segs) and all(
            s.get("status") in ("completed", "failed") for s in segs
        )

    def _all_completed(segs: list) -> bool:
        return bool(segs) and all(s.get("status") == "completed" for s in segs)

    h_done = _all_resolved(h_segs) if h_segs else True  # sem segs = target vazio = ok
    v_done = _all_resolved(v_segs) if v_segs else True

    if not (h_done and v_done):
        completed_h = sum(1 for s in h_segs if s.get("status") == "completed")
        completed_v = sum(1 for s in v_segs if s.get("status") == "completed")
        logger.info(
            "[HeyGenCallback] Aguardando segmentos. h=%d/%d v=%d/%d project=%s",
            completed_h, len(h_segs), completed_v, len(v_segs), project_id,
        )
        return CallbackResponse(ok=True, message="Aguardando segmentos restantes")

    # Monta listas de paths (apenas segmentos completados, na ordem original)
    h_paths    = [s["video_url"] for s in h_segs if s.get("status") == "completed" and s.get("video_url")]
    v_paths    = [s["video_url"] for s in v_segs if s.get("status") == "completed" and s.get("video_url")]
    seg_ids    = [s["seg_id"]   for s in h_segs if s.get("status") == "completed"]
    v_seg_ids  = [s["seg_id"]   for s in v_segs if s.get("status") == "completed"]

    if not h_paths and not v_paths:
        logger.error("[HeyGenCallback] Todos os segmentos falharam para %s.", project_id)
        await _firestore.update_stage(project_id, "avatar", {
            "status": "error",
            "error_message": "Todos os segmentos HeyGen falharam.",
        })
        return CallbackResponse(ok=False, message="Todos os segmentos falharam")

    logger.info(
        "[HeyGenCallback] TODOS completados para %s. h=%d v=%d segs=%d. Publicando avatar_completed.",
        project_id, len(h_paths), len(v_paths), len(seg_ids),
    )

    _pubsub.publish(AVATAR_COMPLETED_TOPIC, AvatarCompletedMsg(
        project_id=project_id,
        horizontal_video_paths=h_paths,
        vertical_video_paths=v_paths,
        segment_ids=seg_ids,
        vertical_segment_ids=v_seg_ids,
        duration_seconds=0.0,
        total_cost_usd=0.0,
    ))
    await _firestore.update_stage(project_id, "avatar", {
        "status": "completed",
        "completed_at": int(time.time()),
    })
    return CallbackResponse(ok=True, message="avatar_completed publicado")


async def _download_and_store_video(
    project_id: str,
    orientation: str,
    video_url: str,
    suffix: str = "",
) -> str:
    """Baixa vídeo da URL HeyGen e armazena no GCS."""
    gcs_path     = f"projects/{project_id}/avatar{suffix}.mp4"
    full_gcs_uri = f"gs://{GCS_BUCKET}/{gcs_path}"

    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.get(video_url)
        resp.raise_for_status()

    video_bytes = resp.content
    bucket = _gcs.bucket(GCS_BUCKET)
    blob   = bucket.blob(gcs_path)
    loop   = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: blob.upload_from_string(video_bytes, content_type="video/mp4"),
    )
    logger.info(
        "[HeyGenCallback] Armazenado: %s (%d bytes)", full_gcs_uri, len(video_bytes)
    )
    return full_gcs_uri
