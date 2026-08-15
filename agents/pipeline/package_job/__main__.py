"""
agents/pipeline/package_job/__main__.py
========================================
Entry point do Cloud Run Job de geração de pacote editorial.

Invocado via: python -m package_job

Lê a mensagem Pub/Sub de PUBSUB_MESSAGE (injetado pelo pipeline-trigger)
ou de stdin (testes locais), no mesmo formato dos demais jobs da pipeline.
"""

import base64
import json
import logging
import os
import sys

from google.cloud import firestore

from shared.models import PackageRequestedMsg
from shared.pubsub_client import get_secret
from package_job.job import PackageJob

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

GCP_PROJECT_ID = os.environ["GCP_PROJECT_ID"]
CMO_AGENT_URL  = os.environ["CMO_AGENT_URL"]


def main() -> None:
    raw = os.environ.get("PUBSUB_MESSAGE") or sys.stdin.read()
    if not raw:
        raise ValueError("Nenhuma mensagem Pub/Sub encontrada (PUBSUB_MESSAGE ou stdin)")

    envelope = json.loads(raw)
    data = base64.b64decode(envelope["message"]["data"]).decode("utf-8")
    msg = PackageRequestedMsg(**json.loads(data))

    if msg.phase not in ("script", "derivatives"):
        raise ValueError(f"phase inválida: {msg.phase!r}")

    logger.info("[PackageJob] Iniciando session=%s phase=%s", msg.session_id, msg.phase)

    # O segredo compartilhado é o mesmo que o Next.js usa para falar com o
    # cmo-agent; sem ele o agent responde 401 em todo endpoint.
    try:
        internal_secret = get_secret("cmo-internal-secret", GCP_PROJECT_ID)
    except Exception as exc:
        logger.warning("[PackageJob] cmo-internal-secret indisponível (%s)", exc)
        internal_secret = ""

    job = PackageJob(
        db=firestore.Client(project=GCP_PROJECT_ID),
        cmo_agent_url=CMO_AGENT_URL,
        internal_secret=internal_secret,
    )
    job.run(msg.session_id, msg.phase, msg.tenant_id)
    logger.info("[PackageJob] Concluído session=%s phase=%s", msg.session_id, msg.phase)


if __name__ == "__main__":
    main()
