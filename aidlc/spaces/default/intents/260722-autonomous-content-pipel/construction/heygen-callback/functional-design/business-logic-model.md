# Business Logic Model — U-10: heygen-callback

> Referências: [unit-of-work.md](../../../inception/units-generation/unit-of-work.md) | [requirements.md](../../../inception/requirements-analysis/requirements.md) | [components.md](../../../inception/application-design/components.md) | [component-methods.md](../../../inception/application-design/component-methods.md) | [services.md](../../../inception/application-design/services.md) | [unit-of-work-story-map.md](../../../inception/units-generation/unit-of-work-story-map.md)

---

## Visão Geral

`HeyGenCallbackHandler` é um Cloud Run Service FastAPI que recebe webhooks HeyGen quando jobs Lipsync completam. Implementa a lógica crítica de "ambos completados": só publica `avatar_completed` no Pub/Sub quando **ambos** horizontal e vertical têm `status == "completed"`. Qualquer falha de qualquer um seta `stages.avatar.status = "error"` imediatamente.

**Path no monorepo:** `agents/pipeline/heygen_callback/`
**Entry point:** `uvicorn heygen_callback.app:app --host 0.0.0.0 --port 8091`
**Trigger:** HTTP POST webhook da HeyGen
**Port:** 8091
**Scaling:** min-instances=0, max-instances=1

---

## Fluxo de Execução

```
[POST /heygen-callback]
        │
        ▼
1. Valida header X-HeyGen-Token vs HEYGEN_CALLBACK_TOKEN do Secret Manager
   → 401 se inválido
        │
        ▼
2. Parseia payload: {lipsync_id, status, video_url}
        │
        ▼
3. Resolve lipsync_id → (project_id, orientation)
   via Firestore collection_group("lipsync_jobs")
   → 404 se não encontrado
        │
        ▼
4. Se status == "failed":
   → Atualiza stages.avatar.lipsync_jobs.{orientation}.status = "failed"
   → Atualiza stages.avatar.status = "error"
   → Retorna 200 (webhook sempre recebe 200 para não gerar retry HeyGen)
        │
        ▼
5. Se status == "completed":
   a. Baixa vídeo da video_url e salva no GCS
      gs://{bucket}/projects/{project_id}/avatar_{orientation}.mp4
   b. Atualiza stages.avatar.lipsync_jobs.{orientation}:
      {status: "completed", video_url: <gcs_path>}
        │
        ▼
6. LÓGICA CRÍTICA — verifica se AMBOS completados:
   Lê stages.avatar.lipsync_jobs do Firestore (estado atual)
   se horizontal.status == "completed" AND vertical.status == "completed":
     → Publica avatar_completed no Pub/Sub
     → Atualiza stages.avatar.status = "completed"
   else:
     → Retorna 200 (aguarda segundo callback)
        │
        ▼
7. Retorna {"ok": true}
```

---

## Especificação Detalhada

### Modelos de Dados

```python
# agents/pipeline/heygen_callback/app.py

from pydantic import BaseModel
from typing import Literal, Optional


class HeyGenCallbackPayload(BaseModel):
    """Payload do webhook HeyGen Lipsync v3."""
    lipsync_id: str
    status:     Literal["completed", "failed", "processing"]
    video_url:  Optional[str] = None  # presente apenas quando status == "completed"
    error:      Optional[str] = None  # presente quando status == "failed"


class CallbackResponse(BaseModel):
    ok: bool
    message: Optional[str] = None
```

### FastAPI Application

