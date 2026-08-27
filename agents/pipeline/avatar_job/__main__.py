"""
agents/pipeline/avatar_job/__main__.py
=========================================
Entry point do Cloud Run Job de Avatar (HeyGen Lipsync v3).
"""

import asyncio
import base64
import json
import logging
import os
import sys

from shared.firestore_client import FirestoreClient
from shared.pubsub_client import PubSubClient, get_secret
from shared.models import TtsCompletedMsg
from avatar_job.job import AvatarJob

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

GCP_PROJECT_ID      = os.environ["GCP_PROJECT_ID"]
GCS_BUCKET          = os.environ["GCS_BUCKET"]
HEYGEN_CALLBACK_URL = os.environ["HEYGEN_CALLBACK_URL"]
TENANT_ID           = os.environ.get("TENANT_ID", "default")


async def main() -> None:
    raw = os.environ.get("PUBSUB_MESSAGE") or sys.stdin.read()
    if not raw:
        raise ValueError("Nenhuma mensagem Pub/Sub encontrada")

    envelope = json.loads(raw)
    data = base64.b64decode(envelope["message"]["data"]).decode("utf-8")
    msg = TtsCompletedMsg(**json.loads(data))

    logger.info("[AvatarJob] Iniciando project_id=%s", msg.project_id)

    # HeyGen key está no Firestore (agent_configurations/api_keys.HEYGEN_API_KEY)
    # Importa firebase_admin para acessar diretamente
    import firebase_admin
    from firebase_admin import firestore as fb_firestore
    if not firebase_admin._apps:
        firebase_admin.initialize_app()
    db = fb_firestore.AsyncClient(project=GCP_PROJECT_ID)
    doc = await db.document("agent_configurations/api_keys").get()
    heygen_key: str = doc.to_dict()["HEYGEN_API_KEY"]

    # A URL COMPLETA é montada aqui — path primeiro, token depois.
    #
    # A ordem não é estética. Antes, o token era colado primeiro e o
    # `avatar_job/job.py` concatenava "/heygen-video-callback" no fim, o que
    # produzia `.../?token=xxx/heygen-video-callback`: o path virava "/" e o
    # endpoint ia parar DENTRO do valor do token. Os quatro callbacks do ciclo
    # de 27/08 voltaram 404, o projeto ficou em `pending_callback` para sempre
    # e os créditos do HeyGen já tinham sido gastos.
    #
    # Quem recebe esta string usa como está. Não concatene nada nela.
    #
    # Token embutido na URL, não em header: o HeyGen só faz POST na URL exata
    # configurada em callback_url, sem suporte a header customizado. É esta
    # query string que autentica o webhook depois que heygen-callback passa a
    # aceitar tráfego não-autenticado por IAM (ver heygen_callback/app.py).
    callback_url = f"{HEYGEN_CALLBACK_URL.rstrip('/')}/heygen-video-callback"
    try:
        callback_token = get_secret("heygen-callback-token", GCP_PROJECT_ID)
        if callback_token:
            sep = "&" if "?" in callback_url else "?"
            callback_url = f"{callback_url}{sep}token={callback_token}"
    except Exception as exc:
        logger.warning("[AvatarJob] heygen-callback-token indisponível (%s) — "
                       "callback seguirá sem autenticação de aplicação.", exc)

    firestore_client = FirestoreClient(GCP_PROJECT_ID)
    pubsub_client    = PubSubClient(GCP_PROJECT_ID)

    job = AvatarJob(
        firestore=firestore_client,
        pubsub=pubsub_client,
        heygen_api_key=heygen_key,
        gcs_bucket=GCS_BUCKET,
        callback_url=callback_url,
        tenant_id=TENANT_ID,
    )
    await job.run(msg)
    logger.info("[AvatarJob] Concluído project_id=%s", msg.project_id)


if __name__ == "__main__":
    asyncio.run(main())
