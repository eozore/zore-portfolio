# Business Logic Model — U-13: cloudbuild-pipeline

> Referências: [unit-of-work.md](../../../inception/units-generation/unit-of-work.md) | [requirements.md](../../../inception/requirements-analysis/requirements.md) | [components.md](../../../inception/application-design/components.md) | [component-methods.md](../../../inception/application-design/component-methods.md) | [services.md](../../../inception/application-design/services.md) | [unit-of-work-story-map.md](../../../inception/units-generation/unit-of-work-story-map.md)

---

## Visão Geral

U-13 especifica o Dockerfile unificado da pipeline Python e o `cloudbuild-pipeline.yaml` — pipeline CI/CD separada do web app, responsável por build, push e deploy de todos os Cloud Run Jobs e Services da content pipeline. Nenhuma lógica de negócio aqui; o valor está na correção e completude dos manifests de deploy.

**Separado do** `cloudbuild.yaml` do web app (Next.js) por decisão de isolamento de falha: um deploy quebrado da pipeline não bloqueia o deploy do frontend e vice-versa.

---

## Dockerfile — `agents/pipeline/Dockerfile`

```dockerfile
# agents/pipeline/Dockerfile
# Imagem unificada para todos os Cloud Run Jobs e Services da pipeline.
# CMD é selecionado via Cloud Run Job/Service --command override.

FROM python:3.12-slim

# ── Sistema: FFmpeg + dependências de sistema ─────────────────────────────────
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        libmagic1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# ── Playwright + Chromium (para VideoEditorJob) ───────────────────────────────
# Instalado antes das dependências Python para cache de layer eficiente
RUN pip install --no-cache-dir playwright==1.44.0 \
    && playwright install chromium --with-deps

# ── Dependências Python ───────────────────────────────────────────────────────
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# ── Código da pipeline ────────────────────────────────────────────────────────
COPY . /app
WORKDIR /app

# PYTHONPATH permite imports de 'shared' de qualquer job
ENV PYTHONPATH=/app

# Variáveis de ambiente para Chromium headless no Cloud Run (sem /dev/shm)
ENV PLAYWRIGHT_CHROMIUM_ARGS="--disable-dev-shm-usage --no-sandbox --disable-gpu"

# CMD padrão — sobrescrito por cada Cloud Run Job/Service
CMD ["python", "--version"]
```

---

## `agents/pipeline/requirements.txt`

```
# Web framework (heygen-callback, publisher-immediate)
fastapi==0.111.0
uvicorn[standard]==0.29.0

# HTTP clients
requests==2.31.0
httpx==0.27.0

# GCP clients
google-cloud-pubsub==2.21.0
google-cloud-storage==2.14.0
google-cloud-secret-manager==2.18.0
firebase-admin==6.4.0

# Data validation
pydantic==2.7.0

# Audio processing (avatar-job)
pydub==0.25.1

# HTML/manifest parsing
beautifulsoup4==4.12.3
lxml==5.2.2

# Playwright (video-editor-job) — instalado separadamente no Dockerfile
# playwright==1.44.0  (listado aqui por completude; pip install no Dockerfile acima)

# Utilities
python-multipart==0.0.9
```

---

## `cloudbuild-pipeline.yaml`

