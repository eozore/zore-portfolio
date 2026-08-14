# Services
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Referências: [requirements.md](../requirements-analysis/requirements.md) | [stories.md](../user-stories/stories.md) | [team-practices.md](../practices-discovery/team-practices.md)

---

## Topologia de Serviços GCP

```
+------------------+
| Next.js App      |  Cloud Run Service (sempre online)
| (apps/web)       |  - Serve UI + Route Handlers
| Port 3000        |  - Firebase Admin ADC
+------------------+
         |
         | Firestore writes / Pub/Sub publish
         v
+------------------+
| CMO Agent        |  Cloud Run Service (sempre online)
| (agents/cmo)     |  - FastAPI Python
| Port 8090        |  - Interview, Generate, YouTube, Repurpose
+------------------+

Pub/Sub Topics:
  content-pipeline.package-approved      → TTSJob
  content-pipeline.tts-completed         → AvatarJob
  content-pipeline.avatar-completed      → VideoEditorJob
  content-pipeline.video-ready           → PublisherService
  content-pipeline.heygen-callback       → (internal, HeyGenCallbackHandler)

+------------------+     +------------------+     +------------------+
| TTSJob           | --> | AvatarJob        | --> | VideoEditorJob   |
| Cloud Run Job    |     | Cloud Run Job    |     | Cloud Run Job    |
| Python           |     | Python           |     | Python           |
+------------------+     +------------------+     +------------------+
                                                          |
                                                          v
                                               +------------------+
                                               | PublisherService  |
                                               | Cloud Run Job    |
                                               | (Scheduler mode) |
                                               |                  |
                                               | PublisherService  |
                                               | Cloud Run Service |
                                               | (Immediate mode) |
                                               +------------------+

+------------------+
| HeyGenCallback   |  Cloud Run Service (webhook endpoint)
| Handler          |  - Recebe webhook HeyGen
| Port 8091        |  - Publica no Pub/Sub
+------------------+

+------------------+
| Cloud Scheduler  |  Cron: diário às horários configurados
|                  |  - Chama PublisherService (Job mode)
|                  |  - Seleciona próximo projeto na fila
+------------------+

Infrastructure:
  Firestore: content_projects, pipeline_config, channel_config
  GCS: projects/{id}/audio/, projects/{id}/video/, projects/{id}/manifest.html
  Secret Manager: elevenLabs-api-key, heygen-api-key, youtube-oauth-token, ...
  Artifact Registry: Docker images para os Cloud Run Jobs
```

---

## Serviços por Tipo

### Cloud Run Services (sempre online, respondem a HTTP)

| Serviço | Imagem | Porta | Trigger | Escalabilidade |
|---|---|---|---|---|
| `web` | `gcr.io/{project}/web` | 3000 | HTTP | min: 1, max: 3 |
| `cmo-agent` | `gcr.io/{project}/cmo-agent` | 8090 | HTTP | min: 0, max: 3 |
| `heygen-callback` | `gcr.io/{project}/pipeline` | 8091 | HTTP webhook | min: 0, max: 1 |
| `publisher-immediate` | `gcr.io/{project}/pipeline` | 8092 | HTTP (Publicar Agora) | min: 0, max: 2 |

### Cloud Run Jobs (execução assíncrona, timeout longo)

| Job | Imagem | Timeout | Memory | Trigger |
|---|---|---|---|---|
| `tts-job` | `gcr.io/{project}/pipeline` | 30 min | 512 MB | Pub/Sub |
| `avatar-job` | `gcr.io/{project}/pipeline` | 150 min | 512 MB | Pub/Sub |
| `video-editor-job` | `gcr.io/{project}/pipeline` | 60 min | **4 GB** | Pub/Sub |
| `publisher-scheduled` | `gcr.io/{project}/pipeline` | 30 min | 512 MB | Cloud Scheduler |

**Nota:** Todos os Python Jobs são um único container image `gcr.io/{project}/pipeline` com diferentes `CMD` ou `ENTRYPOINT`. Isso simplifica o build e o deploy.

### Imagem Docker Unificada para Pipeline

```dockerfile
# agents/pipeline/Dockerfile
FROM python:3.12-slim

# Playwright com Chromium para VideoEditorJob
RUN pip install playwright && playwright install chromium --with-deps

# FFmpeg para VideoEditorJob
RUN apt-get install -y ffmpeg

# Dependências Python
COPY requirements.txt .
RUN pip install -r requirements.txt

# Código dos jobs
COPY . /app
WORKDIR /app

# CMD selecionado via Cloud Run Job command override
# Exemplos:
#   CMD ["python", "-m", "tts_job"]
#   CMD ["python", "-m", "avatar_job"]
#   CMD ["python", "-m", "video_editor_job"]
#   CMD ["uvicorn", "heygen_callback:app", "--port", "8091"]
#   CMD ["uvicorn", "publisher_immediate:app", "--port", "8092"]
```

