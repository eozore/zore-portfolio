# Build Instructions — Bolt 0 + Bolt 1

---

## Verificação Local (sem Docker)

```bash
cd /Users/victorzore/Desktop/zore-portfolio/agents/pipeline
PYTHONPATH=. python3 -m pytest tests/ -v
```

## Build Docker (local)

```bash
cd /Users/victorzore/Desktop/zore-portfolio
docker build -t gcr.io/vazfy-417019/pipeline:local -f agents/pipeline/Dockerfile agents/pipeline
```

## Deploy via Cloud Build

```bash
cd /Users/victorzore/Desktop/zore-portfolio
gcloud builds submit --config=cloudbuild-pipeline.yaml --project=vazfy-417019
```

## Primeiro Deploy (one-time setup)

```bash
# 1. Criar service account e permissões
# 2. Criar bucket GCS
gcloud storage buckets create gs://vazfy-417019-pipeline-media --location=us-central1

# 3. Setup Pub/Sub
bash agents/pipeline/infra/setup_pubsub.sh vazfy-417019

# 4. Deploy da imagem inicial
gcloud builds submit agents/pipeline --tag=gcr.io/vazfy-417019/pipeline:latest

# 5. Criar Cloud Run Jobs
bash agents/pipeline/infra/setup_jobs.sh vazfy-417019

# 6. Deploy Firestore rules e indexes
firebase deploy --only firestore --project vazfy-417019
```
