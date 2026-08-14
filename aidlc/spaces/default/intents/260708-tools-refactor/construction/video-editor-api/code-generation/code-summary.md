# Code Summary — Video Editor API

## What Was Built

Refactor completo da `tool-videoyoutube`: de um protótipo Node.js + Python scripts soltos para uma **API FastAPI modular** com:

- 6 módulos independentes (STT, SlideExport, Alignment, Compose, JumpCuts, Storage)
- Pipeline orchestrator com state machine e progress events
- REST API (6 endpoints) + WebSocket para real-time
- Dual output: horizontal (1920×1080) + vertical (1080×1920, auto-adapted)
- Projeto com memória: cada vídeo é um projeto persistido, cacheável, retry-friendly
- Docker-ready para Cloud Run

## File Count

- **15 Python files** (nova implementação em `app/`)
- **3 config files** (requirements.txt, Dockerfile, docker-compose.yml)
- Legacy files mantidos (podem ser removidos após validação)

## How to Run

```bash
# Local (requer Python 3.11+, FFmpeg, Playwright)
cd tool-videoyoutube
pip install -r requirements.txt
playwright install chromium
python -m app.main

# Docker
docker-compose up --build
```

## API Quick Test

```bash
# Upload e processar
curl -X POST http://localhost:4000/api/projects \
  -F "videoFile=@meu_video.mp4" \
  -F "htmlFile=@meu_deck.html"

# Acompanhar via WebSocket
wscat -c ws://localhost:4000/ws/projects/<project_id>

# Download resultado
curl http://localhost:4000/api/projects/<project_id>/download/horizontal -o horizontal.mp4
curl http://localhost:4000/api/projects/<project_id>/download/vertical -o vertical.mp4
```
