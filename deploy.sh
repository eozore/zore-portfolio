#!/bin/bash
# ==============================================================================
# Script de Implantação Automatizada no GCP (Cromex & Portfólio)
# ==============================================================================

# Definições de Configuração (Ajustar de acordo com o projeto GCP)
PROJECT_ID="eozore-portfolio"
REGION="us-central1"
BUCKET_NAME="eozore-cromex-data"

SERVICE_PY_NAME="cromex-pricing-service"
SERVICE_WEB_NAME="portfolio-web"

echo "=== 1. Autenticação e Configuração do GCP ==="
# Certifica-se de que o gcloud está configurado para o projeto correto
gcloud config set project $PROJECT_ID

echo "=== 2. Criando o Google Cloud Storage Bucket (se não existir) ==="
# Cria bucket multirregional para os inputs e outputs de planilhas
gsutil mb -p $PROJECT_ID -c standard -l $REGION gs://$BUCKET_NAME || true
gsutil iam ch allUsers:objectViewer gs://$BUCKET_NAME || true

echo "=== 2b. Enviando planilhas de exemplo para o bucket GCS ==="
# Envia planilhas de exemplo sem sobrescrever as existentes (-n)
gsutil cp -n tool-cromex/datainput/* gs://$BUCKET_NAME/raw/ || true

echo "=== 3. Construindo e Implantando o Microserviço Python (Cromex Pricing API) ==="
# Compila o container no Cloud Build e joga no Container Registry
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_PY_NAME projects/cromex-pricing-service

# Deploy do container compilado no Cloud Run
gcloud run deploy $SERVICE_PY_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_PY_NAME \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --update-env-vars GCP_STORAGE_BUCKET=$BUCKET_NAME,IS_LOCAL=false

# Obtém a URL gerada para o microserviço Python
PY_SERVICE_URL=$(gcloud run services describe $SERVICE_PY_NAME --platform managed --region $REGION --format 'value(status.url)')
echo "Microserviço Python implantado em: $PY_SERVICE_URL"

echo "=== 4. Construindo e Implantando o Frontend Next.js ==="
# Envia a URL do microserviço Python como variável de build para o Next.js
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_WEB_NAME \
  --update-env-vars NEXT_PUBLIC_PRICING_API_URL=$PY_SERVICE_URL \
  apps/web

# Deploy do Next.js no Cloud Run
gcloud run deploy $SERVICE_WEB_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_WEB_NAME \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated

WEB_URL=$(gcloud run services describe $SERVICE_WEB_NAME --platform managed --region $REGION --format 'value(status.url)')

echo "=============================================================================="
echo " Implantação Concluída com Sucesso!"
echo "------------------------------------------------------------------------------"
echo " Dashboard Cromex disponível em: $WEB_URL/pt-BR/tools/cromex"
echo " API Backend Pricing disponível em: $PY_SERVICE_URL/health"
echo "=============================================================================="
