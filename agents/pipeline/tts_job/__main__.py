"""
agents/pipeline/tts_job/__main__.py
=====================================
Entry point do Cloud Run Job de TTS.

Invocado via: python -m tts_job

Lê a mensagem Pub/Sub do env var PUBSUB_MESSAGE (injetado pelo trigger)
ou de stdin (para testes locais).
"""

import asyncio
import base64
import json
import logging
import os
import sys

from shared.firestore_client import FirestoreClient
from shared.pubsub_client import PubSubClient, get_secret
from shared.models import PackageApprovedMsg
from tts_job.job import TTSJob

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

GCP_PROJECT_ID = os.environ["GCP_PROJECT_ID"]
GCS_BUCKET     = os.environ["GCS_BUCKET"]
TENANT_ID      = os.environ.get("TENANT_ID", "default")


async def main() -> None:
    raw = os.environ.get("PUBSUB_MESSAGE") or sys.stdin.read()
    if not raw:
        raise ValueError("Nenhuma mensagem Pub/Sub encontrada (PUBSUB_MESSAGE ou stdin)")

    envelope = json.loads(raw)
    data = base64.b64decode(envelope["message"]["data"]).decode("utf-8")
    msg = PackageApprovedMsg(**json.loads(data))

    logger.info("[TTSJob] Iniciando project_id=%s", msg.project_id)

    elevenlabs_key = get_secret("elevenlabs-api-key", GCP_PROJECT_ID)
    voice_id       = get_secret("elevenlabs-voice-id", GCP_PROJECT_ID)

    firestore = FirestoreClient(GCP_PROJECT_ID)
    pubsub    = PubSubClient(GCP_PROJECT_ID)

    job = TTSJob(
        firestore=firestore,
        pubsub=pubsub,
        elevenlabs_api_key=elevenlabs_key,
        voice_id=voice_id,
        gcs_bucket=GCS_BUCKET,
        tenant_id=TENANT_ID,
    )
    await job.run(msg)
    logger.info("[TTSJob] Concluído project_id=%s", msg.project_id)


if __name__ == "__main__":
    asyncio.run(main())
