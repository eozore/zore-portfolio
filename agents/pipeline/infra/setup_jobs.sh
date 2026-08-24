#!/bin/bash
# Cria os Cloud Run Jobs iniciais da content pipeline éozoré
# Executar UMA vez no setup do projeto. Deploys subsequentes usam cloudbuild-pipeline.yaml.
# Uso: ./setup_jobs.sh [project_id] [region]
set -e

PROJECT=${1:-vazfy-417019}
REGION=${2:-us-central1}
SA_EMAIL="pipeline-jobs-sa@${PROJECT}.iam.gserviceaccount.com"
GCS_BUCKET="${PROJECT}-pipeline-media"
IMAGE="gcr.io/${PROJECT}/pipeline:latest"

echo "Criando Cloud Run Jobs no projeto: $PROJECT (região: $REGION)"
echo "Service Account: $SA_EMAIL"
echo "Image: $IMAGE"
echo ""

# ── tts-job ──────────────────────────────────────────────────────────────────
echo "Criando tts-job..."
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
  --set-env-vars="GCP_PROJECT_ID=${PROJECT},GCS_BUCKET=${GCS_BUCKET},TENANT_ID=default" \
  --set-secrets="ELEVENLABS_API_KEY=elevenlabs-api-key:latest,ELEVENLABS_VOICE_ID=elevenlabs-voice-id:latest" \
  2>/dev/null || echo "  (tts-job já existe — use gcloud run jobs update para atualizar)"

# ── avatar-job ────────────────────────────────────────────────────────────────
echo "Criando avatar-job..."
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
  --set-env-vars="GCP_PROJECT_ID=${PROJECT},GCS_BUCKET=${GCS_BUCKET},TENANT_ID=default,HEYGEN_CALLBACK_URL=https://heygen-callback-HASH-uc.a.run.app" \
  --set-secrets="HEYGEN_API_KEY=heygen-api-key:latest" \
  2>/dev/null || echo "  (avatar-job já existe — use gcloud run jobs update para atualizar)"

# ── video-editor-job ──────────────────────────────────────────────────────────
echo "Criando video-editor-job..."
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
  --set-env-vars="GCP_PROJECT_ID=${PROJECT},GCS_BUCKET=${GCS_BUCKET},TENANT_ID=default,PLAYWRIGHT_CHROMIUM_ARGS=--disable-dev-shm-usage --no-sandbox --disable-gpu" \
  2>/dev/null || echo "  (video-editor-job já existe — use gcloud run jobs update para atualizar)"

# ── vertical-cut-job ──────────────────────────────────────────────────────────
# Deriva o Reel/Short do vídeo do YouTube: crop 9:16 dos clipes de avatar já
# gerados + ilustração vertical com o mesmo áudio TTS. Não chama HeyGen nem
# ElevenLabs, então é barato e pode ser reexecutado à vontade.
echo "Criando vertical-cut-job..."
gcloud run jobs create vertical-cut-job \
  --image="${IMAGE}" \
  --region="${REGION}" \
  --command=python \
  --args="-m,vertical_cut_job" \
  --memory=4Gi \
  --cpu=4 \
  --task-timeout=3600s \
  --max-retries=0 \
  --service-account="${SA_EMAIL}" \
  --set-env-vars="GCP_PROJECT_ID=${PROJECT},GCS_BUCKET=${GCS_BUCKET},TENANT_ID=default,HEYGEN_AVATAR_CROP_X_RATIO=0.5,PLAYWRIGHT_CHROMIUM_ARGS=--disable-dev-shm-usage --no-sandbox --disable-gpu" \
  2>/dev/null || echo "  (vertical-cut-job já existe — use gcloud run jobs update para atualizar)"

# ── publisher-scheduled ───────────────────────────────────────────────────────
echo "Criando publisher-scheduled..."
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
  --set-env-vars="GCP_PROJECT_ID=${PROJECT},GCS_BUCKET=${GCS_BUCKET},TENANT_ID=default" \
  --set-secrets="YOUTUBE_OAUTH_TOKEN=youtube-oauth-token:latest,HEYGEN_API_KEY=heygen-api-key:latest" \
  2>/dev/null || echo "  (publisher-scheduled já existe — use gcloud run jobs update para atualizar)"

echo ""
echo "✅ Cloud Run Jobs criados com sucesso!"
echo ""

