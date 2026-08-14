"""
publisher_immediate/app.py
===========================
Cloud Run Service de publicação imediata.

Endpoints:
  GET  /health             — health check
  POST /scheduled          — aciona processamento da fila agendada
  POST /publish-now        — publica um item imediatamente (sem fila)
  POST /publish-video      — publica vídeo pronto (VideoReadyMsg payload)
  POST /pubsub/video-ready — push do Pub/Sub (content-pipeline.video-ready)
  GET  /queue-status       — resumo da fila publish_queue por status/plataforma
"""

import base64
import json
import logging
import os
import sys

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Any, Optional

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("publisher_immediate")

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "vazfy-417019")

app = FastAPI(title="publisher-immediate", version="1.0.0")


# ── Modelos ────────────────────────────────────────────────────────────────────

class PublishNowRequest(BaseModel):
    """Um item de conteúdo para publicação imediata."""
    platform:     str                        # linkedin | instagram | facebook | threads | youtube | youtube_community | youtube_shorts
    format:       str = "text"               # text | image | reel | shorts | story | carousel | thread | community_post
    title:        str = ""
    copy:         str
    imageUrl:     Optional[str] = None
    videoUrl:     Optional[str] = None
    imageHtml:    Optional[str] = None       # HTML para gerar imagem via Playwright (ignorado aqui — já deve vir como imageUrl)
    asset_urls:   Optional[list[str]] = None
    tags:         Optional[list[str]] = None
    threadPosts:  Optional[list[str]] = None # Para threads sequenciais
    privacy:      str = "public"

class VideoReadyRequest(BaseModel):
    project_id:       str
    horizontal_final: str
    vertical_final:   str
    duration_seconds: float = 0.0
    trigger:          str   = "immediate"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "publisher-immediate", "version": "1.0.0"}


@app.post("/scheduled")
def scheduled_trigger(payload: Optional[dict] = None):
    """Aciona processamento da fila agendada (chamado pelo Cloud Scheduler)."""
    logger.info("[/scheduled] Processando fila agendada...")
    try:
        from publisher_job.job import PublisherJob
        job     = PublisherJob(gcp_project_id=GCP_PROJECT_ID)
        results = job.run()
        logger.info(f"[/scheduled] {results}")
        return {"status": "ok", "results": results}
    except Exception as e:
        logger.exception("[/scheduled] Erro")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/publish-now")
