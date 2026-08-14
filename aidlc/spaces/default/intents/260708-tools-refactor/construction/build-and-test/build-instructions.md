# Build Instructions — Video Editor API

## Prerequisites

- Python 3.11+
- FFmpeg (with libx264)
- Playwright + Chromium

## Local Build

```bash
cd tool-videoyoutube
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## Run (Development)

```bash
python -m app.main
# Server starts at http://localhost:4000
```

## Docker Build

```bash
docker build -t video-editor-api .
docker run -p 4000:4000 -e GOOGLE_CLOUD_PROJECT=ainewz-project video-editor-api
```

## Docker Compose (Full Local)

```bash
docker-compose up --build
```

## Verify Build

```bash
# Syntax check all Python files
python3 -c "import ast, pathlib; [ast.parse(p.read_text()) for p in pathlib.Path('app').rglob('*.py')]"

# Import check
python3 -c "from app.models.project import Project; from app.config import config; print('OK')"

# Health check (after server is running)
curl http://localhost:4000/health
```