```yaml
# cloudbuild-pipeline.yaml
# Pipeline CI/CD separada para os microserviços Python da content pipeline.
# Trigger: push para branch main ou tags v*.*.* em agents/pipeline/**
#
# Variáveis substituídas pelo Cloud Build:
#   $PROJECT_ID      — GCP project ID (automático)
#   $COMMIT_SHA      — hash do commit (automático)
#   $_REGION         — região GCP (substitution var, ex: "us-central1")
#   $_SA_EMAIL       — service account dos jobs (substitution var)
#   $_GCS_BUCKET     — bucket GCS da pipeline (substitution var)
#   $_HEYGEN_CB_URL  — URL do heygen-callback service (substitution var)

substitutions:
  _REGION: us-central1
  _SA_EMAIL: pipeline-jobs-sa@$PROJECT_ID.iam.gserviceaccount.com
  _GCS_BUCKET: $PROJECT_ID-pipeline-media
  _HEYGEN_CB_URL: https://heygen-callback-HASH-uc.a.run.app  # atualizar após primeiro deploy

options:
  logging: CLOUD_LOGGING_ONLY
  machineType: E2_HIGHCPU_8

steps:
  # ── Step 1: Build imagem unificada ──────────────────────────────────────────
  - name: gcr.io/cloud-builders/docker
    id: build
    args:
      - build
      - --tag
      - gcr.io/$PROJECT_ID/pipeline:$COMMIT_SHA
      - --tag
      - gcr.io/$PROJECT_ID/pipeline:latest
      - --cache-from
      - gcr.io/$PROJECT_ID/pipeline:latest
      - --file
      - agents/pipeline/Dockerfile
      - agents/pipeline
    waitFor: ["-"]

  # ── Step 2: Push imagem ──────────────────────────────────────────────────────
  - name: gcr.io/cloud-builders/docker
    id: push
    args:
      - push
      - --all-tags
      - gcr.io/$PROJECT_ID/pipeline
    waitFor: [build]

  # ── Step 3: Deploy heygen-callback (Cloud Run Service) ──────────────────────
  - name: gcr.io/google.com/cloudsdktool/cloud-sdk
    id: deploy-heygen-callback
    entrypoint: gcloud
    args:
      - run
      - deploy
      - heygen-callback
      - --image=gcr.io/$PROJECT_ID/pipeline:$COMMIT_SHA
      - --region=$_REGION
      - --platform=managed
      - --port=8091
      - --command=uvicorn
      - --args=heygen_callback.app:app,--host,0.0.0.0,--port,8091
      - --min-instances=0
      - --max-instances=1
      - --memory=512Mi
      - --cpu=1
      - --timeout=60
      - --service-account=$_SA_EMAIL
      - --no-allow-unauthenticated
      - --set-env-vars=GCP_PROJECT_ID=$PROJECT_ID,GCS_BUCKET=$_GCS_BUCKET,TENANT_ID=default
      - --set-secrets=HEYGEN_CALLBACK_TOKEN_UNUSED=heygen-callback-token:latest
      - --ingress=all
    waitFor: [push]

  # ── Step 4: Deploy publisher-immediate (Cloud Run Service) ──────────────────
  - name: gcr.io/google.com/cloudsdktool/cloud-sdk
    id: deploy-publisher-immediate
    entrypoint: gcloud
    args:
      - run
      - deploy
      - publisher-immediate
      - --image=gcr.io/$PROJECT_ID/pipeline:$COMMIT_SHA
      - --region=$_REGION
      - --platform=managed
      - --port=8092
      - --command=uvicorn
      - --args=publisher_immediate.app:app,--host,0.0.0.0,--port,8092
      - --min-instances=0
      - --max-instances=2
      - --memory=512Mi
      - --cpu=1
      - --timeout=300
      - --service-account=$_SA_EMAIL
      - --no-allow-unauthenticated
      - --set-env-vars=GCP_PROJECT_ID=$PROJECT_ID,GCS_BUCKET=$_GCS_BUCKET,TENANT_ID=default
      - --set-secrets=ELEVENLABS_API_KEY_UNUSED=elevenlabs-api-key:latest,HEYGEN_API_KEY_UNUSED=heygen-api-key:latest
    waitFor: [push]

  # ── Step 5: Update tts-job (Cloud Run Job) ───────────────────────────────────
  - name: gcr.io/google.com/cloudsdktool/cloud-sdk
    id: deploy-tts-job
    entrypoint: gcloud
    args:
      - run
      - jobs
      - update
      - tts-job
      - --image=gcr.io/$PROJECT_ID/pipeline:$COMMIT_SHA
      - --region=$_REGION
      - --command=python
      - --args=-m,tts_job
      - --memory=512Mi
      - --cpu=1
      - --task-timeout=1800s
      - --max-retries=0
      - --service-account=$_SA_EMAIL
      - --set-env-vars=GCP_PROJECT_ID=$PROJECT_ID,GCS_BUCKET=$_GCS_BUCKET,TENANT_ID=default
      - --set-secrets=ELEVENLABS_API_KEY=elevenlabs-api-key:latest,ELEVENLABS_VOICE_ID=elevenlabs-voice-id:latest
    waitFor: [push]

  # ── Step 6: Update avatar-job (Cloud Run Job) ────────────────────────────────
  - name: gcr.io/google.com/cloudsdktool/cloud-sdk
    id: deploy-avatar-job
    entrypoint: gcloud
    args:
      - run
      - jobs
      - update
      - avatar-job
      - --image=gcr.io/$PROJECT_ID/pipeline:$COMMIT_SHA
      - --region=$_REGION
      - --command=python
      - --args=-m,avatar_job
      - --memory=512Mi
      - --cpu=1
      - --task-timeout=9000s
      - --max-retries=0
      - --service-account=$_SA_EMAIL
      - --set-env-vars=GCP_PROJECT_ID=$PROJECT_ID,GCS_BUCKET=$_GCS_BUCKET,TENANT_ID=default,HEYGEN_CALLBACK_URL=$_HEYGEN_CB_URL
      - --set-secrets=HEYGEN_API_KEY=heygen-api-key:latest
    waitFor: [push]

  # ── Step 7: Update video-editor-job (Cloud Run Job — 4 GB) ──────────────────
  - name: gcr.io/google.com/cloudsdktool/cloud-sdk
    id: deploy-video-editor-job
    entrypoint: gcloud
    args:
      - run
      - jobs
      - update
      - video-editor-job
      - --image=gcr.io/$PROJECT_ID/pipeline:$COMMIT_SHA
      - --region=$_REGION
      - --command=python
      - --args=-m,video_editor_job
      - --memory=4Gi
      - --cpu=4
      - --task-timeout=3600s
      - --max-retries=0
      - --service-account=$_SA_EMAIL
      - --set-env-vars=GCP_PROJECT_ID=$PROJECT_ID,GCS_BUCKET=$_GCS_BUCKET,TENANT_ID=default,PLAYWRIGHT_CHROMIUM_ARGS=--disable-dev-shm-usage --no-sandbox --disable-gpu
    waitFor: [push]

  # ── Step 8: Update publisher-scheduled (Cloud Run Job) ──────────────────────
  - name: gcr.io/google.com/cloudsdktool/cloud-sdk
    id: deploy-publisher-scheduled
    entrypoint: gcloud
    args:
      - run
      - jobs
      - update
      - publisher-scheduled
      - --image=gcr.io/$PROJECT_ID/pipeline:$COMMIT_SHA
      - --region=$_REGION
      - --command=python
      - --args=-m,publisher_job
      - --memory=512Mi
      - --cpu=1
      - --task-timeout=1800s
      - --max-retries=0
      - --service-account=$_SA_EMAIL
      - --set-env-vars=GCP_PROJECT_ID=$PROJECT_ID,GCS_BUCKET=$_GCS_BUCKET,TENANT_ID=default
      - --set-secrets=YOUTUBE_OAUTH_TOKEN=youtube-oauth-token:latest,HEYGEN_API_KEY=heygen-api-key:latest
    waitFor: [push]

images:
  - gcr.io/$PROJECT_ID/pipeline:$COMMIT_SHA
  - gcr.io/$PROJECT_ID/pipeline:latest
```

