# CD Config — Content Pipeline éozoré

## Estratégia de Deploy

**Tipo:** Rolling deploy (Cloud Run gerencia automaticamente)
**Rollback:** `gcloud run deploy <service> --image=gcr.io/vazfy-417019/pipeline:<sha-anterior>`

## Sequência de Primeiro Deploy

```bash
# 1. Setup infra (one-time)
bash agents/pipeline/infra/setup_pubsub.sh vazfy-417019
firebase deploy --only firestore --project vazfy-417019
gcloud storage buckets create gs://vazfy-417019-pipeline-media --location=us-central1

# 2. Build e push da imagem
gcloud builds submit agents/pipeline --tag=gcr.io/vazfy-417019/pipeline:latest --project=vazfy-417019

# 3. Criar Jobs (one-time)
bash agents/pipeline/infra/setup_jobs.sh vazfy-417019

# 4. Deploy dos Services
gcloud run deploy heygen-callback --image=gcr.io/vazfy-417019/pipeline:latest \
  --region=us-central1 --port=8091 --command=uvicorn \
  --args="heygen_callback.app:app,--host,0.0.0.0,--port,8091" \
  --min-instances=0 --max-instances=1 --memory=512Mi \
  --set-env-vars=GCP_PROJECT_ID=vazfy-417019,GCS_BUCKET=vazfy-417019-pipeline-media \
  --no-allow-unauthenticated --project=vazfy-417019
```

## Deploys Subsequentes

```bash
# Basta fazer push para main — Cloud Build trigger executa cloudbuild-pipeline.yaml
git push origin main
```
