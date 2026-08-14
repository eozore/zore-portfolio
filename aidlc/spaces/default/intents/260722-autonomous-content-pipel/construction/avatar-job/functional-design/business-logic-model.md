# Business Logic Model — U-09: avatar-job

> Referências: [unit-of-work.md](../../../inception/units-generation/unit-of-work.md) | [requirements.md](../../../inception/requirements-analysis/requirements.md) | [components.md](../../../inception/application-design/components.md) | [component-methods.md](../../../inception/application-design/component-methods.md) | [services.md](../../../inception/application-design/services.md) | [unit-of-work-story-map.md](../../../inception/units-generation/unit-of-work-story-map.md)

---

## Visão Geral

`AvatarJob` é um Cloud Run Job Python que gera vídeos de avatar via HeyGen Lipsync API v3. Consome `tts_completed`, concatena os MP3s dos segmentos de avatar, faz upload para HeyGen Assets API, cria dois jobs Lipsync (horizontal + vertical) com callback URL, registra os `lipsync_id`s no Firestore e **termina** — não aguarda a conclusão dos jobs HeyGen.

**Path no monorepo:** `agents/pipeline/avatar_job/`
**Entry point:** `python -m avatar_job`
**Trigger:** Mensagem Pub/Sub `content-pipeline.tts-completed`
**Timeout:** 9000s (150 min) — timeout generoso para upload de áudios grandes
**Memory:** 512 MB

---

## Fluxo de Execução

```
[Pub/Sub: tts_completed]
        │
        ▼
1. Parseia mensagem → extrai project_id, audio_paths, cost_limit
        │
        ▼
2. Idempotência: verifica stages.avatar.status no Firestore
   → se "completed" ou "pending_callback": loga e retorna
        │
        ▼
3. Verifica cost gate (estimate_heygen_cost para duração estimada)
   → se bloqueado: status="error", tipo="permanent" (custo)
        │
        ▼
4. Para CADA target (horizontal, vertical):
   a. Baixa MP3s do GCS para /tmp/
   b. Concatena MP3s com pydub (pause_after_s entre segmentos)
   c. Salva /tmp/{target}_concat.mp3
        │
        ▼
5. Para CADA target:
   a. Upload /tmp/{target}_concat.mp3 para HeyGen Assets API
      POST /v3/assets (multipart/form-data)
      → recebe asset_id
        │
        ▼
6. Para CADA target:
   a. Cria job Lipsync: POST /v3/lipsyncs
      payload: {video, audio, mode, enable_dynamic_duration, callback_url}
      → recebe lipsync_id
   b. Salva stages.avatar.lipsync_jobs.{target} no Firestore
        │
        ▼
7. Atualiza stages.avatar.status = "pending_callback" no Firestore
        │
        ▼
8. Registra custo estimado via CostTrackerService
        │
        ▼
9. Job TERMINA — HeyGenCallbackHandler receberá o resultado
```

---

## Especificação Detalhada

### Entry Point

```python
# agents/pipeline/avatar_job/__main__.py

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

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

GCP_PROJECT_ID     = os.environ["GCP_PROJECT_ID"]
GCS_BUCKET         = os.environ["GCS_BUCKET"]
HEYGEN_CALLBACK_URL = os.environ["HEYGEN_CALLBACK_URL"]  # URL do heygen-callback Cloud Run Service
TENANT_ID          = os.environ.get("TENANT_ID", "default")


async def main() -> None:
    raw = os.environ.get("PUBSUB_MESSAGE") or sys.stdin.read()
    envelope = json.loads(raw)
    data = base64.b64decode(envelope["message"]["data"]).decode("utf-8")
    msg = TtsCompletedMsg(**json.loads(data))

    heygen_key = get_secret("heygen-api-key", GCP_PROJECT_ID)

    firestore = FirestoreClient(GCP_PROJECT_ID)
    pubsub    = PubSubClient(GCP_PROJECT_ID)

    job = AvatarJob(
        firestore=firestore,
        pubsub=pubsub,
        heygen_api_key=heygen_key,
        gcs_bucket=GCS_BUCKET,
        callback_url=HEYGEN_CALLBACK_URL,
        tenant_id=TENANT_ID,
    )
    await job.run(msg)


if __name__ == "__main__":
    asyncio.run(main())
```