---

## Comandos de Setup Inicial (one-time)

Os Cloud Run Jobs devem ser **criados** antes do primeiro deploy via `cloudbuild-pipeline.yaml`. Após criação, o YAML usa `update` em vez de `create`.

```bash
# ── Criar Cloud Run Jobs (executar UMA vez no setup do projeto) ──────────────

export PROJECT_ID=eozore-prod
export REGION=us-central1
export SA_EMAIL=pipeline-jobs-sa@${PROJECT_ID}.iam.gserviceaccount.com
export GCS_BUCKET=${PROJECT_ID}-pipeline-media
export IMAGE=gcr.io/${PROJECT_ID}/pipeline:latest

# tts-job
gcloud run jobs create tts-job \
  --image="${IMAGE}" \
  --region="${REGION}" \
  --command=python \
  --args="-m,tts_job" \
  --memory=512Mi \
  --cpu=1 \
  --task-timeout=1800s \
  --max-retries=0 \
  --service-account="${SA_EMAIL}" \
  --set-env-vars="GCP_PROJECT_ID=${PROJECT_ID},GCS_BUCKET=${GCS_BUCKET},TENANT_ID=default" \
  --set-secrets="ELEVENLABS_API_KEY=elevenlabs-api-key:latest,ELEVENLABS_VOICE_ID=elevenlabs-voice-id:latest"

# avatar-job
gcloud run jobs create avatar-job \
  --image="${IMAGE}" \
  --region="${REGION}" \
  --command=python \
  --args="-m,avatar_job" \
  --memory=512Mi \
  --cpu=1 \
  --task-timeout=9000s \
  --max-retries=0 \
  --service-account="${SA_EMAIL}" \
  --set-env-vars="GCP_PROJECT_ID=${PROJECT_ID},GCS_BUCKET=${GCS_BUCKET},TENANT_ID=default,HEYGEN_CALLBACK_URL=https://heygen-callback-HASH-uc.a.run.app" \
  --set-secrets="HEYGEN_API_KEY=heygen-api-key:latest"

# video-editor-job
gcloud run jobs create video-editor-job \
  --image="${IMAGE}" \
  --region="${REGION}" \
  --command=python \
  --args="-m,video_editor_job" \
  --memory=4Gi \
  --cpu=4 \
  --task-timeout=3600s \
  --max-retries=0 \
  --service-account="${SA_EMAIL}" \
  --set-env-vars="GCP_PROJECT_ID=${PROJECT_ID},GCS_BUCKET=${GCS_BUCKET},TENANT_ID=default,PLAYWRIGHT_CHROMIUM_ARGS=--disable-dev-shm-usage --no-sandbox --disable-gpu"

# publisher-scheduled
gcloud run jobs create publisher-scheduled \
  --image="${IMAGE}" \
  --region="${REGION}" \
  --command=python \
  --args="-m,publisher_job" \
  --memory=512Mi \
  --cpu=1 \
  --task-timeout=1800s \
  --max-retries=0 \
  --service-account="${SA_EMAIL}" \
  --set-env-vars="GCP_PROJECT_ID=${PROJECT_ID},GCS_BUCKET=${GCS_BUCKET},TENANT_ID=default" \
  --set-secrets="YOUTUBE_OAUTH_TOKEN=youtube-oauth-token:latest,HEYGEN_API_KEY=heygen-api-key:latest"
```

