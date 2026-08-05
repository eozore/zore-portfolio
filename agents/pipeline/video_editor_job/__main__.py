"""
agents/pipeline/video_editor_job/__main__.py
=============================================
Entry point do Cloud Run Job do Video Editor.
Invocado via: python -m video_editor_job
"""

import asyncio
import base64
import json
import logging
import os
import sys

from shared.firestore_client import FirestoreClient
from shared.pubsub_client import PubSubClient
from shared.models import AvatarCompletedMsg
from video_editor_job.job import VideoEditorJob

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
        raise ValueError("Nenhuma mensagem Pub/Sub encontrada")

    envelope = json.loads(raw)
    data = base64.b64decode(envelope["message"]["data"]).decode("utf-8")
    msg = AvatarCompletedMsg(**json.loads(data))

    logger.info("[VideoEditorJob] Iniciando project_id=%s", msg.project_id)

    firestore = FirestoreClient(GCP_PROJECT_ID)
    pubsub    = PubSubClient(GCP_PROJECT_ID)

    job = VideoEditorJob(
        firestore=firestore,
        pubsub=pubsub,
        gcs_bucket=GCS_BUCKET,
        tenant_id=TENANT_ID,
    )
    await job.run(msg)
    logger.info("[VideoEditorJob] Concluído project_id=%s", msg.project_id)


if __name__ == "__main__":
    asyncio.run(main())
