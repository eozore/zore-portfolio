# Business Logic Model — U-07: pipeline-shared-lib

> Referências: [unit-of-work.md](../../../inception/units-generation/unit-of-work.md) | [requirements.md](../../../inception/requirements-analysis/requirements.md) | [components.md](../../../inception/application-design/components.md) | [component-methods.md](../../../inception/application-design/component-methods.md) | [services.md](../../../inception/application-design/services.md) | [unit-of-work-story-map.md](../../../inception/units-generation/unit-of-work-story-map.md)

---

## Visão Geral

`agents/pipeline/shared/` é o módulo Python compartilhado por todos os Cloud Run Jobs da pipeline. Fornece retry com backoff, rastreamento de custo, e wrappers de infra (Firestore, Pub/Sub, Secret Manager). Nenhuma lógica de negócio específica de Job reside aqui — apenas utilitários reutilizáveis.

**Path no monorepo:** `agents/pipeline/shared/`

**Importado por:** `tts_job`, `avatar_job`, `heygen_callback`, `video_editor_job`, `publisher_job`, `publisher_immediate`

---

## Módulo 1: `retry.py`

### Contrato

```python
# agents/pipeline/shared/retry.py

import asyncio
import logging
from typing import Callable, TypeVar, Optional
from shared.firestore_client import FirestoreClient

logger = logging.getLogger(__name__)
T = TypeVar("T")


class ApiError(Exception):
    """Erro de API com status HTTP para classificação transitório/permanente."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"HTTP {status_code}: {message}")


async def with_retry(
    fn: Callable,
    max_retries: int = 3,
    backoff: list[float] = [1.0, 4.0, 16.0],
    transient_errors: tuple[int, ...] = (429, 503),
    project_id: Optional[str] = None,
    stage_id: Optional[str] = None,
    firestore: Optional[FirestoreClient] = None,
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
        backoff:          Lista de segundos de espera por tentativa (default: [1, 4, 16])
        transient_errors: Tuple de status codes HTTP considerados transitórios
        project_id:       ID do projeto para atualizar Firestore (opcional)
        stage_id:         ID do stage ("tts", "avatar", etc.) para atualizar Firestore (opcional)
        firestore:        Instância do FirestoreClient (opcional)

    Returns:
        Resultado de `fn()` na primeira tentativa bem-sucedida

    Raises:
        ApiError: quando erro permanente OU quando max_retries esgotado
    """
    last_error: Optional[ApiError] = None

    for attempt in range(max_retries):
        try:
            return await fn()
        except ApiError as e:
            if e.status_code not in transient_errors:
                logger.error(f"Erro permanente HTTP {e.status_code}: {e.message}")
                raise

            last_error = e
            retry_count = attempt + 1
            logger.warning(
                f"Erro transitório HTTP {e.status_code} na tentativa {retry_count}/{max_retries}. "
                f"Aguardando {backoff[attempt]}s..."
            )

            # Atualiza retry_count no Firestore ANTES de aguardar
            if firestore and project_id and stage_id and attempt < max_retries - 1:
                await firestore.update_stage(project_id, stage_id, {
                    "retry_count": retry_count,
                    "status": "retrying",
                })

            if attempt < max_retries - 1:
                await asyncio.sleep(backoff[attempt])

    raise last_error
```

### Invariantes de `with_retry`

| # | Condição | Resultado esperado |
|---|---|---|
| I-1 | `fn` lança `ApiError(429)` duas vezes e sucede na terceira | Executa 3 vezes, retorna resultado, atualiza `retry_count=1` e `retry_count=2` no Firestore antes de cada espera |
| I-2 | `fn` lança `ApiError(401)` na primeira chamada | Re-lança imediatamente, sem retry, sem espera |
| I-3 | `fn` lança `ApiError(503)` três vezes | Re-lança após 3 tentativas (esperas de 1s, 4s) |
| I-4 | `project_id=None` | Nunca chama Firestore, apenas executa retry normalmente |
| I-5 | `backoff=[1,4,16]` e `attempt=2` | Não dorme após tentativa 3 (última) — espera ocorre apenas entre tentativas |

---

## Módulo 2: `cost_tracker.py`

### Contrato

