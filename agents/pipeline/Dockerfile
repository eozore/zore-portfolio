# agents/pipeline/Dockerfile
# ============================================================
# Imagem unificada para todos os Cloud Run Jobs e Services
# da content pipeline eozore.
#
# CMD e selecionado via Cloud Run Job/Service command override:
#   tts-job:              python -m tts_job
#   avatar-job:           python -m avatar_job
#   video-editor-job:     python -m video_editor_job
#   vertical-cut-job:     python -m vertical_cut_job
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
        # Fonte das legendas queimadas (shared/captions.py -> libass).
        # A imagem slim nao traz fonte nenhuma: sem isto o libass cai num
        # fallback silencioso, e a legenda sai com outro desenho e outra
        # metrica -- quebra de linha e margens deixam de bater com o que o
        # ASS pediu, sem nenhum erro no log.
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# ── Playwright: instala CLI primeiro, depois deps do SO, depois browsers
# Separado em dois RUN para cache granular e debug mais facil
RUN pip install --no-cache-dir playwright==1.44.0

# playwright install-deps instala as dependencias do SO para o chromium
# sem tentar baixar o browser ainda (evita problemas de rede no build)
RUN playwright install-deps chromium

# Agora baixa o binario do chromium
RUN playwright install chromium

# ── HyperFrames: renderizador deterministico de slide ─────────
#
# Opcional em execucao (RENDERIZADOR_SLIDE=hyperframes), obrigatorio na
# imagem: o job precisa poder cair para o Playwright sem trocar de container.
#
# Node 22+ e requisito do CLI. Vem do nodesource porque o Debian 12 ainda
# empacota o 18.
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g --no-fund --no-audit hyperframes@0.8.17 \
    && npm cache clean --force

# Reusa o Chromium que o Playwright ja baixou, em vez de trazer um segundo
# navegador de ~150 MB para a mesma imagem. Verificado: o seek de
# `animation-delay` sai identico nos dois binarios.
#
# O caminho tem o numero da build do Playwright no meio, entao resolve aqui e
# fixa num link -- descobrir em tempo de execucao falharia DEPOIS de o avatar
# ja ter sido pago.
RUN CHR="$(find /root/.cache/ms-playwright -name chrome -type f -path '*chrome-linux*' | head -n1)" \
    && test -n "$CHR" \
    && mkdir -p /opt/chrome && ln -s "$CHR" /opt/chrome/chrome \
    && /opt/chrome/chrome --version
# Duas variaveis de proposito: `HYPERFRAMES_BROWSER_PATH` e a que o resolver
# do CLI 0.8.x le -- `HYPERFRAMES_CHROME_PATH` aparece no Dockerfile oficial
# deles e e IGNORADA por esta versao. Sem a primeira o CLI tenta baixar um
# chrome-headless-shell em tempo de execucao e falha no Cloud Run, que nao
# tem saida para a internet nem disco gravavel fora de /tmp.
ENV HYPERFRAMES_BROWSER_PATH=/opt/chrome/chrome
ENV HYPERFRAMES_CHROME_PATH=/opt/chrome/chrome

# Conteudo do cliente nao vai para telemetria de terceiro.
ENV HYPERFRAMES_NO_TELEMETRY=1
ENV DO_NOT_TRACK=1

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