# ── Pub/Sub do corte vertical ─────────────────────────────────────────────────
# O Terraform em infra/pipeline/main.tf descreve estes recursos, mas NÃO roda no
# CI — o cloudbuild só constrói a imagem e atualiza os jobs. Sem criar o tópico
# aqui, o botão "Gerar pacote de conteúdos" falha com NOT_FOUND ao publicar.
TRIGGER_URL=$(gcloud run services describe pipeline-trigger \
  --region="${REGION}" --project="${PROJECT}" --format='value(status.url)' 2>/dev/null || echo "")

echo "Criando tópico content-pipeline.vertical-cut..."
gcloud pubsub topics create content-pipeline.vertical-cut \
  --project="${PROJECT}" \
  2>/dev/null || echo "  (tópico já existe)"

if [ -n "$TRIGGER_URL" ]; then
  echo "Criando subscription vertical-cut-job-sub → ${TRIGGER_URL}/trigger/vertical-cut..."
  gcloud pubsub subscriptions create vertical-cut-job-sub \
    --project="${PROJECT}" \
    --topic=content-pipeline.vertical-cut \
    --push-endpoint="${TRIGGER_URL}/trigger/vertical-cut" \
    --push-auth-service-account="${SA_EMAIL}" \
    --ack-deadline=600 \
    --dead-letter-topic=content-pipeline.dead-letter \
    --max-delivery-attempts=5 \
    2>/dev/null || echo "  (subscription já existe)"
else
  echo "  ⚠️  pipeline-trigger ainda não deployado — crie a subscription depois:"
  echo "     gcloud pubsub subscriptions create vertical-cut-job-sub \\"
  echo "       --topic=content-pipeline.vertical-cut \\"
  echo "       --push-endpoint=<URL_DO_PIPELINE_TRIGGER>/trigger/vertical-cut \\"
  echo "       --push-auth-service-account=${SA_EMAIL} --ack-deadline=600"
fi
echo ""

# ── publisher-scheduler (Cloud Scheduler a cada hora) ────────────────────────
echo "Configurando Cloud Scheduler para publisher-scheduled (a cada hora)..."
PUBLISHER_JOB_URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT}/jobs/publisher-scheduled:run"
SCHEDULER_SA="scheduler-sa@${PROJECT}.iam.gserviceaccount.com"

# IAM: scheduler-sa pode invocar Cloud Run
gcloud projects add-iam-policy-binding "${PROJECT}" \
  --member="serviceAccount:${SCHEDULER_SA}" \
  --role="roles/run.invoker" \
  --condition=None \
  --quiet 2>/dev/null || echo "  (binding pode já existir)"

gcloud scheduler jobs create http "trigger-publisher-scheduled" \
  --location="${REGION}" \
  --project="${PROJECT}" \
  --schedule="0 * * * *" \
  --time-zone="America/Sao_Paulo" \
  --uri="${PUBLISHER_JOB_URI}" \
  --http-method=POST \
  --oauth-service-account-email="${SCHEDULER_SA}" \
  --attempt-deadline=1800s \
  --description="Publica itens da social_queue com status=planned e scheduled_at <= agora" \
  2>/dev/null || \
gcloud scheduler jobs update http "trigger-publisher-scheduled" \
  --location="${REGION}" \
  --project="${PROJECT}" \
  --schedule="0 * * * *" \
  --time-zone="America/Sao_Paulo" \
  --uri="${PUBLISHER_JOB_URI}" \
  --http-method=POST \
  --oauth-service-account-email="${SCHEDULER_SA}" \
  --attempt-deadline=1800s
echo "  ✅ Cloud Scheduler 'trigger-publisher-scheduled' configurado (0 * * * * horário de Brasília)."

echo ""
echo "Verificando jobs:"
gcloud run jobs list --region="${REGION}" --project="${PROJECT}" \
  --filter="metadata.name:(tts-job OR avatar-job OR video-editor-job OR vertical-cut-job OR publisher-scheduled)"
echo ""
echo "ATENÇÃO: Após primeiro deploy do heygen-callback Service,"
echo "         atualizar HEYGEN_CALLBACK_URL no avatar-job:"
echo "  gcloud run jobs update avatar-job \\"
echo "    --region=${REGION} \\"
echo "    --update-env-vars=HEYGEN_CALLBACK_URL=https://heygen-callback-<HASH>-uc.a.run.app"