```python
# agents/pipeline/shared/cost_tracker.py

import logging
import time
from shared.firestore_client import FirestoreClient

logger = logging.getLogger(__name__)

# Taxas de API (USD)
ELEVENLABS_FLASH_V2_5_RATE_USD_PER_CHAR = 0.00005   # $0.00005/char
HEYGEN_SPEED_RATE_USD_PER_SECOND = 0.0335            # $0.0335/s


class CostTrackerService:
    """
    Rastreia custo acumulado por projeto e verifica gates de custo.

    Taxa de câmbio USD→BRL é lida do Firestore pipeline_config.exchange_rate_usd_brl.
    Nunca hardcoded — permite ajuste sem redeploy.
    """

    def __init__(self, firestore: FirestoreClient, tenant_id: str = "default"):
        self.firestore = firestore
        self.tenant_id = tenant_id
        self._exchange_rate: float | None = None

    async def _get_exchange_rate(self) -> float:
        """Lê taxa de câmbio do Firestore. Cache por instância (lifetime do Job)."""
        if self._exchange_rate is None:
            config = await self.firestore.get_pipeline_config(self.tenant_id)
            self._exchange_rate = config.get("exchange_rate_usd_brl", 5.50)
        return self._exchange_rate

    async def estimate_tts_cost(
        self,
        chars: int,
        model: str = "eleven_flash_v2_5",
    ) -> float:
        """
        Estima custo TTS em BRL.

        Args:
            chars: Número de caracteres a processar
            model: Identificador do modelo ElevenLabs (apenas flash_v2_5 suportado)

        Returns:
            Custo estimado em BRL (float)

        Raises:
            ValueError: se model desconhecido
        """
        if model != "eleven_flash_v2_5":
            raise ValueError(f"Modelo desconhecido: {model}. Apenas eleven_flash_v2_5 suportado.")
        cost_usd = chars * ELEVENLABS_FLASH_V2_5_RATE_USD_PER_CHAR
        rate = await self._get_exchange_rate()
        return round(cost_usd * rate, 4)

    async def estimate_heygen_cost(self, duration_s: float) -> float:
        """
        Estima custo HeyGen Lipsync modo speed em BRL.

        Args:
            duration_s: Duração total do áudio em segundos

        Returns:
            Custo estimado em BRL (float)
        """
        cost_usd = duration_s * HEYGEN_SPEED_RATE_USD_PER_SECOND
        rate = await self._get_exchange_rate()
        return round(cost_usd * rate, 4)

    async def check_cost_gate(
        self,
        project_id: str,
        additional_cost: float,
        limit: float,
    ) -> bool:
        """
        Verifica se (custo_atual + additional_cost) ≤ limit.

        Se False: escreve cost_blocked no Firestore imediatamente.

        Args:
            project_id:      ID do projeto
            additional_cost: Custo adicional estimado em BRL (próxima etapa)
            limit:           Teto de custo em BRL (de pipeline_config.cost_limit)

        Returns:
            True se pode prosseguir, False se custo excederia o teto
        """
        project = await self.firestore.get_project(project_id)
        cost_breakdown = project.get("cost_breakdown", {})
        current_cost = cost_breakdown.get("total_real", 0.0)

        if current_cost + additional_cost > limit:
            logger.warning(
                f"[CostGate] BLOQUEADO project={project_id}: "
                f"atual={current_cost:.2f} + estimado={additional_cost:.2f} > limite={limit:.2f} BRL"
            )
            await self.firestore.update_project(project_id, {
                "cost_blocked": {
                    "blocked": True,
                    "current_cost": current_cost,
                    "estimated_next": additional_cost,
                    "limit": limit,
                    "blocked_at": int(time.time()),
                }
            })
            return False

        return True

    async def update_actual_cost(
        self,
        project_id: str,
        stage: str,
        cost_usd: float,
    ) -> None:
        """
        Registra custo real de uma etapa após execução.

        Converte USD → BRL usando taxa de câmbio do Firestore.
        Atualiza cost_breakdown.{stage} e recalcula total_real.

        Args:
            project_id: ID do projeto
            stage:      "tts" | "heygen" | "gemini" | "gcp"
            cost_usd:   Custo real da etapa em USD
        """
        rate = await self._get_exchange_rate()
        cost_brl = round(cost_usd * rate, 4)

        project = await self.firestore.get_project(project_id)
        breakdown = project.get("cost_breakdown", {})
        breakdown[stage] = round(breakdown.get(stage, 0.0) + cost_brl, 4)

        tts = breakdown.get("tts", 0.0) or 0.0
        heygen = breakdown.get("heygen", 0.0) or 0.0
        gemini = breakdown.get("gemini", 0.0) or 0.0
        gcp = breakdown.get("gcp", 0.0) or 0.0
        breakdown["total_real"] = round(tts + heygen + gemini + gcp, 4)

        await self.firestore.update_project(project_id, {"cost_breakdown": breakdown})
        logger.info(
            f"[CostTracker] project={project_id} stage={stage} "
            f"cost_usd={cost_usd:.6f} cost_brl={cost_brl:.4f} total_brl={breakdown['total_real']:.4f}"
        )
```

