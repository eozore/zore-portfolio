"""
pipeline_trigger/app.py
========================
Cloud Run Service que recebe Pub/Sub push subscriptions e aciona
os Cloud Run Jobs correspondentes via Google Cloud Run Jobs API.

Endpoints:
  POST /trigger/package      <- package-requested -> package-job
  POST /trigger/tts          <- package-approved  -> tts-job
  POST /trigger/avatar       <- tts-completed     -> avatar-job
  POST /trigger/video-editor <- avatar-completed  -> video-editor-job

Cada endpoint recebe o envelope Pub/Sub e passa a mensagem como
override de env var PUBSUB_MESSAGE para o job, via Cloud Run Jobs
execute API com overrides.

Autenticacao: Cloud Run invocado com OIDC token pela subscription.
              Rejeita requests sem Authorization header valido.
              (Cloud Run valida automaticamente quando --no-allow-unauthenticated)
"""
import base64
import json
import logging
import os
import sys
from typing import Any

import google.auth
import google.auth.transport.requests
from fastapi import FastAPI, HTTPException, Request

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
log = logging.getLogger("pipeline_trigger")

app = FastAPI(title="pipeline-trigger", version="1.0.0")

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "vazfy-417019")
GCP_REGION     = os.environ.get("GCP_REGION", "us-central1")


def _execute_job(job_name: str, pubsub_message: str) -> dict[str, Any]:
    """
    Dispara um Cloud Run Job com PUBSUB_MESSAGE como env override.
    Usa a Google Auth library para obter token ADC.
    """
    import google.auth
    import google.auth.transport.requests
    import urllib.request

    credentials, project = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    token = credentials.token

    url = (
        f"https://run.googleapis.com/v2/projects/{GCP_PROJECT_ID}"
        f"/locations/{GCP_REGION}/jobs/{job_name}:run"
    )

    body = json.dumps({
        "overrides": {
            "containerOverrides": [{
                "env": [
                    {"name": "PUBSUB_MESSAGE", "value": pubsub_message}
                ]
            }]
        }
    }).encode()

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            log.info("[trigger] job=%s execution=%s", job_name, result.get("name"))
            return result
    except urllib.error.HTTPError as e:
        body_err = e.read().decode()
        log.error("[trigger] job=%s error=%s body=%s", job_name, e.code, body_err)
        raise HTTPException(status_code=500, detail=f"Job execute failed: {body_err}")


def _parse_pubsub_envelope(body: bytes) -> str:
    """
    Recebe o envelope Pub/Sub e retorna a mensagem como string JSON para o job.
    Valida que tem o campo message.data.
    """
    try:
        envelope = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}")

    if "message" not in envelope:
        raise HTTPException(status_code=400, detail="Missing 'message' field")

    msg = envelope["message"]
    if "data" not in msg:
        raise HTTPException(status_code=400, detail="Missing 'message.data' field")

    # Valida que data e base64 decodificavel
    try:
        base64.b64decode(msg["data"]).decode("utf-8")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid base64 data: {exc}")

    # Passa o envelope inteiro — o __main__.py de cada job espera o envelope completo
    return body.decode("utf-8")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "pipeline-trigger"}


@app.post("/trigger/tts")
async def trigger_tts(request: Request) -> dict:
    """
    Pub/Sub push para content-pipeline.package-approved -> aciona tts-job
    """
    body = await request.body()
    pubsub_message = _parse_pubsub_envelope(body)
    log.info("[trigger/tts] Acionando tts-job size=%d", len(pubsub_message))
    result = _execute_job("tts-job", pubsub_message)
    return {"status": "triggered", "execution": result.get("name")}


@app.post("/trigger/package")
async def trigger_package(request: Request) -> dict:
    """
    Pub/Sub push para content-pipeline.package-requested -> aciona package-job.

    Diferente dos demais, este trigger fica ANTES da aprovação: é a geração do
    roteiro/derivações que antes rodava dentro do request HTTP do Next.js.
    """
    body = await request.body()
    pubsub_message = _parse_pubsub_envelope(body)
    log.info("[trigger/package] Acionando package-job size=%d", len(pubsub_message))
    result = _execute_job("package-job", pubsub_message)
    return {"status": "triggered", "execution": result.get("name")}


@app.post("/trigger/avatar")
async def trigger_avatar(request: Request) -> dict:
    """
    Pub/Sub push para content-pipeline.tts-completed -> aciona avatar-job
    """
    body = await request.body()
    pubsub_message = _parse_pubsub_envelope(body)
    log.info("[trigger/avatar] Acionando avatar-job size=%d", len(pubsub_message))
    result = _execute_job("avatar-job", pubsub_message)
    return {"status": "triggered", "execution": result.get("name")}


@app.post("/trigger/video-editor")
async def trigger_video_editor(request: Request) -> dict:
    """
    Pub/Sub push para content-pipeline.avatar-completed -> aciona video-editor-job
    """
    body = await request.body()
    pubsub_message = _parse_pubsub_envelope(body)
    log.info("[trigger/video-editor] Acionando video-editor-job size=%d", len(pubsub_message))
    result = _execute_job("video-editor-job", pubsub_message)
    return {"status": "triggered", "execution": result.get("name")}
