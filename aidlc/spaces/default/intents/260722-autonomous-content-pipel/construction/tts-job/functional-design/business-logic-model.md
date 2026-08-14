# Business Logic Model — U-08: tts-job

> Referências: [unit-of-work.md](../../../inception/units-generation/unit-of-work.md) | [requirements.md](../../../inception/requirements-analysis/requirements.md) | [components.md](../../../inception/application-design/components.md) | [component-methods.md](../../../inception/application-design/component-methods.md) | [services.md](../../../inception/application-design/services.md) | [unit-of-work-story-map.md](../../../inception/units-generation/unit-of-work-story-map.md)

---

## Visão Geral

`TTSJob` é um Cloud Run Job Python que processa Text-to-Speech via ElevenLabs Flash v2.5 para todos os segmentos de áudio do manifesto. Segmentos de slide puro (`segment.script == ""`) são ignorados completamente — não geram custo nem arquivo de áudio.

**Path no monorepo:** `agents/pipeline/tts_job/`
**Entry point:** `python -m tts_job` (ou `CMD ["python", "-m", "tts_job"]`)
**Trigger:** Mensagem Pub/Sub `content-pipeline.package-approved`
**Timeout:** 1800s (30 min)
**Memory:** 512 MB

---

## Fluxo de Execução

```
[Pub/Sub: package_approved]
        │
        ▼
1. Parseia mensagem → extrai project_id, manifest_gcs_path, cost_limit
        │
        ▼
2. Idempotência: verifica stages.tts.status no Firestore
   → se "completed": loga e retorna (sem reprocessamento)
        │
        ▼
3. Atualiza stages.tts.status = "running" no Firestore
        │
        ▼
4. Carrega manifesto HTML do GCS
        │
        ▼
5. Extrai segmentos (filtra: script != "")
   → segmentos slide puro (script == "") são IGNORADOS
        │
        ▼
6. Para CADA segmento de áudio (horizontal e vertical):
   a. Verifica cost gate (estimate_tts_cost)
   b. POST ElevenLabs /v1/text-to-speech/{voice_id}
      com with_retry(max=3, backoff=[1,4,16], transient=[429,503])
   c. Salva MP3 no GCS: gs://{bucket}/projects/{id}/audio/{target}/{segment_id}.mp3
   d. Registra custo via update_actual_cost
        │
        ▼
7. Atualiza stages.tts.status = "completed" no Firestore
        │
        ▼
8. Publica tts_completed no Pub/Sub com audio_paths + segment_count
```

---

## Especificação Detalhada

### Entry Point

```python
# agents/pipeline/tts_job/__main__.py

import asyncio
import base64
import json
import logging
import os
import sys

from shared.firestore_client import FirestoreClient
from shared.pubsub_client import PubSubClient, get_secret
from shared.models import PackageApprovedMsg, TtsCompletedMsg
from tts_job.job import TTSJob

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

GCP_PROJECT_ID = os.environ["GCP_PROJECT_ID"]
GCS_BUCKET     = os.environ["GCS_BUCKET"]
TENANT_ID      = os.environ.get("TENANT_ID", "default")


async def main() -> None:
    """
    Entry point do Cloud Run Job.

    Lê mensagem Pub/Sub do ambiente (PUBSUB_MESSAGE env var injetada pelo trigger)
    ou de stdin (para testes locais com gcloud pubsub).
    """
    raw = os.environ.get("PUBSUB_MESSAGE") or sys.stdin.read()
    if not raw:
        raise ValueError("Nenhuma mensagem Pub/Sub encontrada (PUBSUB_MESSAGE ou stdin)")

    envelope = json.loads(raw)
    data = base64.b64decode(envelope["message"]["data"]).decode("utf-8")
    msg_dict = json.loads(data)
    msg = PackageApprovedMsg(**msg_dict)

    elevenlabs_key = get_secret("elevenlabs-api-key", GCP_PROJECT_ID)
    voice_id       = get_secret("elevenlabs-voice-id", GCP_PROJECT_ID)

    firestore = FirestoreClient(GCP_PROJECT_ID)
    pubsub    = PubSubClient(GCP_PROJECT_ID)

    job = TTSJob(
        firestore=firestore,
        pubsub=pubsub,
        elevenlabs_api_key=elevenlabs_key,
        voice_id=voice_id,
        gcs_bucket=GCS_BUCKET,
        tenant_id=TENANT_ID,
    )
    await job.run(msg)


if __name__ == "__main__":
    asyncio.run(main())
```