### Invariantes de `CostTrackerService`

| # | Condição | Resultado esperado |
|---|---|---|
| I-1 | `check_cost_gate(id, 20.0, 100.0)` com `total_real=85.0` | Retorna `False`; escreve `cost_blocked` no Firestore |
| I-2 | `check_cost_gate(id, 14.0, 100.0)` com `total_real=85.0` | Retorna `True`; não escreve no Firestore |
| I-3 | `estimate_tts_cost(10_000)` com `exchange_rate=5.50` | Retorna `0.00005 * 10_000 * 5.50 = 2.75` BRL |
| I-4 | `estimate_heygen_cost(600.0)` com `exchange_rate=5.50` | Retorna `0.0335 * 600 * 5.50 = 110.55` BRL |
| I-5 | `update_actual_cost(id, "tts", 0.75)` com `exchange_rate=5.50` e `tts` atual=0 | `cost_breakdown.tts = 4.125`, `total_real` recalculado |
| I-6 | `estimate_tts_cost(chars, model="unknown")` | Lança `ValueError` |
| I-7 | `exchange_rate_usd_brl` não definido no Firestore | Default = 5.50 (fallback seguro) |

---

## Módulo 3: `firestore_client.py`

### Contrato

```python
# agents/pipeline/shared/firestore_client.py

import logging
from typing import Any
from google.cloud import firestore
from google.cloud.firestore_v1 import AsyncClient

logger = logging.getLogger(__name__)

# Coleções Firestore
COLLECTION_CONTENT_PROJECTS = "content_projects"
COLLECTION_PIPELINE_CONFIG   = "pipeline_config"


class FirestoreClient:
    """
    Wrapper do Firebase Admin SDK para operações da pipeline.

    Usa Application Default Credentials (ADC) — sem chaves explícitas no código.
    Todas as operações são async (AsyncClient).
    """

    def __init__(self, project_id: str):
        self._db: AsyncClient = firestore.AsyncClient(project=project_id)

    async def get_project(self, project_id: str) -> dict[str, Any]:
        """
        Lê documento content_projects/{project_id}.

        Returns:
            Dict com todos os campos do documento

        Raises:
            ProjectNotFoundError: se documento não existe
        """
        ref = self._db.collection(COLLECTION_CONTENT_PROJECTS).document(project_id)
        snap = await ref.get()
        if not snap.exists:
            raise ProjectNotFoundError(f"Projeto não encontrado: {project_id}")
        return snap.to_dict()

    async def update_project(self, project_id: str, updates: dict[str, Any]) -> None:
        """
        Atualiza campos do documento content_projects/{project_id}.

        Usa merge=True (não sobrescreve campos não listados).
        """
        ref = self._db.collection(COLLECTION_CONTENT_PROJECTS).document(project_id)
        await ref.set(updates, merge=True)
        logger.debug(f"[Firestore] update_project project={project_id} fields={list(updates.keys())}")

    async def update_stage(
        self,
        project_id: str,
        stage_id: str,
        updates: dict[str, Any],
    ) -> None:
        """
        Atualiza campos de stages.{stage_id} no documento do projeto.

        Expande automaticamente para dot-notation do Firestore:
          update_stage(id, "tts", {"status": "running"})
          → {"stages.tts.status": "running"}
        """
        dot_updates = {f"stages.{stage_id}.{k}": v for k, v in updates.items()}
        ref = self._db.collection(COLLECTION_CONTENT_PROJECTS).document(project_id)
        await ref.update(dot_updates)
        logger.debug(f"[Firestore] update_stage project={project_id} stage={stage_id} fields={list(updates.keys())}")

    async def get_pipeline_config(self, tenant_id: str) -> dict[str, Any]:
        """
        Lê pipeline_config/{tenant_id}.

        Returns:
            Dict com cost_limit, exchange_rate_usd_brl, schedule, etc.
            Retorna defaults se documento não existe.
        """
        ref = self._db.collection(COLLECTION_PIPELINE_CONFIG).document(tenant_id)
        snap = await ref.get()
        if not snap.exists:
            return {
                "cost_limit": 100.0,
                "alert_threshold": 80.0,
                "exchange_rate_usd_brl": 5.50,
                "schedule": {},
            }
        return snap.to_dict()

    async def resolve_lipsync_to_project(self, lipsync_id: str) -> tuple[str, str] | None:
        """
        Resolve lipsync_id → (project_id, orientation) via collection_group query.

        Query: db.collection_group("lipsync_jobs").where("lipsync_id", "==", lipsync_id).limit(1)

        Requer índice collection_group em firestore.indexes.json (fieldOverrides.lipsync_jobs.lipsync_id).

        Returns:
            Tuple (project_id, orientation) onde orientation = "horizontal" | "vertical"
            None se não encontrado
        """
        query = (
            self._db.collection_group("lipsync_jobs")
            .where("lipsync_id", "==", lipsync_id)
            .limit(1)
        )
        docs = await query.get()
        if not docs:
            return None

        doc = docs[0]
        # Path: content_projects/{project_id}/stages/avatar/lipsync_jobs/{orientation}
        path_parts = doc.reference.path.split("/")
        project_id = path_parts[1]
        orientation = path_parts[-1]  # "horizontal" | "vertical"
        return project_id, orientation


class ProjectNotFoundError(Exception):
    pass
```

