# Rollback Runbook — Content Pipeline éozoré

## Cenário: Job falhou após deploy

```bash
# 1. Verificar logs do job
gcloud logging read "resource.type=cloud_run_job AND labels.job_name=tts-job" --limit=20

# 2. Reverter imagem para SHA anterior
PREV_SHA=$(gcloud run jobs describe tts-job --region=us-central1 --format="value(spec.template.spec.template.spec.containers[0].image)" | cut -d: -f2)
# Atualizar para SHA anterior via cloudbuild ou gcloud direto
gcloud run jobs update tts-job --image=gcr.io/vazfy-417019/pipeline:<sha-anterior> --region=us-central1
```

## Cenário: heygen-callback inacessível

```bash
# Reverter tráfego para revisão anterior
gcloud run services update-traffic heygen-callback --to-revisions=<rev>=100 --region=us-central1
```