### Classe `TTSJob`

```python
# agents/pipeline/tts_job/job.py

import asyncio
import logging
import time
from typing import Literal

import requests
from google.cloud import storage

from shared.firestore_client import FirestoreClient
from shared.pubsub_client import PubSubClient
from shared.retry import with_retry, ApiError
from shared.cost_tracker import CostTrackerService
from shared.models import (
    Manifest, Segment, PackageApprovedMsg, TtsCompletedMsg
)

logger = logging.getLogger(__name__)

ELEVENLABS_BASE_URL = "https://api.elevenlabs.io"
TTS_TOPICS = {
    "tts_completed": "content-pipeline.tts-completed",
}


class TTSJob:
    def __init__(
        self,
        firestore: FirestoreClient,
        pubsub: PubSubClient,
        elevenlabs_api_key: str,
        voice_id: str,
        gcs_bucket: str,
        tenant_id: str = "default",
    ):
        self.firestore  = firestore
        self.pubsub     = pubsub
        self.api_key    = elevenlabs_api_key
        self.voice_id   = voice_id
        self.gcs_bucket = gcs_bucket
        self.cost       = CostTrackerService(firestore, tenant_id)
        self.gcs        = storage.Client()

    async def run(self, msg: PackageApprovedMsg) -> None:
        project_id = msg.project_id

        # ── Idempotência ──────────────────────────────────────────────────────
        project = await self.firestore.get_project(project_id)
        if project["stages"]["tts"]["status"] == "completed":
            logger.info(f"[TTSJob] TTS já concluído para {project_id}. Ignorando.")
            return

        await self.firestore.update_stage(project_id, "tts", {
            "status": "running",
            "started_at": int(time.time()),
        })

        try:
            manifest = await self._load_manifest(msg.manifest_gcs_path)
            audio_paths = await self._process_all_targets(project_id, manifest, msg.cost_limit)

            segment_count = sum(len(paths) for paths in audio_paths.values())
            total_cost_usd = self._calculate_total_cost_usd(manifest)

            await self.firestore.update_stage(project_id, "tts", {
                "status": "completed",
                "completed_at": int(time.time()),
                "cost_real": total_cost_usd,
            })

            completed_msg = TtsCompletedMsg(
                project_id=project_id,
                audio_paths=audio_paths,
                total_cost_usd=total_cost_usd,
                segment_count=segment_count,
            )
            self.pubsub.publish(TTS_TOPICS["tts_completed"], completed_msg)
            logger.info(f"[TTSJob] Concluído: {segment_count} segmentos, projeto={project_id}")

        except Exception as e:
            await self.firestore.update_stage(project_id, "tts", {
                "status": "error",
                "error_message": str(e),
                "error_type": "permanent" if isinstance(e, ApiError) and e.status_code in (401, 403) else "transient",
            })
            raise

    async def _load_manifest(self, gcs_path: str) -> Manifest:
        """Lê manifesto HTML do GCS e parseia para dataclass Manifest."""
        bucket_name, blob_path = gcs_path.replace("gs://", "").split("/", 1)
        bucket = self.gcs.bucket(bucket_name)
        blob   = bucket.blob(blob_path)
        content = blob.download_as_text()
        return _parse_manifest(content)

    async def _process_all_targets(
        self,
        project_id: str,
        manifest: Manifest,
        cost_limit: float,
    ) -> dict[str, list[str]]:
        """
        Processa TTS para todos os targets (horizontal + vertical).

        CRÍTICO: Filtra apenas segmentos com script != "".
        Segmentos de slide puro (script == "") são completamente ignorados.
        """
        audio_paths: dict[str, list[str]] = {"horizontal": [], "vertical": []}

        for target in ("horizontal", "vertical"):
            segments = manifest.get_avatar_segments(target)  # já filtra script != ""
            logger.info(
                f"[TTSJob] target={target}: {len(segments)} segmentos de áudio "
                f"(segmentos de slide puro ignorados)"
            )

            for segment in segments:
                gcs_path = await self._process_segment(project_id, segment, target, cost_limit)
                audio_paths[target].append(gcs_path)

        return audio_paths

    async def _process_segment(
        self,
        project_id: str,
        segment: Segment,
        target: Literal["horizontal", "vertical"],
        cost_limit: float,
    ) -> str:
        """Processa um segmento individual: cost gate → TTS → GCS upload."""
        # Verifica cost gate
        config = await self.firestore.get_pipeline_config("default")
        limit = cost_limit or config.get("cost_limit", 100.0)
        estimated = await self.cost.estimate_tts_cost(len(segment.script))
        can_proceed = await self.cost.check_cost_gate(project_id, estimated, limit)
        if not can_proceed:
            raise CostLimitExceededError(
                f"Custo excede teto para segment={segment.id} project={project_id}"
            )

        # Chama ElevenLabs com retry
        audio_bytes = await with_retry(
            lambda: self._call_elevenlabs(segment.script),
            max_retries=3,
            backoff=[1.0, 4.0, 16.0],
            transient_errors=(429, 503),
            project_id=project_id,
            stage_id="tts",
            firestore=self.firestore,
        )

        # Salva no GCS
        gcs_path = f"gs://{self.gcs_bucket}/projects/{project_id}/audio/{target}/{segment.id}.mp3"
        await self._upload_to_gcs(audio_bytes, gcs_path)

        # Registra custo real
        chars = len(segment.script)
        cost_usd = chars * 0.00005
        await self.cost.update_actual_cost(project_id, "tts", cost_usd)

        return gcs_path

    async def _call_elevenlabs(self, text: str) -> bytes:
        """
        POST /v1/text-to-speech/{voice_id}

        Parâmetros fixos:
          model_id:      "eleven_flash_v2_5"
          output_format: "mp3_44100_128"
          voice_settings: {stability: 0.5, similarity_boost: 0.75}

        Raises:
            ApiError: com status HTTP para classificação pelo retry
        """
        url = f"{ELEVENLABS_BASE_URL}/v1/text-to-speech/{self.voice_id}"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": "eleven_flash_v2_5",
            "output_format": "mp3_44100_128",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }

        # requests é síncrono — executado em thread pool para não bloquear event loop
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.post(url, json=payload, headers=headers, timeout=60)
        )

        if response.status_code != 200:
            raise ApiError(response.status_code, response.text)

        return response.content  # bytes MP3

    async def _upload_to_gcs(self, audio_bytes: bytes, gcs_uri: str) -> None:
        """Upload de bytes MP3 para GCS."""
        bucket_name, blob_path = gcs_uri.replace("gs://", "").split("/", 1)
        bucket = self.gcs.bucket(bucket_name)
        blob   = bucket.blob(blob_path)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: blob.upload_from_string(audio_bytes, content_type="audio/mpeg")
        )
        logger.debug(f"[TTSJob] Uploaded: {gcs_uri}")

    def _calculate_total_cost_usd(self, manifest: Manifest) -> float:
        """Calcula custo total USD com base nos caracteres de todos os segmentos."""
        total_chars = 0
        for target in ("horizontal", "vertical"):
            for seg in manifest.get_avatar_segments(target):
                total_chars += len(seg.script)
        return round(total_chars * 0.00005, 6)


class CostLimitExceededError(Exception):
    pass


def _parse_manifest(html_content: str) -> Manifest:
    """Parseia manifesto HTML para dataclass Manifest."""
    # Implementação: extrai <script type="application/json"> do HTML
    # e desserializa para Manifest
    import re
    import json as json_lib
    pattern = r'<script[^>]+type=["\']application/json["\'][^>]*>(.*?)</script>'
    match = re.search(pattern, html_content, re.DOTALL)
    if not match:
        raise ManifestParseError("JSON block não encontrado no manifesto HTML")
    data = json_lib.loads(match.group(1))
    return Manifest(**data)


class ManifestParseError(Exception):
    pass
```