---

## Padrão de Mensagens Pub/Sub

Todas as mensagens usam JSON serializado como `data` (base64 encoded pelo Pub/Sub).

```json
// package_approved (CMO Agent → TTSJob)
{
  "project_id": "string",
  "manifest_gcs_path": "gs://bucket/projects/{id}/manifest.html",
  "channels_approved": ["youtube", "instagram_reel", "linkedin", "threads", "blog"],
  "approved_at": "ISO-8601",
  "cost_limit": 100.0
}

// tts_completed (TTSJob → AvatarJob)
{
  "project_id": "string",
  "audio_paths": {
    "horizontal": ["gs://.../audio/yt-01.mp3", "gs://.../audio/yt-02.mp3"],
    "vertical": ["gs://.../audio/r1-01.mp3"]
  },
  "total_cost_usd": 0.75,
  "segment_count": 12
}

// avatar_completed (HeyGenCallbackHandler → VideoEditorJob)
{
  "project_id": "string",
  "horizontal_video_path": "gs://bucket/projects/{id}/avatar_horizontal.mp4",
  "vertical_video_path": "gs://bucket/projects/{id}/avatar_vertical.mp4",
  "duration_seconds": 912.5,
  "total_cost_usd": 54.00
}

// video_ready (VideoEditorJob → PublisherService)
{
  "project_id": "string",
  "horizontal_final": "gs://bucket/projects/{id}/final_horizontal_cut.mp4",
  "vertical_final": "gs://bucket/projects/{id}/final_vertical_cut.mp4",
  "duration_seconds": 885.0,
  "trigger": "scheduled" | "immediate"
}
```

---

## Padrão de Retry e Resiliência

### Retry em Jobs Python

```python
# shared/retry.py
import asyncio
from typing import Callable, TypeVar

T = TypeVar('T')

async def with_retry(
    fn: Callable,
    max_retries: int = 3,
    backoff_seconds: list[float] = [1.0, 4.0, 16.0],
    transient_errors: tuple[int, ...] = (429, 503),
) -> T:
    for attempt in range(max_retries):
        try:
            return await fn()
        except ApiError as e:
            if e.status_code not in transient_errors:
                raise  # Erro permanente — não re-tenta
            if attempt < max_retries - 1:
                # Atualiza retry_count no Firestore antes de aguardar
                await update_stage_retry_count(attempt + 1)
                await asyncio.sleep(backoff_seconds[attempt])
            else:
                raise  # Esgotou tentativas
```

### Idempotência

Cada job verifica se já foi executado antes de iniciar:

```python
# Verificação de idempotência no início de cada job
project = firestore.get(project_id)
if project['stages']['tts']['status'] == 'completed':
    logger.info(f"TTS already completed for {project_id}. Skipping.")
    return  # Mensagem Pub/Sub processada com sucesso, sem reprocessamento
```

---

## Firestore Collections e Paths

```
content_projects/                       ← coleção principal
  {project_id}/
    (schema base: ver interaction-spec.md seção 5)
    stages:
      avatar:
        lipsync_jobs:                   ← mapeamento lipsync_id→project_id (Finding 1)
          horizontal:
            lipsync_id: string
            status: "pending" | "completed" | "failed"
            video_url: string | null
          vertical:
            lipsync_id: string
            status: "pending" | "completed" | "failed"
            video_url: string | null

pipeline_config/
  {tenantId}/                           ← configuração global da pipeline
    cost_limit: number
    alert_threshold: number
    exchange_rate_usd_brl: number       ← taxa de câmbio configurável (default: 5.50)
    schedule: { seg: null, ter: "18:00", ... }

channel_config/
  {tenantId}/
    {channel_id}/                       ← youtube, instagram_reel, linkedin, etc.
      enabled: boolean
      max_per_day: number
      oauth_token?: { value_secret_name: string, expires_at: Timestamp }
      schedule: string | null           ← sobrescreve schedule global
```

---

## Estratégia de Scheduling

O Cloud Scheduler chama um endpoint do `publisher-scheduled` job uma vez por dia por canal configurado. A lógica de seleção de projeto:

```python
def select_next_project(tenant_id: str, channel: str) -> str | None:
    """Seleciona o projeto mais antigo em awaiting_publication para o canal."""
    projects = firestore.query(
        collection='content_projects',
        where=[
            ('status', '==', 'awaiting_publication'),
            ('channels_approved', 'array_contains', channel),
            (f'publications.{channel}.status', 'not_in', ['published', 'throttled'])
        ],
        order_by='approved_at',
        limit=1
    )
    return projects[0].id if projects else None
```

**Resolução de OQ-07/OQ-08:** Quando o throttler de um canal está no limite, o Publisher Service registra `publications.{channel}.status: "throttled"` e o projeto permanece em `awaiting_publication`. O Scheduler re-seleciona o mesmo projeto no próximo dia para re-tentar o canal throttled.
