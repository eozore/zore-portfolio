"""
publisher_job/__main__.py
==========================
Entry point do Cloud Run Job de publicação.

Modos de execução (via env var PUBLISHER_MODE):
  - 'queue'         (default): processa fila publish_queue agendada
  - 'video_ready':  publicação imediata de um VideoReadyMsg (via PUBSUB_MESSAGE)
  - 'single':       publica um item específico (via PUBLISH_ITEM_JSON)
"""

import asyncio
import base64
import json
import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("publisher_job")

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "vazfy-417019")
PUBLISHER_MODE = os.environ.get("PUBLISHER_MODE", "queue")


def main() -> None:
    from publisher_job.job import PublisherJob
    job = PublisherJob(gcp_project_id=GCP_PROJECT_ID)

    if PUBLISHER_MODE == "video_ready":
        # Recebe VideoReadyMsg do Pub/Sub (via PUBSUB_MESSAGE ou stdin)
        raw = os.environ.get("PUBSUB_MESSAGE") or sys.stdin.read()
        if not raw:
            logger.error("PUBSUB_MESSAGE não encontrado")
            sys.exit(1)
        try:
            envelope = json.loads(raw)
            data     = base64.b64decode(envelope["message"]["data"]).decode("utf-8")
            msg_dict = json.loads(data)
        except Exception as e:
            logger.error(f"Falha ao parsear PUBSUB_MESSAGE: {e}")
            sys.exit(1)

        from shared.models import VideoReadyMsg
        msg     = VideoReadyMsg(**msg_dict)
        results = job.publish_video_ready(msg)
        logger.info(f"publish_video_ready results: {results}")

    elif PUBLISHER_MODE == "single":
        # Publica um item específico passado via env var
        item_json = os.environ.get("PUBLISH_ITEM_JSON")
        if not item_json:
            logger.error("PUBLISH_ITEM_JSON não definido")
            sys.exit(1)
        item    = json.loads(item_json)
        post_id = job.publish_single(item)
        logger.info(f"publish_single result: {post_id}")

    else:  # queue (default)
        results = job.run()
        logger.info(f"Queue run results: {results}")
        if results.get("failed", 0) > 0:
            logger.warning(f"{results['failed']} item(s) falharam na publicação")


if __name__ == "__main__":
    main()