---

## GCS Path Convention

| Target | Segmento | Path GCS |
|---|---|---|
| horizontal | `yt-01` | `gs://{bucket}/projects/{project_id}/audio/horizontal/yt-01.mp3` |
| horizontal | `yt-02` | `gs://{bucket}/projects/{project_id}/audio/horizontal/yt-02.mp3` |
| vertical | `r1-01` | `gs://{bucket}/projects/{project_id}/audio/vertical/r1-01.mp3` |

---

## Campos Firestore Atualizados

**`content_projects/{project_id}/stages/tts`** ao longo da execução:

| Momento | Campos atualizados |
|---|---|
| Início | `status="running"`, `started_at=unix_ts` |
| Erro transitório (retry) | `status="retrying"`, `retry_count=N` |
| Erro permanente | `status="error"`, `error_message`, `error_type` |
| Sucesso | `status="completed"`, `completed_at=unix_ts`, `cost_real=usd_total` |

---

## Mensagem Pub/Sub Publicada

**Tópico:** `content-pipeline.tts-completed`

```json
{
  "project_id": "proj-abc123",
  "audio_paths": {
    "horizontal": [
      "gs://bucket/projects/proj-abc123/audio/horizontal/yt-01.mp3",
      "gs://bucket/projects/proj-abc123/audio/horizontal/yt-02.mp3",
      "gs://bucket/projects/proj-abc123/audio/horizontal/yt-03.mp3"
    ],
    "vertical": [
      "gs://bucket/projects/proj-abc123/audio/vertical/r1-01.mp3"
    ]
  },
  "total_cost_usd": 0.000125,
  "segment_count": 4
}
```

