#!/bin/bash
# Cria tópicos Pub/Sub e subscriptions para a content pipeline éozoré
# Uso: ./setup_pubsub.sh <project_id>
set -e

PROJECT=${1:-vazfy-417019}
echo "Configurando Pub/Sub no projeto: $PROJECT"

# Tópicos principais
TOPICS=(
  "content-pipeline.package-approved"
  "content-pipeline.tts-completed"
  "content-pipeline.avatar-completed"
  "content-pipeline.video-ready"
)

for TOPIC in "${TOPICS[@]}"; do
  echo "Criando tópico: $TOPIC"
  gcloud pubsub topics create "$TOPIC" --project="$PROJECT" 2>/dev/null || \
    echo "  (já existe, pulando)"
done

# Dead-letter topic para mensagens que falharam após max_delivery_attempts
echo ""
echo "Criando dead-letter topic..."
gcloud pubsub topics create "content-pipeline.dead-letter" --project="$PROJECT" 2>/dev/null || \
  echo "  (dead-letter já existe)"

# Subscriptions com dead-letter e max retry
echo ""
echo "Criando subscriptions..."

create_subscription() {
  local TOPIC=$1
  local SUB=$2
  gcloud pubsub subscriptions create "$SUB" \
    --topic="$TOPIC" \
    --project="$PROJECT" \
    --ack-deadline=600 \
    --dead-letter-topic="content-pipeline.dead-letter" \
    --max-delivery-attempts=5 \
    2>/dev/null || echo "  (subscription $SUB já existe)"
}

create_subscription "content-pipeline.package-approved" "tts-job-sub"
create_subscription "content-pipeline.tts-completed"    "avatar-job-sub"
create_subscription "content-pipeline.avatar-completed" "video-editor-job-sub"
create_subscription "content-pipeline.video-ready"      "publisher-service-sub"

echo ""
echo "✅ Pub/Sub configurado com sucesso!"
echo ""
echo "Verificando tópicos:"
gcloud pubsub topics list --project="$PROJECT" --filter="name:content-pipeline"