```python
# agents/pipeline/heygen_callback/app.py (continuação)

import asyncio
import logging
import os
import time

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from google.cloud import storage

from shared.firestore_client import FirestoreClient
from shared.pubsub_client import PubSubClient, get_secret
from shared.models import AvatarCompletedMsg

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="HeyGen Callback Handler")

GCP_PROJECT_ID = os.environ["GCP_PROJECT_ID"]
GCS_BUCKET     = os.environ["GCS_BUCKET"]
TENANT_ID      = os.environ.get("TENANT_ID", "default")

# Inicializado no startup (evita cold start lento no primeiro request)
_firestore: FirestoreClient | None = None
_pubsub: PubSubClient | None = None
_gcs: storage.Client | None = None
_callback_token: str | None = None


@app.on_event("startup")
async def startup():
    global _firestore, _pubsub, _gcs, _callback_token
    _firestore      = FirestoreClient(GCP_PROJECT_ID)
    _pubsub         = PubSubClient(GCP_PROJECT_ID)
    _gcs            = storage.Client()
    _callback_token = get_secret("heygen-callback-token", GCP_PROJECT_ID)
    logger.info("[HeyGenCallback] Serviço iniciado.")


@app.get("/health")
async def health_check():
    """Endpoint de saúde para Cloud Run readiness probe."""
    return {"status": "ok"}


@app.post("/heygen-callback", response_model=CallbackResponse)
async def heygen_callback(
    payload: HeyGenCallbackPayload,
    x_heygen_token: str | None = Header(default=None, alias="X-HeyGen-Token"),
) -> CallbackResponse:
    """
    Recebe webhook HeyGen quando job Lipsync completa ou falha.

    Sempre retorna HTTP 200 para evitar retry automático do HeyGen
    (mesmo em casos de erro de negócio — apenas erros de infra propagam exceção).
    """
    # ── Autenticação ──────────────────────────────────────────────────────────
    if x_heygen_token != _callback_token:
        logger.warning(f"[HeyGenCallback] Token inválido para lipsync_id={payload.lipsync_id}")
        raise HTTPException(status_code=401, detail="Token inválido")

    lipsync_id = payload.lipsync_id
    logger.info(f"[HeyGenCallback] Recebido: lipsync_id={lipsync_id} status={payload.status}")

    # ── Resolver lipsync_id → project_id + orientation ───────────────────────
    result = await _firestore.resolve_lipsync_to_project(lipsync_id)
    if not result:
        logger.error(f"[HeyGenCallback] lipsync_id não encontrado: {lipsync_id}")
        # Retorna 200 mesmo assim — pode ser callback duplicado ou lipsync antigo
        return CallbackResponse(ok=False, message=f"lipsync_id {lipsync_id} não encontrado")

    project_id, orientation = result
    logger.info(f"[HeyGenCallback] Resolvido: project_id={project_id} orientation={orientation}")

    # ── Processar falha ───────────────────────────────────────────────────────
    if payload.status == "failed":
        await _firestore.update_stage(project_id, "avatar", {
            f"lipsync_jobs.{orientation}.status": "failed",
        })
        await _firestore.update_stage(project_id, "avatar", {
            "status": "error",
            "error_message": f"HeyGen lipsync falhou para {orientation}: {payload.error}",
            "error_type": "transient",  # HeyGen pode ser re-tentado via manual-retry
        })
        logger.error(f"[HeyGenCallback] Lipsync FALHOU: project={project_id} orientation={orientation}")
        return CallbackResponse(ok=False, message="Lipsync falhou — stages.avatar.status = error")

    # ── Processar sucesso ─────────────────────────────────────────────────────
    if payload.status == "completed" and payload.video_url:
        # Baixa vídeo da video_url e salva no GCS
        gcs_path = await _download_and_store_video(
            project_id=project_id,
            orientation=orientation,
            video_url=payload.video_url,
        )

        # Atualiza lipsync_job no Firestore
        await _firestore.update_stage(project_id, "avatar", {
            f"lipsync_jobs.{orientation}.status":    "completed",
            f"lipsync_jobs.{orientation}.video_url": gcs_path,
        })
        logger.info(f"[HeyGenCallback] Vídeo salvo: {gcs_path}")

    # ── LÓGICA CRÍTICA: ambos completados? ────────────────────────────────────
    project = await _firestore.get_project(project_id)
    lipsync_jobs = project["stages"]["avatar"].get("lipsync_jobs", {})

    h_status = lipsync_jobs.get("horizontal", {}).get("status")
    v_status = lipsync_jobs.get("vertical", {}).get("status")

    if h_status == "completed" and v_status == "completed":
        logger.info(f"[HeyGenCallback] AMBOS completados para {project_id}. Publicando avatar_completed.")

        h_video = lipsync_jobs["horizontal"]["video_url"]
        v_video = lipsync_jobs["vertical"]["video_url"]

        # Duração estimada — VideoEditorJob calculará a real via ffprobe
        duration_s = project["stages"]["avatar"].get("cost_estimated", 0.0) / 0.0335 if project["stages"]["avatar"].get("cost_estimated") else 0.0

        msg = AvatarCompletedMsg(
            project_id=project_id,
            horizontal_video_path=h_video,
            vertical_video_path=v_video,
            duration_seconds=duration_s,
            total_cost_usd=0.0,  # custo real calculado pelo VideoEditorJob via ffprobe
        )
        _pubsub.publish("content-pipeline.avatar-completed", msg)

        await _firestore.update_stage(project_id, "avatar", {
            "status": "completed",
            "completed_at": int(time.time()),
        })
        return CallbackResponse(ok=True, message="avatar_completed publicado")
    else:
        logger.info(
            f"[HeyGenCallback] Aguardando segundo callback. "
            f"horizontal={h_status} vertical={v_status} project={project_id}"
        )
        return CallbackResponse(ok=True, message="Aguardando segundo lipsync")


async def _download_and_store_video(
    project_id: str,
    orientation: str,
    video_url: str,
) -> str:
    """
    Baixa vídeo da URL HeyGen e armazena no GCS.

    GCS path: gs://{bucket}/projects/{project_id}/avatar_{orientation}.mp4

    Returns:
        GCS URI do vídeo armazenado
    """
    gcs_path = f"projects/{project_id}/avatar_{orientation}.mp4"
    full_gcs_uri = f"gs://{GCS_BUCKET}/{gcs_path}"

    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.get(video_url)
        response.raise_for_status()

    loop = asyncio.get_event_loop()
    video_bytes = response.content
    bucket = _gcs.bucket(GCS_BUCKET)
    blob   = bucket.blob(gcs_path)

    await loop.run_in_executor(
        None,
        lambda: blob.upload_from_string(video_bytes, content_type="video/mp4")
    )
    logger.info(f"[HeyGenCallback] Vídeo armazenado: {full_gcs_uri} ({len(video_bytes):,} bytes)")
    return full_gcs_uri
```