---

## Testes Nyquist — U-08

### NT-1: Happy path — 3 segmentos com script + 1 slide puro ignorado

```python
# tests/test_tts_job.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from shared.models import PackageApprovedMsg, Manifest, Segment
from tts_job.job import TTSJob

FAKE_MP3 = b"\xff\xfb\x90\x00" * 100  # bytes válidos de header MP3

def make_manifest_with_mixed_segments():
    """
    Manifesto com 3 segmentos com script e 1 segmento slide puro (script="").
    Apenas 3 devem gerar MP3.
    """
    manifest = MagicMock(spec=Manifest)
    seg1 = Segment(id="yt-01", script="Olá mundo", slide=0, beat="intro", min_duration_s=4.5, pause_after_s=0.4)
    seg2 = Segment(id="yt-02", script="Segundo segmento", slide=1, beat="body", min_duration_s=4.5, pause_after_s=0.4)
    seg3 = Segment(id="yt-03", script="Terceiro segmento", slide=2, beat="outro", min_duration_s=4.5, pause_after_s=0.4)
    seg4 = Segment(id="yt-04", script="", slide=3, beat="slide-only", min_duration_s=4.5, pause_after_s=0.0)

    # get_avatar_segments retorna APENAS segmentos com script != ""
    manifest.get_avatar_segments.side_effect = lambda target: (
        [seg1, seg2, seg3] if target == "horizontal" else []
    )
    return manifest


@pytest.mark.asyncio
async def test_tts_job_processes_3_segments_ignores_slide_pure():
    """
    Dado: manifesto com 3 segmentos com script e 1 slide puro
    Quando: TTSJob.run() é executado
    Então:
      - 3 arquivos MP3 são salvos no GCS
      - 1 segmento slide puro é ignorado (nenhuma chamada ElevenLabs para ele)
      - tts_completed publicado com segment_count=3
      - stages.tts.status = "completed" no Firestore
    """
    mock_firestore = AsyncMock()
    mock_firestore.get_project = AsyncMock(return_value={
        "stages": {"tts": {"status": "pending"}},
        "cost_breakdown": {"total_real": 0.0}
    })
    mock_firestore.get_pipeline_config = AsyncMock(return_value={
        "cost_limit": 100.0,
        "exchange_rate_usd_brl": 5.50,
    })
    mock_firestore.update_stage  = AsyncMock()
    mock_firestore.update_project = AsyncMock()

    mock_pubsub = MagicMock()
    mock_pubsub.publish = MagicMock()

    elevenlabs_call_count = 0

    job = TTSJob(
        firestore=mock_firestore,
        pubsub=mock_pubsub,
        elevenlabs_api_key="test-key",
        voice_id="voice-123",
        gcs_bucket="test-bucket",
    )

    manifest = make_manifest_with_mixed_segments()

    with patch.object(job, "_load_manifest", return_value=manifest), \
         patch.object(job, "_call_elevenlabs", return_value=FAKE_MP3) as mock_el, \
         patch.object(job, "_upload_to_gcs", return_value=None) as mock_gcs:

        msg = PackageApprovedMsg(
            project_id="proj-123",
            manifest_gcs_path="gs://bucket/projects/proj-123/manifest.html",
            channels_approved=["youtube"],
            approved_at="2025-01-01T00:00:00Z",
            cost_limit=100.0,
        )
        await job.run(msg)

    # ElevenLabs chamado exatamente 3 vezes (3 segmentos com script)
    assert mock_el.call_count == 3

    # GCS upload feito 3 vezes
    assert mock_gcs.call_count == 3

    # Pub/Sub publicou tts_completed
    mock_pubsub.publish.assert_called_once()
    published_msg = mock_pubsub.publish.call_args[0][1]
    assert published_msg.segment_count == 3
    assert len(published_msg.audio_paths["horizontal"]) == 3

    # Firestore stages.tts.status = "completed"
    status_calls = [
        call[0][2]
        for call in mock_firestore.update_stage.call_args_list
        if call[0][1] == "tts"
    ]
    final_status = status_calls[-1]
    assert final_status["status"] == "completed"


@pytest.mark.asyncio
async def test_tts_job_idempotent_when_already_completed():
    """
    Dado: stages.tts.status já é "completed"
    Quando: TTSJob.run() é chamado
    Então: retorna sem chamar ElevenLabs nem publicar Pub/Sub
    """
    mock_firestore = AsyncMock()
    mock_firestore.get_project = AsyncMock(return_value={
        "stages": {"tts": {"status": "completed"}},
    })
    mock_pubsub = MagicMock()

    job = TTSJob(
        firestore=mock_firestore, pubsub=mock_pubsub,
        elevenlabs_api_key="key", voice_id="voice", gcs_bucket="bucket",
    )

    with patch.object(job, "_call_elevenlabs") as mock_el:
        msg = PackageApprovedMsg(
            project_id="proj-dup", manifest_gcs_path="gs://b/m.html",
            channels_approved=["youtube"], approved_at="2025-01-01T00:00:00Z",
            cost_limit=100.0,
        )
        await job.run(msg)

    mock_el.assert_not_called()
    mock_pubsub.publish.assert_not_called()
```

---

## Dependências

| Dependência | Versão | Uso |
|---|---|---|
| `requests` | `2.31.0` | HTTP para ElevenLabs API |
| `google-cloud-storage` | `2.14.0` | Upload/download GCS |
| `firebase-admin` | `6.4.0` | Firestore via ADC |
| `google-cloud-pubsub` | `2.21.0` | Pub/Sub |
| `google-cloud-secret-manager` | `2.18.0` | API keys |
| `shared` (internal) | — | retry, cost_tracker, firestore_client, pubsub_client |

**Secrets no Secret Manager:**
- `elevenlabs-api-key` — chave da API ElevenLabs
- `elevenlabs-voice-id` — ID da voz (ex: "pNInz6obpgDQGcFmaJgB")

**Environment Variables:**
- `GCP_PROJECT_ID` — ID do projeto GCP
- `GCS_BUCKET` — nome do bucket GCS
- `TENANT_ID` — tenant da pipeline (default: "default")
- `PUBSUB_MESSAGE` — mensagem Pub/Sub serializada (injetada pelo trigger)
