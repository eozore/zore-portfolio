# API Interface & WebSocket Events — Video Editor API

> Referência: requirements.md (FR-01), business-rules.md (BR-16)
> Nota: Este projeto é backend-only (API). O frontend é um workstream separado.
> Este artefato documenta a interface que o frontend consumirá.

## REST API Endpoints

### POST /api/projects

Cria um novo projeto de edição. Upload dos arquivos.

**Request:** `multipart/form-data`
```
videoFile: File (MP4, max 2GB)
htmlFile: File (HTML, max 10MB)
```

**Response:** `201 Created`
```json
{
  "project_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "created",
  "ws_url": "ws://host/ws/projects/a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**Errors:**
- `400` — Arquivo faltando, tipo inválido, ou excede limites
- `429` — Fila cheia (max concurrent jobs atingido)
- `500` — Erro interno

---

### GET /api/projects/:id

Consulta estado de um projeto.

**Response:** `200 OK`
```json
{
  "id": "a1b2c3d4-...",
  "status": "composing_horizontal",
  "created_at": "2026-07-08T15:30:00Z",
  "progress": {
    "current_step": "compose_horizontal",
    "percent": 65,
    "message": "Montando vídeo horizontal com FFmpeg...",
    "steps_completed": ["upload", "stt", "slide_export", "alignment"]
  },
  "input": {
    "video_duration_sec": 1200,
    "total_slides": 12
  },
  "outputs": null,
  "error": null
}
```

---

### GET /api/projects/:id/download/:format

Download do vídeo final. `format` = `horizontal` | `vertical`

**Response:** `200 OK` (stream do arquivo MP4) ou redirect para GCS signed URL

**Errors:**
- `404` — Projeto não encontrado ou output não existe
- `410` — Output expirado

---

### POST /api/projects/:id/retry

Re-executa o pipeline a partir do step que falhou (usa cache dos steps anteriores).

**Response:** `202 Accepted`
```json
{
  "project_id": "a1b2c3d4-...",
  "status": "transcribing",
  "retry_from": "stt"
}
```

---

### GET /api/projects

Lista projetos (últimos 7 dias).

**Query params:** `?status=completed&limit=20`

**Response:** `200 OK`
```json
{
  "projects": [...],
  "total": 42
}
```

---

### DELETE /api/projects/:id

Remove projeto e todos os artefatos associados.

**Response:** `204 No Content`

---

## WebSocket Interface

### Connection

```
ws://host/ws/projects/:id
```

O client conecta após criar o projeto. O server envia eventos de progresso em tempo real.

### Event Schema

Todos os eventos seguem o formato:

```json
{
  "event": "EVENT_NAME",
  "data": { ... },
  "timestamp": "2026-07-08T15:30:00Z"
}
```

### Events

#### STEP_STARTED
```json
{
  "event": "STEP_STARTED",
  "data": {
    "step": "stt",
    "message": "Iniciando transcrição com GCP Speech-to-Text..."
  }
}
```

#### STEP_PROGRESS
```json
{
  "event": "STEP_PROGRESS",
  "data": {
    "step": "slide_export",
    "percent": 45,
    "message": "Exportando slide 5/12..."
  }
}
```

#### STEP_COMPLETED
```json
{
  "event": "STEP_COMPLETED",
  "data": {
    "step": "alignment",
    "message": "Alinhamento concluído. 10 slides mapeados."
  }
}
```

#### PROJECT_COMPLETED
```json
{
  "event": "PROJECT_COMPLETED",
  "data": {
    "outputs": {
      "horizontal_url": "/api/projects/a1b2c3d4/download/horizontal",
      "vertical_url": "/api/projects/a1b2c3d4/download/vertical"
    },
    "duration_sec": 845,
    "message": "Edição concluída! 2 vídeos prontos para download."
  }
}
```

#### PROJECT_FAILED
```json
{
  "event": "PROJECT_FAILED",
  "data": {
    "step": "alignment",
    "message": "Gemini retornou JSON inválido após 2 tentativas.",
    "retryable": true
  }
}
```

#### HEARTBEAT
```json
{
  "event": "HEARTBEAT",
  "data": {
    "step": "compose_horizontal",
    "message": "⏳ Processando... (codificando vídeo)"
  }
}
```
Enviado a cada 15s durante steps longos para evitar timeout do client.

## Tech Stack Recomendada

| Camada | Tecnologia | Justificativa |
|--------|-----------|---------------|
| API Server | **FastAPI** (Python) | Async nativo, WebSocket built-in, tipagem forte, ecossistema GCP |
| WebSocket | FastAPI WebSocket | Integrado, sem dependência extra |
| Task Queue | **asyncio + semaphore** (v1) | Simples para 3 concurrent jobs. Escalar para Cloud Tasks se necessário |
| Storage | **Google Cloud Storage** | Já em uso, signed URLs, lifecycle policies |
| State | **Firestore** (prod) / JSON local (dev) | Já no projeto, real-time listeners |
| STT | **GCP Speech-to-Text** | Já em uso, qualidade boa para pt-BR |
| LLM | **Gemini 2.5 Flash** via Vertex AI | Já em uso, rápido, barato |
| Video | **FFmpeg** (subprocess) | Padrão da indústria, já em uso |
| Slide Render | **Playwright** (Python) | Já em uso, headless Chromium |
| Container | **Docker** → **Cloud Run** | Já tem Dockerfile, auto-scale |

## File Structure Proposta (Refactored)

```
tool-videoyoutube/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app + WebSocket
│   ├── config.py            # Env vars, settings
│   ├── models/
│   │   ├── project.py       # Project, ProjectStatus, etc.
│   │   └── pipeline.py      # TranscriptResult, AlignmentResult, etc.
│   ├── modules/
│   │   ├── stt.py           # ISttModule implementation
│   │   ├── slide_export.py  # ISlideExportModule implementation
│   │   ├── alignment.py     # IAlignmentModule implementation
│   │   ├── compose.py       # IComposeModule implementation
│   │   ├── jump_cuts.py     # IJumpCutsModule implementation
│   │   └── storage.py       # IStorageModule implementation
│   ├── services/
│   │   ├── pipeline.py      # Orchestrator (runs modules in sequence)
│   │   └── project_repo.py  # IProjectRepository (Firestore/local)
│   ├── api/
│   │   ├── routes.py        # REST endpoints
│   │   └── websocket.py     # WebSocket handler
│   └── utils/
│       ├── ffmpeg.py        # FFmpeg helpers (probe, has_audio, etc.)
│       └── html_parser.py   # BeautifulSoup slide extraction
├── tests/
│   ├── test_stt.py
│   ├── test_alignment.py
│   └── ...
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pyproject.toml
└── README.md
```