---

## Invariantes de Negócio

| # | Condição | Resultado esperado |
|---|---|---|
| I-1 | Primeiro callback (horizontal completed) | Atualiza `lipsync_jobs.horizontal.status="completed"`, **NÃO** publica `avatar_completed` |
| I-2 | Segundo callback (vertical completed) | Atualiza `lipsync_jobs.vertical.status="completed"`, **publica** `avatar_completed` |
| I-3 | Callback com status="failed" | `stages.avatar.status="error"`, retorna 200 |
| I-4 | Token inválido | Retorna HTTP 401 |
| I-5 | `lipsync_id` não encontrado | Retorna 200 com `ok=false` (não re-tenta HeyGen) |
| I-6 | Callback duplicado (orientation já "completed") | Lê Firestore, verifica ambos, re-publica `avatar_completed` se ambos OK (idempotente) |

---

## Testes Nyquist — U-10

### NT-1: Primeiro callback não publica

```python
# tests/test_heygen_callback.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from heygen_callback.app import app

VALID_TOKEN = "test-callback-token-123"


def make_project_state(h_status: str, v_status: str) -> dict:
    return {
        "stages": {
            "avatar": {
                "status": "pending_callback",
                "lipsync_jobs": {
                    "horizontal": {"lipsync_id": "lip-001", "status": h_status, "video_url": None},
                    "vertical":   {"lipsync_id": "lip-002", "status": v_status, "video_url": None},
                }
            }
        }
    }


@pytest.fixture
def client(monkeypatch):
    """TestClient com mocks de infra injetados."""
    import heygen_callback.app as app_module

    mock_firestore = AsyncMock()
    mock_pubsub    = MagicMock()

    app_module._firestore      = mock_firestore
    app_module._pubsub         = mock_pubsub
    app_module._gcs            = MagicMock()
    app_module._callback_token = VALID_TOKEN

    return TestClient(app), mock_firestore, mock_pubsub


def test_first_callback_does_not_publish_avatar_completed(client):
    """
    Dado: projeto com horizontal=pending, vertical=pending
    Quando: primeiro callback (horizontal=completed) chega
    Então: Firestore atualizado, avatar_completed NÃO publicado
    """
    test_client, mock_firestore, mock_pubsub = client

    # Estado após atualizar horizontal: horizontal=completed, vertical=pending
    mock_firestore.resolve_lipsync_to_project = AsyncMock(return_value=("proj-123", "horizontal"))
    mock_firestore.get_project = AsyncMock(return_value=make_project_state("completed", "pending"))
    mock_firestore.update_stage = AsyncMock()

    with patch("heygen_callback.app._download_and_store_video", return_value="gs://b/h.mp4"):
        response = test_client.post(
            "/heygen-callback",
            json={"lipsync_id": "lip-001", "status": "completed", "video_url": "https://cdn.heygen.com/h.mp4"},
            headers={"X-HeyGen-Token": VALID_TOKEN},
        )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    # avatar_completed NÃO publicado
    mock_pubsub.publish.assert_not_called()


def test_second_callback_publishes_avatar_completed(client):
    """
    Dado: projeto com horizontal=completed (já processado), vertical=pending
    Quando: segundo callback (vertical=completed) chega
    Então: Firestore atualizado, avatar_completed PUBLICADO
    """
    test_client, mock_firestore, mock_pubsub = client

    # Estado após atualizar vertical: ambos completed
    mock_firestore.resolve_lipsync_to_project = AsyncMock(return_value=("proj-123", "vertical"))
    mock_firestore.get_project = AsyncMock(return_value=make_project_state("completed", "completed"))
    mock_firestore.update_stage = AsyncMock()

    with patch("heygen_callback.app._download_and_store_video", return_value="gs://b/v.mp4"):
        response = test_client.post(
            "/heygen-callback",
            json={"lipsync_id": "lip-002", "status": "completed", "video_url": "https://cdn.heygen.com/v.mp4"},
            headers={"X-HeyGen-Token": VALID_TOKEN},
        )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    # avatar_completed PUBLICADO
    mock_pubsub.publish.assert_called_once()
    topic = mock_pubsub.publish.call_args[0][0]
    assert topic == "content-pipeline.avatar-completed"


def test_callback_with_invalid_token_returns_401(client):
    """Dado: token inválido. Então: HTTP 401."""
    test_client, _, _ = client
    response = test_client.post(
        "/heygen-callback",
        json={"lipsync_id": "lip-001", "status": "completed", "video_url": "https://x.com/v.mp4"},
        headers={"X-HeyGen-Token": "wrong-token"},
    )
    assert response.status_code == 401


def test_health_endpoint():
    """GET /health retorna {"status": "ok"}."""
    with TestClient(app) as c:
        r = c.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

---

## Dependências

| Dependência | Versão | Uso |
|---|---|---|
| `fastapi` | `0.111.0` | Framework HTTP |
| `uvicorn` | `0.29.0` | ASGI server |
| `httpx` | `0.27.0` | Download assíncrono de vídeo |
| `pydantic` | `2.7.0` | Validação de payload |
| `firebase-admin` | `6.4.0` | Firestore via ADC |
| `google-cloud-pubsub` | `2.21.0` | Pub/Sub |
| `google-cloud-storage` | `2.14.0` | Upload GCS |
| `google-cloud-secret-manager` | `2.18.0` | Token de callback |

**Secrets no Secret Manager:**
- `heygen-callback-token` — token para validar autenticidade do webhook HeyGen

**Environment Variables:**
- `GCP_PROJECT_ID`, `GCS_BUCKET`, `TENANT_ID`

**Requisito de infra:** Índice `collection_group` em `lipsync_jobs.lipsync_id` deve existir antes do primeiro deploy (definido em `firestore.indexes.json` — U-01).
