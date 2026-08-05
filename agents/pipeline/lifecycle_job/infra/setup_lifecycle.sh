#!/usr/bin/env bash
# ============================================================
# setup_lifecycle.sh — Sprint 4 / G6
# Provisiona o lifecycle_job (Cloud Run Job) e o Cloud Scheduler
# que o dispara diariamente às 03:00 UTC.
#
# Pré-requisitos:
#   gcloud auth login
#   gcloud config set project vazfy-417019
#   docker auth com Artifact Registry configurado
#
# Uso:
#   bash setup_lifecycle.sh [--dry-run]
# ============================================================
set -euo pipefail

# ── Configuração ─────────────────────────────────────────────
PROJECT_ID="${GCP_PROJECT_ID:-vazfy-417019}"
REGION="${GCP_REGION:-us-central1}"
JOB_NAME="lifecycle-job"
IMAGE_TAG="gcr.io/${PROJECT_ID}/lifecycle-job:latest"
SERVICE_ACCOUNT="pipeline-sa@${PROJECT_ID}.iam.gserviceaccount.com"
SCHEDULER_SA="scheduler-sa@${PROJECT_ID}.iam.gserviceaccount.com"

MEDIA_BUCKET="${GCS_MEDIA_BUCKET:-${PROJECT_ID}-pipeline-media}"
ARCHIVE_BUCKET="${GCS_ARCHIVE_BUCKET:-${PROJECT_ID}-pipeline-archive}"
RETENTION_DAYS="${LIFECYCLE_RETENTION_DAYS:-60}"

DRY_RUN_FLAG="false"
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN_FLAG="true"
  echo "⚠  Modo dry-run ativado — nenhum asset será deletado."
fi

echo "=== lifecycle_job setup ==="
echo "Projeto:         ${PROJECT_ID}"
echo "Região:          ${REGION}"
echo "Job:             ${JOB_NAME}"
echo "Imagem:          ${IMAGE_TAG}"
echo "Media bucket:    ${MEDIA_BUCKET}"
echo "Archive bucket:  ${ARCHIVE_BUCKET}"
echo "Retenção (dias): ${RETENTION_DAYS}"
echo "Dry-run:         ${DRY_RUN_FLAG}"
echo ""

# ── 1. Cria bucket de archive (Nearline, se não existir) ─────
echo ">>> Verificando bucket de archive..."
if ! gsutil ls "gs://${ARCHIVE_BUCKET}" &>/dev/null; then
  gsutil mb \
    -p "${PROJECT_ID}" \
    -l "${REGION}" \
    -c NEARLINE \
    "gs://${ARCHIVE_BUCKET}"
  echo "    Bucket gs://${ARCHIVE_BUCKET} criado (Nearline)."
else
  echo "    Bucket gs://${ARCHIVE_BUCKET} já existe."
fi

# ── 2. Build e push da imagem Docker ─────────────────────────
echo ">>> Build e push da imagem..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIFECYCLE_DIR="$(dirname "${SCRIPT_DIR}")"
AGENTS_DIR="$(dirname "${LIFECYCLE_DIR}")"

# Copia shared/ para o contexto do build se existir
if [[ -d "${AGENTS_DIR}/shared" ]]; then
  cp -r "${AGENTS_DIR}/shared" "${LIFECYCLE_DIR}/shared_tmp" 2>/dev/null || true
fi

gcloud builds submit \
  --tag "${IMAGE_TAG}" \
  --project "${PROJECT_ID}" \
  "${LIFECYCLE_DIR}"

# Limpa shared temporário
rm -rf "${LIFECYCLE_DIR}/shared_tmp" 2>/dev/null || true

echo "    Imagem enviada: ${IMAGE_TAG}"

# ── 3. Cria/atualiza Cloud Run Job ────────────────────────────
echo ">>> Criando/atualizando Cloud Run Job..."
gcloud run jobs create "${JOB_NAME}" \
  --image="${IMAGE_TAG}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --service-account="${SERVICE_ACCOUNT}" \
  --max-retries=1 \
  --task-timeout=3600 \
  --set-env-vars="GCP_PROJECT_ID=${PROJECT_ID},GCS_MEDIA_BUCKET=${MEDIA_BUCKET},GCS_ARCHIVE_BUCKET=${ARCHIVE_BUCKET},LIFECYCLE_RETENTION_DAYS=${RETENTION_DAYS},LIFECYCLE_DRY_RUN=${DRY_RUN_FLAG}" \
  2>/dev/null || \
gcloud run jobs update "${JOB_NAME}" \
  --image="${IMAGE_TAG}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --service-account="${SERVICE_ACCOUNT}" \
  --max-retries=1 \
  --task-timeout=3600 \
  --set-env-vars="GCP_PROJECT_ID=${PROJECT_ID},GCS_MEDIA_BUCKET=${MEDIA_BUCKET},GCS_ARCHIVE_BUCKET=${ARCHIVE_BUCKET},LIFECYCLE_RETENTION_DAYS=${RETENTION_DAYS},LIFECYCLE_DRY_RUN=${DRY_RUN_FLAG}"

echo "    Cloud Run Job ${JOB_NAME} pronto."

# ── 4. IAM: permite que o Scheduler invoque o Job ─────────────
echo ">>> Configurando IAM para o Scheduler..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SCHEDULER_SA}" \
  --role="roles/run.invoker" \
  --condition=None \
  --quiet 2>/dev/null || echo "    (IAM binding pode já existir)"

# ── 5. Cria/atualiza Cloud Scheduler job (diário 03:00 UTC) ──
echo ">>> Configurando Cloud Scheduler..."
JOB_URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB_NAME}:run"

gcloud scheduler jobs create http "trigger-${JOB_NAME}" \
  --location="${REGION}" \
  --project="${PROJECT_ID}" \
  --schedule="0 3 * * *" \
  --time-zone="UTC" \
  --uri="${JOB_URI}" \
  --http-method=POST \
  --oauth-service-account-email="${SCHEDULER_SA}" \
  --attempt-deadline=3700s \
  --description="Arquiva assets de projetos publicados há mais de ${RETENTION_DAYS} dias" \
  2>/dev/null || \
gcloud scheduler jobs update http "trigger-${JOB_NAME}" \
  --location="${REGION}" \
  --project="${PROJECT_ID}" \
  --schedule="0 3 * * *" \
  --time-zone="UTC" \
  --uri="${JOB_URI}" \
  --http-method=POST \
  --oauth-service-account-email="${SCHEDULER_SA}" \
  --attempt-deadline=3700s

echo "    Cloud Scheduler 'trigger-${JOB_NAME}' configurado (0 3 * * * UTC)."

echo ""
echo "=== setup_lifecycle.sh concluído com sucesso ==="
echo ""
echo "Para testar manualmente:"
echo "  gcloud run jobs execute ${JOB_NAME} --region=${REGION} --project=${PROJECT_ID}"
echo ""
echo "Para rodar em dry-run sem deletar nada:"
echo "  gcloud run jobs execute ${JOB_NAME} --region=${REGION} --project=${PROJECT_ID} \\"
echo "    --update-env-vars=LIFECYCLE_DRY_RUN=true"