### Classe `AvatarJob`

```python
# agents/pipeline/avatar_job/job.py

import asyncio
import logging
import os
import time
from io import BytesIO
from typing import Literal

import requests
from google.cloud import storage
from pydub import AudioSegment

from shared.firestore_client import FirestoreClient
from shared.pubsub_client import PubSubClient
from shared.retry import with_retry, ApiError
from shared.cost_tracker import CostTrackerService
from shared.models import TtsCompletedMsg

logger = logging.getLogger(__name__)

HEYGEN_BASE_URL = "https://api.heygen.com"

# URLs dos vídeos base do avatar (landscape e portrait)
AVATAR_BASE_VIDEOS = {
    "horizontal": "https://storage.googleapis.com/.../avatar_base_landscape.mp4",
    "vertical":   "https://storage.googleapis.com/.../avatar_base_portrait.mp4",
}


class AvatarJob:
    def __init__(
        self,
        firestore: FirestoreClient,
        pubsub: PubSubClient,
        heygen_api_key: str,
        gcs_bucket: str,
        callback_url: str,
        tenant_id: str = "default",
    ):
        self.firestore    = firestore
        self.pubsub       = pubsub
        self.heygen_key   = heygen_api_key
        self.gcs_bucket   = gcs_bucket
        self.callback_url = callback_url
        self.cost         = CostTrackerService(firestore, tenant_id)
        self.gcs          = storage.Client()

    async def run(self, msg: TtsCompletedMsg) -> None:
        project_id = msg.project_id

        # ── Idempotência ──────────────────────────────────────────────────────
        project = await self.firestore.get_project(project_id)
        avatar_status = project["stages"]["avatar"]["status"]
        if avatar_status in ("completed", "pending_callback"):
            logger.info(f"[AvatarJob] Avatar já em status '{avatar_status}' para {project_id}. Ignorando.")
            return

        await self.firestore.update_stage(project_id, "avatar", {
            "status": "running",
            "started_at": int(time.time()),
        })

        try:
            # ── Cost gate ────────────────────────────────────────────────────
            total_duration_s = await self._estimate_total_duration(msg.audio_paths)
            estimated_cost_brl = await self.cost.estimate_heygen_cost(total_duration_s)
            config = await self.firestore.get_pipeline_config("default")
            can_proceed = await self.cost.check_cost_gate(
                project_id, estimated_cost_brl, config.get("cost_limit", 100.0)
            )
            if not can_proceed:
                raise CostGateBlockedError(f"Custo HeyGen bloqueado: estimado={estimated_cost_brl:.2f} BRL")

            # ── Processar cada target ────────────────────────────────────────
            lipsync_ids: dict[str, str] = {}

            for target in ("horizontal", "vertical"):
                paths = msg.audio_paths.get(target, [])
                if not paths:
                    logger.info(f"[AvatarJob] Nenhum segmento para target={target}, pulando.")
                    continue

                # 1. Baixar MP3s e concatenar
                concat_path = await self._concatenate_audio(paths, target, project_id)

                # 2. Upload para HeyGen Assets
                asset_id = await with_retry(
                    lambda p=concat_path: self._upload_to_heygen_assets(p),
                    max_retries=3,
                    backoff=[1.0, 4.0, 16.0],
                    transient_errors=(429, 503),
                    project_id=project_id,
                    stage_id="avatar",
                    firestore=self.firestore,
                )

                # 3. Criar job Lipsync
                lipsync_id = await with_retry(
                    lambda aid=asset_id, t=target: self._create_lipsync_job(aid, t),
                    max_retries=3,
                    backoff=[1.0, 4.0, 16.0],
                    transient_errors=(429, 503),
                    project_id=project_id,
                    stage_id="avatar",
                    firestore=self.firestore,
                )
                lipsync_ids[target] = lipsync_id

                # 4. Salvar lipsync_id no Firestore
                await self.firestore.update_stage(project_id, "avatar", {
                    f"lipsync_jobs.{target}": {
                        "lipsync_id": lipsync_id,
                        "status": "pending",
                        "video_url": None,
                    }
                })
                logger.info(f"[AvatarJob] Lipsync criado: target={target} lipsync_id={lipsync_id}")

            # ── Registra custo estimado e status ────────────────────────────
            await self.firestore.update_stage(project_id, "avatar", {
                "status": "pending_callback",
                "cost_estimated": estimated_cost_brl,
            })

            logger.info(
                f"[AvatarJob] Dois jobs HeyGen criados para {project_id}. "
                f"Aguardando callbacks. lipsync_ids={lipsync_ids}"
            )

        except CostGateBlockedError as e:
            await self.firestore.update_stage(project_id, "avatar", {
                "status": "error",
                "error_message": str(e),
                "error_type": "permanent",
            })
            raise

        except Exception as e:
            await self.firestore.update_stage(project_id, "avatar", {
                "status": "error",
                "error_message": str(e),
                "error_type": "transient",
            })
            raise

    async def _estimate_total_duration(self, audio_paths: dict[str, list[str]]) -> float:
        """
        Estima duração total combinada de todos os MP3s para o cost gate.
        Usa heurística: 150 chars/s de fala em velocidade normal.
        (Duração real calculada após concatenação para custo real.)
        """
        all_paths = audio_paths.get("horizontal", []) + audio_paths.get("vertical", [])
        # ~5s por segmento como estimativa conservadora
        return len(all_paths) * 5.0

    async def _concatenate_audio(
        self,
        gcs_paths: list[str],
        target: str,
        project_id: str,
    ) -> str:
        """
        Baixa MP3s do GCS e concatena com pydub.
        Aplica silence de pause_after_s entre segmentos.

        Returns:
            Path local do arquivo concatenado em /tmp/
        """
        combined = AudioSegment.empty()
        pause_ms = 400  # pause_after_s = 0.4s = 400ms

        loop = asyncio.get_event_loop()

        for gcs_uri in gcs_paths:
            bucket_name, blob_path = gcs_uri.replace("gs://", "").split("/", 1)
            bucket = self.gcs.bucket(bucket_name)
            blob   = bucket.blob(blob_path)

            audio_bytes = await loop.run_in_executor(None, blob.download_as_bytes)
            segment_audio = AudioSegment.from_mp3(BytesIO(audio_bytes))
            combined += segment_audio + AudioSegment.silent(duration=pause_ms)

        output_path = f"/tmp/{project_id}_{target}_concat.mp3"
        combined.export(output_path, format="mp3", bitrate="128k")
        logger.info(f"[AvatarJob] Concatenado: target={target} duration_s={len(combined)/1000:.1f}")
        return output_path

    async def _upload_to_heygen_assets(self, local_path: str) -> str:
        """
        POST /v3/assets (multipart/form-data)

        Returns:
            asset_id retornado pela HeyGen Assets API

        Raises:
            ApiError: com status HTTP para classificação pelo retry
        """
        url = f"{HEYGEN_BASE_URL}/v3/assets"
        headers = {"X-Api-Key": self.heygen_key}

        loop = asyncio.get_event_loop()

        def _upload():
            with open(local_path, "rb") as f:
                resp = requests.post(
                    url,
                    headers=headers,
                    files={"file": (os.path.basename(local_path), f, "audio/mpeg")},
                    timeout=120,
                )
            if resp.status_code not in (200, 201):
                raise ApiError(resp.status_code, resp.text)
            return resp.json()["data"]["asset_id"]

        return await loop.run_in_executor(None, _upload)

    async def _create_lipsync_job(self, audio_asset_id: str, target: str) -> str:
        """
        POST /v3/lipsyncs

        Payload:
        {
          "video": {"type": "url", "url": <base_video_url>},
          "audio": {"type": "asset_id", "asset_id": "<asset_id>"},
          "mode": "speed",
          "enable_dynamic_duration": true,
          "callback_url": "<HEYGEN_CALLBACK_URL>/heygen-callback"
        }

        Returns:
            lipsync_id retornado pela HeyGen Lipsync API

        Raises:
            ApiError: com status HTTP
        """
        url = f"{HEYGEN_BASE_URL}/v3/lipsyncs"
        headers = {
            "X-Api-Key": self.heygen_key,
            "Content-Type": "application/json",
        }
        payload = {
            "video": {
                "type": "url",
                "url": AVATAR_BASE_VIDEOS[target],
            },
            "audio": {
                "type": "asset_id",
                "asset_id": audio_asset_id,
            },
            "mode": "speed",
            "enable_dynamic_duration": True,
            "callback_url": f"{self.callback_url}/heygen-callback",
        }

        loop = asyncio.get_event_loop()

        def _create():
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            if resp.status_code not in (200, 201):
                raise ApiError(resp.status_code, resp.text)
            return resp.json()["data"]["lipsync_id"]

        return await loop.run_in_executor(None, _create)


class CostGateBlockedError(Exception):
    pass
```

