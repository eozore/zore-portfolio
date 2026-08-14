# Build Instructions

## cmo-agent + frontend
```bash
gcloud builds submit --config=cloudbuild.yaml --project=vazfy-417019 --substitutions=COMMIT_SHA=bugfixes-v1
```

## Pré-deploy obrigatório (BUG4)
```bash
# Adicionar TAVILY_API_KEY no Secret Manager
gcloud secrets create TAVILY_API_KEY --project=vazfy-417019
echo -n "<chave>" | gcloud secrets versions add TAVILY_API_KEY --data-file=-
# Montar no Cloud Run do cmo-agent
gcloud run services update cmo-agent --region=us-central1 --project=vazfy-417019 \
  --update-secrets=TAVILY_API_KEY=TAVILY_API_KEY:latest
```

## BUG2 — Deploy coordenado
Os 3 serviços devem ser deployados no mesmo build:
- heygen-callback
- video-editor-job (Cloud Run Job)
- avatar-job (Cloud Run Job)
O cloudbuild.yaml deve incluir os 3.
