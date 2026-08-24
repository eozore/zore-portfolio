"""
agents/pipeline/vertical_cut_job/__main__.py
=============================================
Entry point do Cloud Run Job do corte vertical.
Invocado via: python -m vertical_cut_job

Aceita duas formas de entrada, porque este job é disparado sob demanda pela
interface (e não por um encadeamento automático de Pub/Sub como os outros):

  VERTICAL_CUT_PROJECT_ID=<project_id>   — execução direta
  PUBSUB_MESSAGE=<envelope>              — mensagem content-pipeline.vertical-cut
"""

import asyncio
import base64
import json
import logging
import os
import sys

from shared.firestore_client import FirestoreClient
from shared.pubsub_client import PubSubClient
from vertical_cut_job.job import VerticalCutJob

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

GCP_PROJECT_ID = os.environ["GCP_PROJECT_ID"]
GCS_BUCKET     = os.environ["GCS_BUCKET"]
TENANT_ID      = os.environ.get("TENANT_ID", "default")


def _read_request() -> tuple[str, list[str]]:
    direct = os.environ.get("VERTICAL_CUT_PROJECT_ID")
    if direct:
        channels = [
            c.strip() for c in os.environ.get("VERTICAL_CUT_CHANNELS", "").split(",")
            if c.strip()
        ]
        return direct, channels

    raw = os.environ.get("PUBSUB_MESSAGE") or sys.stdin.read()
    if not raw:
        raise ValueError(
            "Informe VERTICAL_CUT_PROJECT_ID ou envie a mensagem Pub/Sub."
        )
    envelope = json.loads(raw)
    payload  = json.loads(
        base64.b64decode(envelope["message"]["data"]).decode("utf-8")
    )
    return payload["project_id"], payload.get("channels") or []


async def main() -> None:
    project_id, channels = _read_request()
    logger.info(
        "[VerticalCutJob] Iniciando project_id=%s canais=%s",
        project_id, channels or "(sem publicação)",
    )

    job = VerticalCutJob(
        firestore=FirestoreClient(GCP_PROJECT_ID),
        pubsub=PubSubClient(GCP_PROJECT_ID),
        gcs_bucket=GCS_BUCKET,
        tenant_id=TENANT_ID,
    )
    uri = await job.run(project_id, channels)
    logger.info("[VerticalCutJob] Concluído: %s", uri)


if __name__ == "__main__":
    asyncio.run(main())
