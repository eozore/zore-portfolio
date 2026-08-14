# Deployment Strategy — Content Pipeline éozoré

## Estratégia: Blue/Green simplificado via Cloud Run

Cloud Run gerencia automaticamente o rolling deploy — sem downtime. Para Services (heygen-callback, publisher-immediate):
- Nova revisão ativada gradualmente
- Tráfego migrando para nova revisão

Para Jobs (tts-job, avatar-job, etc.):
- Jobs são stateless por design — sem impacto em jobs em andamento

## Rollback

```bash
# Listar revisões
gcloud run revisions list --service=heygen-callback --region=us-central1

# Reverter para revisão anterior
gcloud run services update-traffic heygen-callback \
  --to-revisions=<revision-anterior>=100 --region=us-central1
```