---

## IAM — Service Account `pipeline-jobs-sa`

```bash
# Criar service account
gcloud iam service-accounts create pipeline-jobs-sa \
  --display-name="Pipeline Jobs Service Account" \
  --project="${PROJECT_ID}"

# Roles necessários
for ROLE in \
  roles/datastore.user \
  roles/storage.objectAdmin \
  roles/pubsub.publisher \
  roles/pubsub.subscriber \
  roles/secretmanager.secretAccessor \
  roles/run.invoker; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${ROLE}"
done
```

---

## Secrets no Secret Manager — Mapeamento Completo

| Secret Name | Usado por | Descrição |
|---|---|---|
| `elevenlabs-api-key` | tts-job, publisher-immediate | Chave API ElevenLabs |
| `elevenlabs-voice-id` | tts-job | ID da voz padrão |
| `heygen-api-key` | avatar-job, publisher-immediate, publisher-scheduled | Chave API HeyGen |
| `heygen-callback-token` | heygen-callback | Token para validar webhooks |
| `youtube-oauth-token` | publisher-scheduled, publisher-immediate | Refresh token YouTube |
| `instagram-access-token` | publisher-scheduled, publisher-immediate | Token Meta Graph API |
| `linkedin-access-token` | publisher-scheduled, publisher-immediate | Token LinkedIn API |
| `threads-access-token` | publisher-scheduled, publisher-immediate | Token Meta Threads |