---

## Módulo 4: `pubsub_client.py`

### Contrato

```python
# agents/pipeline/shared/pubsub_client.py

import json
import logging
from dataclasses import asdict
from google.cloud import pubsub_v1
from google.cloud import secretmanager

logger = logging.getLogger(__name__)


class PubSubClient:
    """
    Wrapper do Google Cloud Pub/Sub para publicação de mensagens.

    Serializa dataclasses para JSON automaticamente.
    """

    def __init__(self, gcp_project_id: str):
        self._project_id = gcp_project_id
        self._publisher = pubsub_v1.PublisherClient()

    def publish(self, topic: str, message_dataclass) -> str:
        """
        Publica mensagem no tópico Pub/Sub.

        Args:
            topic:              Nome curto do tópico (ex: "content-pipeline.tts-completed")
            message_dataclass:  Instância de dataclass (serializada via dataclasses.asdict)

        Returns:
            message_id retornado pelo Pub/Sub

        Raises:
            Exception: falha de publicação (não faz retry — caller é responsável)
        """
        topic_path = self._publisher.topic_path(self._project_id, topic)
        payload = json.dumps(asdict(message_dataclass)).encode("utf-8")
        future = self._publisher.publish(topic_path, data=payload)
        message_id = future.result()
        logger.info(f"[PubSub] published topic={topic} message_id={message_id}")
        return message_id


def get_secret(secret_name: str, project_id: str, version: str = "latest") -> str:
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
    """
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_name}/versions/{version}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")
```

---

## Testes Nyquist — U-07

### NT-1: `with_retry` — retry em erros transitórios

