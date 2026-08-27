# -*- coding: utf-8 -*-
"""
token_refresh_job/__main__.py
=============================
Entry point do Cloud Run Job. Roda semanalmente pelo Cloud Scheduler.

    TOKEN_REFRESH_DRY_RUN=true   percorre e decide, mas não grava segredo
    TOKEN_REFRESH_DIAS_LIMITE    renova quando faltar menos que isto (15)
    TOKEN_REFRESH_DIAS_ALERTA    alerta o não-renovável abaixo disto (10)

Sai com 0 mesmo quando há alerta. Alerta não é falha do job: significa que
ele funcionou e encontrou algo que só um humano resolve. Sair diferente de
zero marcaria a execução como quebrada e, com o tempo, ensinaria a ignorá-la.
Quem precisa gritar é o log em nível de ERROR, que é o que uma alert policy
do Cloud Monitoring consegue observar.
"""

import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("token_refresh_job.__main__")


def _ler_segredo(project_id: str):
    from google.cloud import secretmanager
    client = secretmanager.SecretManagerServiceClient()

    def ler(secret_id: str) -> str:
        nome = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
        return client.access_secret_version(
            request={"name": nome}
        ).payload.data.decode("utf-8")

    return ler


def _gravar_segredo(project_id: str):
    from google.cloud import secretmanager
    client = secretmanager.SecretManagerServiceClient()

    def gravar(secret_id: str, payload: str) -> None:
        client.add_secret_version(request={
            "parent": f"projects/{project_id}/secrets/{secret_id}",
            "payload": {"data": payload.encode("utf-8")},
        })
        logger.info("[token-refresh] nova versão gravada em %s", secret_id)

    return gravar


def main() -> None:
    project_id = os.environ.get("GCP_PROJECT_ID", "vazfy-417019")
    dry_run = os.environ.get("TOKEN_REFRESH_DRY_RUN", "false").lower() in ("1", "true", "yes")

    from job import TokenRefreshJob

    tarefa = TokenRefreshJob(
        ler_segredo=_ler_segredo(project_id),
        gravar_segredo=_gravar_segredo(project_id),
        dias_limite=int(os.environ.get("TOKEN_REFRESH_DIAS_LIMITE", "15")),
        dias_alerta=int(os.environ.get("TOKEN_REFRESH_DIAS_ALERTA", "10")),
        dry_run=dry_run,
    )

    logger.info("[token-refresh] iniciando | dry_run=%s", dry_run)
    rel = tarefa.run()
    logger.info("[token-refresh] fim | %s", rel.resumo())

    if rel.falhou:
        sys.exit(1)


if __name__ == "__main__":
    main()
