#!/usr/bin/env bash
# =============================================================================
# setup_infra.sh — Primeiro deploy da content pipeline éozoré
#
# Uso:
#   cd zore-portfolio/
#   bash agents/pipeline/infra/setup_infra.sh
#
# O script:
#  1. Valida pré-requisitos (terraform, gcloud autenticado)
#  2. Inicializa o Terraform
#  3. Importa recursos que já existem no GCP (Pub/Sub topics)
#  4. Executa terraform apply
#  5. Imprime instruções para atualizar a callback URL do HeyGen
# =============================================================================
set -euo pipefail

PROJECT_ID="vazfy-417019"
REGION="us-central1"
TF_DIR="$(cd "$(dirname "$0")/../../../infra/pipeline" && pwd)"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── 1. Pré-requisitos ─────────────────────────────────────────────────────

info "Verificando pré-requisitos..."

command -v terraform >/dev/null 2>&1 || error "terraform não encontrado. Instale via: brew install terraform"
command -v gcloud    >/dev/null 2>&1 || error "gcloud não encontrado."

ACTIVE_ACCOUNT=$(gcloud config get-value account 2>/dev/null || echo "")
[[ -z "$ACTIVE_ACCOUNT" ]] && error "gcloud não autenticado. Execute: gcloud auth login"
info "Conta gcloud ativa: $ACTIVE_ACCOUNT"

ACTIVE_PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")
if [[ "$ACTIVE_PROJECT" != "$PROJECT_ID" ]]; then
  warn "Projeto gcloud atual é '$ACTIVE_PROJECT', trocando para '$PROJECT_ID'..."
  gcloud config set project "$PROJECT_ID"
fi

# Garante credenciais de aplicação para o Terraform
if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
  warn "Application Default Credentials não configuradas. Executando gcloud auth application-default login..."
  gcloud auth application-default login
fi

info "Pré-requisitos OK"

# ── 2. Terraform init ─────────────────────────────────────────────────────

info "Inicializando Terraform em $TF_DIR..."
cd "$TF_DIR"
terraform init -input=false

# ── 3. Import de recursos já existentes no GCP ────────────────────────────
#
# Os 4 Pub/Sub topics foram criados manualmente. O Terraform precisa
# conhecê-los antes do apply para não tentar recriá-los (erro 409).
# O comando import é idempotente — se já estiver no state, mostra warning e continua.

import_if_missing() {
  local resource="$1"
  local gcp_id="$2"

  if terraform state show "$resource" >/dev/null 2>&1; then
    warn "Já no state: $resource — pulando import"
  else
    info "Importando: $resource"
    terraform import -input=false "$resource" "$gcp_id"
  fi
}

info "Importando Pub/Sub topics existentes..."
import_if_missing \
  "google_pubsub_topic.package_approved" \
  "projects/${PROJECT_ID}/topics/content-pipeline.package-approved"

import_if_missing \
  "google_pubsub_topic.tts_completed" \
  "projects/${PROJECT_ID}/topics/content-pipeline.tts-completed"

import_if_missing \
  "google_pubsub_topic.avatar_completed" \
  "projects/${PROJECT_ID}/topics/content-pipeline.avatar-completed"

import_if_missing \
  "google_pubsub_topic.video_ready" \
  "projects/${PROJECT_ID}/topics/content-pipeline.video-ready"

# ── 4. Plan ───────────────────────────────────────────────────────────────

info "Executando terraform plan..."
terraform plan \
  -var="project_id=${PROJECT_ID}" \
  -var="region=${REGION}" \
  -out=tfplan

echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW} Revise o plan acima. Recursos a serem CRIADOS:${NC}"
echo -e "${YELLOW}  • google_service_account.pipeline_jobs${NC}"
echo -e "${YELLOW}  • google_storage_bucket.pipeline_media${NC}"
echo -e "${YELLOW}  • google_pubsub_topic.dead_letter${NC}"
echo -e "${YELLOW}  • 4x google_pubsub_subscription.*${NC}"
echo -e "${YELLOW}  • 2x google_cloud_run_v2_service (heygen-callback, publisher-immediate)${NC}"
echo -e "${YELLOW}  • 4x google_cloud_run_v2_job (tts, avatar, video-editor, publisher)${NC}"
echo -e "${YELLOW}  • 1x google_cloud_scheduler_job${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════════${NC}"
echo ""

read -rp "Aplicar? (s/N): " CONFIRM
[[ "${CONFIRM,,}" != "s" ]] && { info "Cancelado pelo usuário."; exit 0; }

# ── 5. Apply ──────────────────────────────────────────────────────────────

info "Aplicando Terraform..."
terraform apply -input=false tfplan

# ── 6. Captura outputs ────────────────────────────────────────────────────

CALLBACK_URL=$(terraform output -raw heygen_callback_url 2>/dev/null || echo "")
BUCKET_NAME=$(terraform output -raw pipeline_media_bucket 2>/dev/null || echo "")
SA_EMAIL=$(terraform output -raw service_account_email 2>/dev/null || echo "")

# ── 7. Firestore indexes ──────────────────────────────────────────────────

REPO_ROOT="$(cd "$TF_DIR/../../.." && pwd)"
if [[ -f "$REPO_ROOT/firestore.indexes.json" ]]; then
  info "Fazendo deploy dos Firestore indexes..."
  if command -v firebase >/dev/null 2>&1; then
    firebase deploy --only firestore:indexes --project "$PROJECT_ID" --config "$REPO_ROOT/firebase.json" || \
      warn "firebase deploy falhou — execute manualmente: firebase deploy --only firestore --project $PROJECT_ID"
  else
    warn "firebase CLI não encontrado — instale com: npm install -g firebase-tools"
    warn "Depois execute: firebase deploy --only firestore --project $PROJECT_ID"
  fi
fi

# ── 8. Atualiza callback URL no avatar-job ────────────────────────────────

if [[ -n "$CALLBACK_URL" && "$CALLBACK_URL" != *"placeholder"* ]]; then
  info "Atualizando HEYGEN_CALLBACK_URL no avatar-job Cloud Run Job..."
  gcloud run jobs update avatar-job \
    --region="$REGION" \
    --project="$PROJECT_ID" \
    --update-env-vars="HEYGEN_CALLBACK_URL=${CALLBACK_URL}" \
    2>&1 || warn "Falha ao atualizar env var — o job ainda não está no ar (normal no 1º deploy antes do cloudbuild)"
fi

# ── 9. Resumo ─────────────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN} INFRAESTRUTURA PRONTA${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e " Bucket GCS   : ${BUCKET_NAME}"
echo -e " Service Acct : ${SA_EMAIL}"
echo -e " HeyGen CB URL: ${CALLBACK_URL}"
echo ""
echo -e "${YELLOW}PRÓXIMOS PASSOS:${NC}"
echo -e " 1. Anote a HeyGen Callback URL acima."
echo -e " 2. Se diferente de 'placeholder', atualize var.heygen_callback_url em infra/pipeline/variables.tf"
echo -e "    e execute terraform apply novamente."
echo -e " 3. Execute o deploy da imagem Docker:"
echo -e "    gcloud builds submit --config=cloudbuild-pipeline.yaml --project=$PROJECT_ID"
echo -e " 4. Teste com mensagem Pub/Sub:"
echo -e "    gcloud pubsub topics publish content-pipeline.package-approved \\"
echo -e "      --message='{\"project_id\":\"test-001\",\"script\":\"Olá mundo\",\"orientations\":[\"horizontal\"]}' \\"
echo -e "      --project=$PROJECT_ID"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