```python
# tests/test_retry.py
import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from shared.retry import with_retry, ApiError

@pytest.mark.asyncio
async def test_with_retry_succeeds_on_third_attempt():
    """
    Dado: função que lança ApiError(429) duas vezes e sucede na terceira
    Quando: with_retry é chamado com max_retries=3, backoff=[0,0,0]
    Então: executa 3 vezes e retorna o resultado da terceira chamada
    """
    call_count = 0

    async def flaky_fn():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ApiError(429, "rate limited")
        return "success"

    # backoff=[0,0,0] para não atrasar testes
    result = await with_retry(flaky_fn, max_retries=3, backoff=[0, 0, 0])
    assert result == "success"
    assert call_count == 3


@pytest.mark.asyncio
async def test_with_retry_raises_immediately_on_permanent_error():
    """
    Dado: função que lança ApiError(401)
    Quando: with_retry é chamado
    Então: re-lança imediatamente sem retry
    """
    call_count = 0

    async def auth_fail():
        nonlocal call_count
        call_count += 1
        raise ApiError(401, "unauthorized")

    with pytest.raises(ApiError) as exc_info:
        await with_retry(auth_fail, max_retries=3, backoff=[0, 0, 0])

    assert exc_info.value.status_code == 401
    assert call_count == 1  # chamado apenas uma vez


@pytest.mark.asyncio
async def test_with_retry_updates_firestore_before_sleep():
    """
    Dado: função que lança ApiError(429) e projeto/stage fornecidos
    Quando: with_retry detecta erro transitório
    Então: chama firestore.update_stage com retry_count ANTES de dormir
    """
    mock_firestore = AsyncMock()
    mock_firestore.update_stage = AsyncMock()
    call_count = 0

    async def flaky():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise ApiError(429, "rate limited")
        return "ok"

    result = await with_retry(
        flaky,
        max_retries=3,
        backoff=[0, 0, 0],
        project_id="proj-123",
        stage_id="tts",
        firestore=mock_firestore,
    )

    assert result == "ok"
    mock_firestore.update_stage.assert_called_once_with(
        "proj-123", "tts", {"retry_count": 1, "status": "retrying"}
    )
```

### NT-2: `CostTrackerService.check_cost_gate` — bloqueio por custo

```python
# tests/test_cost_tracker.py
import pytest
from unittest.mock import AsyncMock
from shared.cost_tracker import CostTrackerService

@pytest.mark.asyncio
async def test_check_cost_gate_blocks_when_limit_exceeded():
    """
    Dado: projeto com total_real=85.0 BRL e additional_cost=20.0 BRL
    Quando: check_cost_gate(id, 20.0, 100.0) é chamado
    Então: retorna False e escreve cost_blocked no Firestore
    """
    mock_firestore = AsyncMock()
    mock_firestore.get_project = AsyncMock(return_value={
        "cost_breakdown": {"total_real": 85.0}
    })
    mock_firestore.update_project = AsyncMock()
    mock_firestore.get_pipeline_config = AsyncMock(return_value={
        "exchange_rate_usd_brl": 5.50
    })

    service = CostTrackerService(firestore=mock_firestore)
    result = await service.check_cost_gate("proj-abc", additional_cost=20.0, limit=100.0)

    assert result is False
    call_args = mock_firestore.update_project.call_args
    cost_blocked = call_args[0][1]["cost_blocked"]
    assert cost_blocked["blocked"] is True
    assert cost_blocked["current_cost"] == 85.0
    assert cost_blocked["estimated_next"] == 20.0
    assert cost_blocked["limit"] == 100.0


@pytest.mark.asyncio
async def test_check_cost_gate_allows_when_within_limit():
    """
    Dado: projeto com total_real=85.0 BRL e additional_cost=14.0 BRL
    Quando: check_cost_gate(id, 14.0, 100.0) é chamado
    Então: retorna True e NÃO chama update_project
    """
    mock_firestore = AsyncMock()
    mock_firestore.get_project = AsyncMock(return_value={
        "cost_breakdown": {"total_real": 85.0}
    })
    mock_firestore.update_project = AsyncMock()
    mock_firestore.get_pipeline_config = AsyncMock(return_value={
        "exchange_rate_usd_brl": 5.50
    })

    service = CostTrackerService(firestore=mock_firestore)
    result = await service.check_cost_gate("proj-abc", additional_cost=14.0, limit=100.0)

    assert result is True
    mock_firestore.update_project.assert_not_called()
```

---

## Dependências e Constraints

| Constraint | Detalhe |
|---|---|
| ADC (Application Default Credentials) | Nenhuma chave explícita no código. Cloud Run usa a service account do Job automaticamente. |
| `exchange_rate_usd_brl` | Lido do Firestore `pipeline_config/{tenant_id}`. Nunca hardcoded exceto como default de fallback. |
| Índice collection_group | `firestore.indexes.json` deve ter fieldOverride para `lipsync_jobs.lipsync_id` antes de U-10 ser deployado. |
| Async | Todos os métodos são `async def`. Caller deve usar `await`. Não misturar com cliente síncrono do Firestore. |
| Import path | `from shared.xxx import ...` — requer que `agents/pipeline/` esteja no `PYTHONPATH` ou seja o `WORKDIR`. |