---

## Campos Firestore Atualizados

**`content_projects/{project_id}/stages/avatar`** ao longo da execução:

| Momento | Campos atualizados |
|---|---|
| Início | `status="running"`, `started_at=unix_ts` |
| Cost gate bloqueado | `status="error"`, `error_message`, `error_type="permanent"` |
| Após criar lipsync (horizontal) | `lipsync_jobs.horizontal = {lipsync_id, status="pending", video_url=null}` |
| Após criar lipsync (vertical) | `lipsync_jobs.vertical = {lipsync_id, status="pending", video_url=null}` |
| Job termina (sucesso) | `status="pending_callback"`, `cost_estimated=float` |

**Nota:** O status `"completed"` é escrito pelo HeyGenCallbackHandler (U-10), não pelo AvatarJob.

---

## Testes Nyquist — U-09

### NT-1: Happy path — dois lipsync_ids salvos no Firestore

```python
# tests/test_avatar_job.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from shared.models import TtsCompletedMsg
from avatar_job.job import AvatarJob

@pytest.mark.asyncio
async def test_avatar_job_creates_two_lipsync_ids():
    """
    Dado: TtsCompletedMsg com audio_paths para horizontal e vertical
    Quando: AvatarJob.run() é executado
    Então:
      - HeyGen Assets API chamada 2x (uma por target)
      - HeyGen Lipsync API chamada 2x (uma por target)
      - stages.avatar.lipsync_jobs.horizontal e .vertical salvos no Firestore
      - stages.avatar.status = "pending_callback"
      - Job TERMINA (não publica Pub/Sub)
    """
    mock_firestore = AsyncMock()
    mock_firestore.get_project = AsyncMock(return_value={
        "stages": {"avatar": {"status": "pending"}},
        "cost_breakdown": {"total_real": 0.0},
    })
    mock_firestore.get_pipeline_config = AsyncMock(return_value={
        "cost_limit": 100.0,
        "exchange_rate_usd_brl": 5.50,
    })
    mock_firestore.update_stage  = AsyncMock()
    mock_firestore.update_project = AsyncMock()

    mock_pubsub = MagicMock()

    job = AvatarJob(
        firestore=mock_firestore,
        pubsub=mock_pubsub,
        heygen_api_key="heygen-test-key",
        gcs_bucket="test-bucket",
        callback_url="https://heygen-callback.run.app",
    )

    # Mocks de HeyGen
    with patch.object(job, "_concatenate_audio", return_value="/tmp/test.mp3"), \
         patch.object(job, "_upload_to_heygen_assets", side_effect=["asset-h", "asset-v"]) as mock_upload, \
         patch.object(job, "_create_lipsync_job", side_effect=["lipsync-001", "lipsync-002"]) as mock_lipsync:

        msg = TtsCompletedMsg(
            project_id="proj-xyz",
            audio_paths={
                "horizontal": ["gs://bucket/projects/proj-xyz/audio/horizontal/yt-01.mp3"],
                "vertical":   ["gs://bucket/projects/proj-xyz/audio/vertical/r1-01.mp3"],
            },
            total_cost_usd=0.01,
            segment_count=2,
        )
        await job.run(msg)

    # Assets API chamado 2 vezes
    assert mock_upload.call_count == 2

    # Lipsync API chamado 2 vezes
    assert mock_lipsync.call_count == 2

    # Verificar que lipsync_jobs foram salvos no Firestore
    update_calls = mock_firestore.update_stage.call_args_list
    lipsync_updates = [
        call[0][2]
        for call in update_calls
        if "lipsync_jobs.horizontal" in str(call) or "lipsync_jobs.vertical" in str(call)
    ]
    assert len(lipsync_updates) == 2

    # Status final deve ser "pending_callback"
    final_call = update_calls[-1][0][2]
    assert final_call["status"] == "pending_callback"

    # Pub/Sub NÃO publicado (job termina sem publicar avatar_completed)
    mock_pubsub.publish.assert_not_called()


@pytest.mark.asyncio
async def test_avatar_job_cost_gate_blocks():
    """
    Dado: custo acumulado próximo do teto (total_real=95.0, estimativa=10.0, limite=100.0)
    Quando: AvatarJob.run() é executado
    Então:
      - check_cost_gate retorna False
      - stages.avatar.status = "error" com error_type="permanent"
      - HeyGen NÃO é chamado
    """
    mock_firestore = AsyncMock()
    mock_firestore.get_project = AsyncMock(return_value={
        "stages": {"avatar": {"status": "pending"}},
        "cost_breakdown": {"total_real": 95.0},
    })
    mock_firestore.get_pipeline_config = AsyncMock(return_value={
        "cost_limit": 100.0,
        "exchange_rate_usd_brl": 5.50,
    })
    mock_firestore.update_stage  = AsyncMock()
    mock_firestore.update_project = AsyncMock()

    job = AvatarJob(
        firestore=mock_firestore,
        pubsub=MagicMock(),
        heygen_api_key="key",
        gcs_bucket="bucket",
        callback_url="https://callback.run.app",
    )

    with patch.object(job, "_upload_to_heygen_assets") as mock_upload, \
         pytest.raises(Exception):  # CostGateBlockedError
        msg = TtsCompletedMsg(
            project_id="proj-blocked",
            audio_paths={"horizontal": ["gs://b/h.mp3"], "vertical": ["gs://b/v.mp3"]},
            total_cost_usd=0.1,
            segment_count=2,
        )
        await job.run(msg)

    mock_upload.assert_not_called()
    final_update = mock_firestore.update_stage.call_args_list[-1][0][2]
    assert final_update["status"] == "error"
    assert final_update["error_type"] == "permanent"
```

---

## Dependências

| Dependência | Versão | Uso |
|---|---|---|
| `pydub` | `0.25.1` | Concatenação de MP3s |
| `requests` | `2.31.0` | HTTP para HeyGen API |
| `google-cloud-storage` | `2.14.0` | Download MP3s do GCS |
| `firebase-admin` | `6.4.0` | Firestore via ADC |
| `ffmpeg` | sistema | Backend do pydub para export MP3 |

**Secrets no Secret Manager:**
- `heygen-api-key` — chave da API HeyGen

**Environment Variables:**
- `GCP_PROJECT_ID`, `GCS_BUCKET`, `TENANT_ID`
- `HEYGEN_CALLBACK_URL` — URL pública do heygen-callback Cloud Run Service
