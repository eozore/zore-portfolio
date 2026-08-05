"""
agents/pipeline/shared/retry.py
================================
Retry com exponential backoff para chamadas de API externas.

Design:
- Erros HTTP permanentes (não em transient_errors) → re-lança imediatamente
- Erros transitórios → espera backoff[attempt]s e tenta novamente
- Atualiza retry_count no Firestore ANTES de aguardar (visibilidade em tempo real)
"""

import asyncio
import logging
from typing import Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ApiError(Exception):
    """Erro de API com status HTTP para classificação transitório/permanente."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(f"HTTP {status_code}: {message}")


async def with_retry(
    fn: Callable,
    max_retries: int = 3,
    backoff: list[float] | None = None,
    transient_errors: tuple[int, ...] = (429, 503),
    project_id: Optional[str] = None,
    stage_id: Optional[str] = None,
    firestore=None,
) -> T:
    """
    Executa `fn` com retry automático para erros transitórios.

    Regras:
    - Erros com status_code NOT IN transient_errors → re-lança imediatamente (erro permanente)
    - A cada retry: atualiza retry_count no Firestore ANTES de aguardar
    - Backoff: espera backoff[attempt] segundos antes de re-tentar
    - Após max_retries tentativas sem sucesso → re-lança o último ApiError

    Args:
        fn:               Callable async sem argumentos (use functools.partial ou lambda)
        max_retries:      Número máximo de tentativas (default: 3)
        backoff:          Lista de segundos de espera por tentativa (default: [1.0, 4.0, 16.0])
        transient_errors: Tuple de status codes HTTP considerados transitórios
        project_id:       ID do projeto para atualizar Firestore (opcional)
        stage_id:         ID do stage ("tts", "avatar", etc.) para atualizar Firestore (opcional)
        firestore:        Instância do FirestoreClient (opcional)

    Returns:
        Resultado de `fn()` na primeira tentativa bem-sucedida

    Raises:
        ApiError: quando erro permanente OU quando max_retries esgotado
    """
    if backoff is None:
        backoff = [1.0, 4.0, 16.0]

    last_error: Optional[ApiError] = None

    for attempt in range(max_retries):
        try:
            return await fn()
        except ApiError as exc:
            if exc.status_code not in transient_errors:
                # Erro permanente: falha rápida, sem retry
                logger.error(
                    "Erro permanente HTTP %d na tentativa %d/%d: %s",
                    exc.status_code,
                    attempt + 1,
                    max_retries,
                    exc.message,
                )
                raise

            last_error = exc
            retry_count = attempt + 1
            sleep_s = backoff[attempt] if attempt < len(backoff) else backoff[-1]

            logger.warning(
                "Erro transitório HTTP %d na tentativa %d/%d. "
                "Aguardando %.1fs... project=%s stage=%s",
                exc.status_code,
                retry_count,
                max_retries,
                sleep_s,
                project_id,
                stage_id,
            )

            # Atualiza retry_count no Firestore ANTES de dormir (somente entre tentativas)
            if (
                firestore is not None
                and project_id is not None
                and stage_id is not None
                and attempt < max_retries - 1
            ):
                await firestore.update_stage(
                    project_id,
                    stage_id,
                    {"retry_count": retry_count, "status": "retrying"},
                )

            if attempt < max_retries - 1:
                await asyncio.sleep(sleep_s)

    raise last_error
