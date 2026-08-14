# Bookworm explícito: é a base validada para as dependências de SO do Chromium
# (mesma escolha de agents/pipeline/Dockerfile).
FROM python:3.11-slim-bookworm

# Dependências de sistema: FFmpeg (video_editor) + curl/ca-certificates
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ── Playwright ────────────────────────────────────────────────────────────────
# html_image_renderer.py importa playwright.async_api para renderizar HTML→PNG
# (thumbnails, posts de imagem, carrosséis). Sem isto o import estoura em runtime
# e todo asset visual falha silenciosamente como "partial error".
# Separado em três RUN para cache granular, igual ao Dockerfile da pipeline.
RUN pip install --no-cache-dir playwright==1.44.0
RUN playwright install-deps chromium
RUN playwright install chromium

WORKDIR /app

# Copy dependencies first to leverage caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Flags de Chromium para Cloud Run (sem /dev/shm real, sem sandbox de kernel)
ENV PLAYWRIGHT_CHROMIUM_ARGS="--disable-dev-shm-usage --no-sandbox --disable-gpu"

EXPOSE 8090

# Run FastAPI app
CMD ["python", "agent.py"]
