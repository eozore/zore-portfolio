# CI/CD Pipeline — Bolt 0+1

---

## Dois Pipelines Separados (practices-discovery)

### 1. `cloudbuild.yaml` — Web App (existente)
- Trigger: push para `main`
- Deploya: `cmo-agent` + `web` (Next.js)
- NÃO modificado por esta entrega

### 2. `cloudbuild-pipeline.yaml` — Content Pipeline (novo)
- Trigger: push para `main` com mudanças em `agents/pipeline/**`
- Deploya: imagem unificada + todos os Cloud Run Jobs/Services da pipeline
- Especificação completa em: `construction/cloudbuild-pipeline/functional-design/business-logic-model.md`

## Branch Strategy (team.md § Way of Working)

```
Bolt 0: git checkout -b bolt/foundations
         → implement → test → squash-merge → main

Bolt 1: git checkout -b bolt/walking-skeleton
         → implement → test → squash-merge → main
```

## Primeiro Deploy Manual (one-time setup)

```bash
# 1. Build e push da imagem inicial
gcloud builds submit agents/pipeline \
  --tag=gcr.io/vazfy-417019/pipeline:latest \
  --project=vazfy-417019

# 2. Criar Cloud Run Jobs (antes do primeiro deploy via YAML)
./agents/pipeline/infra/setup_jobs.sh vazfy-417019

# 3. Setup Pub/Sub
./agents/pipeline/infra/setup_pubsub.sh vazfy-417019

# 4. Setup Cloud Scheduler
./agents/pipeline/infra/setup_scheduler.sh vazfy-417019

# 5. Deploy Firestore rules e indexes
firebase deploy --only firestore --project vazfy-417019
```