def publish_now(req: PublishNowRequest):
    """
    Publica um item imediatamente na plataforma especificada.

    Útil para:
    - Teste de cada plataforma individualmente
    - Publicação manual de itens aprovados no CSM
    - Retry manual de itens com erro

    Retorna o post_id da plataforma em caso de sucesso.
    """
    logger.info(f"[/publish-now] platform={req.platform} format={req.format}")

    data = {
        "platform":    req.platform,
        "format":      req.format,
        "title":       req.title,
        "copy":        req.copy,
        "imageUrl":    req.imageUrl,
        "videoUrl":    req.videoUrl,
        "asset_urls":  req.asset_urls or ([req.imageUrl] if req.imageUrl else []) or ([req.videoUrl] if req.videoUrl else []),
        "tags":        req.tags or ["ia", "machinelearning", "eozore"],
        "threadPosts": req.threadPosts,
        "privacy":     req.privacy,
    }

    try:
        from publisher_job.job import PublisherJob
        job     = PublisherJob(gcp_project_id=GCP_PROJECT_ID)
        post_id = job.publish_single(data)
        logger.info(f"[/publish-now] ✅ {req.platform}: {post_id}")
        return {"status": "published", "platform": req.platform, "post_id": post_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        err = str(e)
        logger.error(f"[/publish-now] ❌ {req.platform}: {err}")
        raise HTTPException(status_code=502, detail=err)
    except Exception as e:
        logger.exception(f"[/publish-now] Erro inesperado")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/publish-video")
def publish_video(req: VideoReadyRequest):
    """
    Publicação imediata pós-vídeo: recebe VideoReadyMsg e publica em todas as plataformas.
    """
    logger.info(f"[/publish-video] project_id={req.project_id}")
    try:
        from shared.models import VideoReadyMsg
        from publisher_job.job import PublisherJob
        msg = VideoReadyMsg(
            project_id=req.project_id,
            horizontal_final=req.horizontal_final,
            vertical_final=req.vertical_final,
            duration_seconds=req.duration_seconds,
            trigger=req.trigger,
        )
        job     = PublisherJob(gcp_project_id=GCP_PROJECT_ID)
        results = job.publish_video_ready(msg)
        return {"status": "ok", "project_id": req.project_id, "results": results}
    except Exception as e:
        logger.exception("[/publish-video] Erro")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/pubsub/video-ready")
def pubsub_video_ready(envelope: dict):
    """
    Consumidor push do tópico content-pipeline.video-ready.

    Sem este endpoint, a mensagem publicada pelo video-editor-job ao terminar o
    vídeo ficava numa subscription pull que NINGUÉM consumia — o vídeo final
    existia no GCS mas nunca era publicado em nenhuma plataforma. A subscription
    `publisher-service-sub` agora é push para cá (OIDC pipeline-jobs-sa).

    Envelope Pub/Sub: {"message": {"data": base64(VideoReadyMsg json)}, ...}
    Retornar 2xx faz o Pub/Sub dar ack; 5xx faz redelivery com backoff.
    """
    try:
        data_b64 = (envelope.get("message") or {}).get("data", "")
        payload = json.loads(base64.b64decode(data_b64).decode("utf-8"))
    except Exception as e:
        logger.error(f"[/pubsub/video-ready] Envelope inválido: {e}")
        # 200 para não ficar em redelivery infinito de mensagem malformada
        return {"status": "ignored", "reason": f"bad envelope: {e}"}

    project_id = payload.get("project_id", "")
    logger.info(f"[/pubsub/video-ready] project_id={project_id}")
    try:
        from shared.models import VideoReadyMsg
        from publisher_job.job import PublisherJob
        msg = VideoReadyMsg(
            project_id=project_id,
            horizontal_final=payload.get("horizontal_final", ""),
            vertical_final=payload.get("vertical_final", ""),
            duration_seconds=payload.get("duration_seconds", 0.0),
            trigger=payload.get("trigger", "scheduled"),
        )
        job = PublisherJob(gcp_project_id=GCP_PROJECT_ID)
        results = job.publish_video_ready(msg)
        logger.info(f"[/pubsub/video-ready] ✅ {project_id}: {results}")
        return {"status": "ok", "project_id": project_id, "results": results}
    except Exception as e:
        logger.exception("[/pubsub/video-ready] Erro — Pub/Sub fará redelivery")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/queue-status")
def queue_status():
    """Resumo da fila publish_queue por status e plataforma."""
    import threading
    result_holder: dict = {}

    def _fetch():
        try:
            from google.cloud import firestore
            import os
            project = os.environ.get("GCP_PROJECT_ID", "vazfy-417019")
            db   = firestore.Client(project=project)
            docs = list(db.collection("publish_queue").limit(200).get())
            stats: dict[str, dict[str, int]] = {}
            errors = []
            for doc in docs:
                d        = doc.to_dict()
                platform = d.get("platform", "unknown")
                status   = d.get("status", "unknown")
                if platform not in stats:
                    stats[platform] = {"pending": 0, "published": 0, "failed": 0, "cancelled": 0}
                stats[platform][status] = stats[platform].get(status, 0) + 1
                if status == "failed":
                    errors.append({
                        "id": doc.id, "platform": platform,
                        "title": d.get("title", "")[:60],
                        "errorCode": d.get("errorCode"),
                        "error": d.get("error", "")[:100],
                    })
            result_holder["data"] = {"stats": stats, "errors": errors[:20], "total_errors": len(errors)}
        except Exception as e:
            result_holder["error"] = str(e)

    t = threading.Thread(target=_fetch, daemon=True)
    t.start()
    t.join(timeout=5)  # 5s máximo

    if "data" in result_holder:
        return result_holder["data"]
    return {
        "stats": {}, "errors": [], "total_errors": 0,
        "note": "Firestore indisponível localmente (gRPC DNS) — funciona no Cloud Run"
    }