```bash
# Criar secrets (valores inseridos via console ou gcloud secrets versions add)
for SECRET in \
  elevenlabs-api-key \
  elevenlabs-voice-id \
  heygen-api-key \
  heygen-callback-token \
  youtube-oauth-token \
  instagram-access-token \
  linkedin-access-token \
  threads-access-token; do
  gcloud secrets create "${SECRET}" \
    --replication-policy=automatic \
    --project="${PROJECT_ID}"
done
```

---

## Topologia de Deploy — Diagrama

```
cloudbuild-pipeline.yaml
│
├── Step 1: docker build → gcr.io/$PROJECT_ID/pipeline:$COMMIT_SHA
├── Step 2: docker push  → gcr.io/$PROJECT_ID/pipeline (latest + SHA)
│
├── Step 3 (parallel após push):
│   └── gcloud run deploy heygen-callback     [Service, port=8091, min=0, max=1]
│
├── Step 4 (parallel após push):
│   └── gcloud run deploy publisher-immediate [Service, port=8092, min=0, max=2]
│
├── Step 5 (parallel após push):
│   └── gcloud run jobs update tts-job        [Job, 512Mi, timeout=1800s]
│
├── Step 6 (parallel após push):
│   └── gcloud run jobs update avatar-job     [Job, 512Mi, timeout=9000s]
│
├── Step 7 (parallel após push):
│   └── gcloud run jobs update video-editor-job [Job, 4Gi, timeout=3600s, cpu=4]
│
└── Step 8 (parallel após push):
    └── gcloud run jobs update publisher-scheduled [Job, 512Mi, timeout=1800s]
```

**Steps 3–8 correm em paralelo** após o push (todos têm `waitFor: [push]`), reduzindo o tempo total de deploy.

---

## Teste Nyquist — U-13

### NT-1: Build bem-sucedido

```bash
# Smoke test executado localmente antes de push para main
# Verifica que o Dockerfile builda sem erros e os módulos são importáveis

docker build \
  -t gcr.io/test-project/pipeline:test \
  -f agents/pipeline/Dockerfile \
  agents/pipeline

# Verifica imports críticos
docker run --rm gcr.io/test-project/pipeline:test \
  python -c "
from shared.retry import with_retry
from shared.cost_tracker import CostTrackerService
from shared.firestore_client import FirestoreClient
from shared.pubsub_client import PubSubClient
print('OK: todos os imports shared funcionam')
"

# Verifica ffmpeg disponível
docker run --rm gcr.io/test-project/pipeline:test ffmpeg -version

# Verifica Playwright Chromium instalado
docker run --rm gcr.io/test-project/pipeline:test \
  python -c "from playwright.sync_api import sync_playwright; print('OK: Playwright disponível')"
```

---

## Constraints e Decisões

| Constraint | Detalhe |
|---|---|
| Imagem unificada | Todos os Jobs usam `gcr.io/$PROJECT_ID/pipeline` com CMD override. Simplifica build e reduz duplicação. |
| `--max-retries=0` nos Jobs | Retry gerenciado em código (`with_retry`), não pelo Cloud Run. Evita execuções duplicadas. |
| Steps 3–8 paralelos | `waitFor: [push]` em todos — deploy total ≈ tempo do step mais lento (~2min), não soma de todos (~12min). |
| `--no-allow-unauthenticated` nos Services | heygen-callback e publisher-immediate não são públicos. HeyGen autentica via token no header. |
| `_HEYGEN_CB_URL` como substitution | URL do heygen-callback só é conhecida após o primeiro deploy. Atualizar a substitution var após Step 3. |
| Playwright flags | `--disable-dev-shm-usage --no-sandbox` obrigatórios em Cloud Run (sem `/dev/shm` real). Passadas via env var `PLAYWRIGHT_CHROMIUM_ARGS`. |
