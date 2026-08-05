# agents/pipeline/Dockerfile
# ============================================================
# Imagem unificada para todos os Cloud Run Jobs e Services
# da content pipeline eozore.
#
# CMD e selecionado via Cloud Run Job/Service command override:
#   tts-job:              python -m tts_job
#   avatar-job:           python -m avatar_job
#   video-editor-job:     python -m video_editor_job
#   heygen-callback:      uvicorn heygen_callback.app:app --port 8091
#   publisher-immediate:  uvicorn publisher_immediate.app:app --port 8092
#   publisher-scheduled:  python -m publisher_job
# ============================================================

# Bookworm (Debian 12) e mais estavel que Trixie para playwright deps
FROM python:3.12-slim-bookworm

# ── Sistema: FFmpeg + dependencias de sistema ─────────────────
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        libmagic1 \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ── Playwright: instala CLI primeiro, depois deps do SO, depois browsers
# Separado em dois RUN para cache granular e debug mais facil
RUN pip install --no-cache-dir playwright==1.44.0

# playwright install-deps instala as dependencias do SO para o chromium
# sem tentar baixar o browser ainda (evita problemas de rede no build)
RUN playwright install-deps chromium

# Agora baixa o binario do chromium
RUN playwright install chromium

# ── Dependencias Python ───────────────────────────────────────
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# ── Codigo da pipeline ────────────────────────────────────────
COPY . /app
WORKDIR /app

# PYTHONPATH permite imports de 'shared' de qualquer job
ENV PYTHONPATH=/app

# Flags Chromium para Cloud Run (sem /dev/shm real)
ENV PLAYWRIGHT_CHROMIUM_ARGS="--disable-dev-shm-usage --no-sandbox --disable-gpu"

# CMD padrao - sobrescrito por cada Cloud Run Job/Service
CMD ["python", "--version"]
