# Business Logic Model — U-02: pubsub-infra

> Referências: [unit-of-work.md](../../../inception/units-generation/unit-of-work.md) | [requirements.md](../../../inception/requirements-analysis/requirements.md) | [components.md](../../../inception/application-design/components.md) | [component-methods.md](../../../inception/application-design/component-methods.md) | [services.md](../../../inception/application-design/services.md) | [unit-of-work-story-map.md](../../../inception/units-generation/unit-of-work-story-map.md)

---

## Escopo

U-02 é provisionamento de infra GCP — não tem lógica de negócio. Provê os tópicos Pub/Sub e o Cloud Scheduler que todos os jobs consomem.

## Script de Provisionamento — `agents/pipeline/infra/setup_pubsub.sh`

```bash
#!/bin/bash
# Cria tópicos Pub/Sub e subscriptions para a content pipeline
# Uso: ./setup_pubsub.sh <project_id>
set -e

PROJECT=${1:-vazfy-417019}
echo "Configurando Pub/Sub no projeto: $PROJECT"

# Tópicos
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

# Dead-letter topic para mensagens que falharam
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
echo "✅ Pub/Sub configurado!"
echo ""
echo "Verificando:"
gcloud pubsub topics list --project="$PROJECT" --filter="name:content-pipeline"
```

## Cloud Scheduler — `agents/pipeline/infra/setup_scheduler.sh`

```bash
#!/bin/bash
# Cria o Cloud Scheduler para publicação diária
# Usa horário configurável via variável (default: 18:00 BRT = 21:00 UTC)
set -e

PROJECT=${1:-vazfy-417019}
PUBLISHER_URL=${2:-"https://publisher-immediate-HASH-uc.a.run.app/scheduled"}
REGION="us-central1"

echo "Criando Cloud Scheduler no projeto: $PROJECT"

gcloud scheduler jobs create http content-pipeline-daily-publisher \
  --project="$PROJECT" \
  --location="$REGION" \
  --schedule="0 21 * * *" \
  --uri="$PUBLISHER_URL" \
  --http-method=POST \
  --message-body='{"trigger":"scheduled"}' \
  --headers="Content-Type=application/json" \
  --time-zone="UTC" \
  --description="Pipeline diária de publicação de conteúdo éozoré" \
  2>/dev/null || \
  echo "Scheduler já existe — atualizando..."

echo "✅ Cloud Scheduler configurado!"
```

## IAM — Service Accounts

```bash
# Service account para os Cloud Run Jobs
gcloud iam service-accounts create pipeline-jobs-sa \
  --display-name="Content Pipeline Jobs" \
  --project="$PROJECT"

SA="pipeline-jobs-sa@${PROJECT}.iam.gserviceaccount.com"

# Permissões necessárias
ROLES=(
  "roles/pubsub.publisher"
  "roles/pubsub.subscriber"
  "roles/datastore.user"
  "roles/secretmanager.secretAccessor"
  "roles/storage.objectAdmin"
)

for ROLE in "${ROLES[@]}"; do
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:$SA" \
    --role="$ROLE"
done

echo "✅ IAM configurado para pipeline-jobs-sa"
```

## Teste Nyquist (1 teste — smoke test)

```bash
# Publicar mensagem de teste e verificar entrega
gcloud pubsub topics publish content-pipeline.package-approved \
  --project=vazfy-417019 \
  --message='{"project_id":"test-smoke","manifest_gcs_path":"gs://test/test.html","channels_approved":["blog"],"approved_at":"2026-07-23T00:00:00Z","cost_limit":100.0}'

# Verificar que a subscription recebeu
gcloud pubsub subscriptions pull tts-job-sub \
  --project=vazfy-417019 \
  --auto-ack \
  --limit=1

echo "✅ Smoke test: mensagem publicada e recebida com sucesso"
```
