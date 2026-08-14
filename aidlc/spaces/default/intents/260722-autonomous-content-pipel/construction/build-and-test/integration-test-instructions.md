# Integration Test Instructions — Bolt 0 + Bolt 1

Testes de integração reais requerem o Bolt 1 deployado no GCP.

```bash
# Spike de validação end-to-end (executado manualmente)
# 1. Publicar mensagem de teste no Pub/Sub
gcloud pubsub topics publish content-pipeline.package-approved \
  --project=vazfy-417019 \
  --message='{"project_id":"test-integration","manifest_gcs_path":"gs://vazfy-417019-pipeline-media/test/manifest.html","channels_approved":["blog"],"approved_at":"2026-07-23T00:00:00Z","cost_limit":100.0}'

# 2. Verificar que TTS Job processou
gcloud logging read "resource.type=cloud_run_job AND labels.job_name=tts-job" --limit=20
```
