"""
agents/pipeline/shared/pubsub_client.py
=========================================
Wrapper do Google Cloud Pub/Sub e Secret Manager para a content pipeline.

PubSubClient:
  - Serializa dataclasses para JSON automaticamente via dataclasses.asdict
  - Publicação síncrona com future.result() para garantir entrega

get_secret:
  - Lê secrets do GCP Secret Manager
  - NUNCA loga o valor do secret — apenas o nome
"""

import json
import logging
from dataclasses import asdict

from google.cloud import pubsub_v1, secretmanager

logger = logging.getLogger(__name__)


class PubSubClient:
    """
    Wrapper do Google Cloud Pub/Sub para publicação de mensagens.

    Serializa dataclasses para JSON automaticamente.
    """

    def __init__(self, gcp_project_id: str) -> None:
        self._project_id = gcp_project_id
        self._publisher = pubsub_v1.PublisherClient()

    def publish(self, topic: str, message_dataclass: object) -> str:
        """
        Publica mensagem no tópico Pub/Sub.

        Args:
            topic:              Nome curto do tópico
                                (ex: "content-pipeline.tts-completed")
            message_dataclass:  Instância de dataclass
                                (serializada via dataclasses.asdict)

        Returns:
            message_id retornado pelo Pub/Sub

        Raises:
            Exception: falha de publicação (não faz retry — caller é responsável)
        """
        topic_path = self._publisher.topic_path(self._project_id, topic)
        payload = json.dumps(asdict(message_dataclass)).encode("utf-8")  # type: ignore[call-overload]
        future = self._publisher.publish(topic_path, data=payload)
        message_id: str = future.result()
        logger.info(
            "[PubSub] published topic=%s message_id=%s project=%s",
            topic,
            message_id,
            self._project_id,
        )
        return message_id


def get_secret(
    secret_name: str,
    project_id: str,
    version: str = "latest",
) -> str:
    """
    Lê secret do GCP Secret Manager.

    Args:
        secret_name: Nome do secret (ex: "elevenlabs-api-key")
        project_id:  GCP project ID
        version:     Versão do secret (default: "latest")

    Returns:
        Valor do secret como string

    Raises:
        google.api_core.exceptions.NotFound: secret não existe

    Security:
        NUNCA loga o valor retornado — apenas o nome do secret.
    """
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_name}/versions/{version}"
    response = client.access_secret_version(request={"name": name})
    logger.debug("[SecretManager] accessed secret=%s version=%s", secret_name, version)
    # Retorna o valor sem logar — caller é responsável por não expor o conteúdo
    return response.payload.data.decode("UTF-8")
