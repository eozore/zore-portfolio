# Code Generation Plan — Video Editor API

> Referência: functional-design/, requirements.md

## Architecture

- **Framework**: FastAPI (Python 3.11)
- **Pattern**: Modular pipeline with orchestrator
- **Communication**: REST API + WebSocket (real-time progress)
- **Storage**: JSON-based ProjectRepository (local dev), swap to Firestore (prod)
- **Container**: Docker → Cloud Run

## Files Generated

### Models (`app/models/`)
- `project.py` — Project entity, state machine, status enum
- `pipeline.py` — DTOs (TranscriptResult, AlignmentResult, etc.)

### Modules (`app/modules/`)
- `stt.py` — GCP Speech-to-Text with caching
- `slide_export.py` — Playwright-based HTML slide recording
- `alignment.py` — Gemini LLM alignment (transcript × slides)
- `compose.py` — FFmpeg overlay composition (horizontal + vertical)
- `jump_cuts.py` — Silence removal via transcript analysis
- `storage.py` — GCS upload with signed URLs

### Services (`app/services/`)
- `pipeline.py` — PipelineOrchestrator (runs all modules in sequence)
- `project_repo.py` — Project persistence (JSON files)

### API (`app/api/`)
- `routes.py` — REST endpoints (CRUD + download + retry)
- `websocket.py` — ConnectionManager for real-time events

### Utils (`app/utils/`)
- `ffmpeg.py` — FFprobe/FFmpeg helpers
- `html_parser.py` — BeautifulSoup slide extraction

### Root
- `app/main.py` — FastAPI app + WebSocket endpoint + health check
- `app/config.py` — Environment-based configuration
- `requirements.txt` — All Python dependencies pinned
- `Dockerfile` — Production container (Python 3.11 + FFmpeg + Playwright)
- `docker-compose.yml` — Local dev setup

## Key Improvements Over Legacy

| Aspect | Before | After |
|--------|--------|-------|
| Entry point | `server.js` (Node) + `process_video.py` (Python) | Single FastAPI app |
| Duplicação | `editor_pipeline.py` + `process_video.py` | Eliminada — 1 pipeline |
| Config | Hardcoded (`ainewz-project`, paths fixos) | Env vars via `config.py` |
| Error handling | Crash fatal | Fallbacks + retry por step |
| Output | Apenas horizontal | Horizontal + Vertical |
| Progress | HTTP chunked (frágil) | WebSocket (robust) |
| State | Nenhum | Projeto com memória persistida |
| Dependencies | Imports dinâmicos, pip install inline | `requirements.txt` completo |
