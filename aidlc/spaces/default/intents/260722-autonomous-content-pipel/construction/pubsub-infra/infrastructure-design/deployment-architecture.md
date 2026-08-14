# Deployment Architecture — Bolt 0+1

> Referências: [components.md](../../../inception/application-design/components.md) | [services.md](../../../inception/application-design/services.md) | [logical-components.md](../nfr-design/logical-components.md)

---

## Topologia GCP — Projeto `vazfy-417019`

```
Region: us-central1

Cloud Run Services (always-on, HTTP):
  ├── web (Next.js)               → gcr.io/vazfy-417019/web:SHA
  ├── cmo-agent (FastAPI)         → gcr.io/vazfy-417019/cmo-agent:SHA
  ├── heygen-callback (FastAPI)   → gcr.io/vazfy-417019/pipeline:SHA  [port 8091]
  └── publisher-immediate (FastAPI) → gcr.io/vazfy-417019/pipeline:SHA [port 8092]

Cloud Run Jobs (on-demand):
  ├── tts-job              → gcr.io/vazfy-417019/pipeline:SHA  [512Mi, 1800s]
  ├── avatar-job           → gcr.io/vazfy-417019/pipeline:SHA  [512Mi, 9000s]
  ├── video-editor-job     → gcr.io/vazfy-417019/pipeline:SHA  [4Gi,   3600s]
  └── publisher-scheduled  → gcr.io/vazfy-417019/pipeline:SHA  [512Mi, 1800s]

Pub/Sub Topics:
  ├── content-pipeline.package-approved   → subscription: tts-job-sub
  ├── content-pipeline.tts-completed      → subscription: avatar-job-sub
  ├── content-pipeline.avatar-completed   → subscription: video-editor-job-sub
  ├── content-pipeline.video-ready        → subscription: publisher-service-sub
  └── content-pipeline.dead-letter        ← mensagens com 5+ falhas

Firestore:
  └── content_projects/{project_id}
  └── pipeline_config/{tenantId}
  └── channel_config/{tenantId}/{channelId}

GCS:
  └── vazfy-417019-pipeline-media/
      └── projects/{project_id}/
          ├── manifest.html
          ├── audio/{horizontal|vertical}/{segment_id}.mp3
          ├── avatar_{horizontal|vertical}.mp4
          └── final_{horizontal|vertical}_cut.mp4

Secret Manager:
  ├── elevenlabs-api-key
  ├── elevenlabs-voice-id
  ├── elevenlabs-model-id
  ├── heygen-avatar-id-horizontal
  ├── heygen-avatar-id-vertical
  ├── youtube-oauth-client-id
  ├── youtube-oauth-client-secret
  ├── youtube-oauth-refresh-token
  └── (heygen-api-key → no Firestore agent_configurations/api_keys)

Cloud Scheduler:
  └── content-pipeline-daily-publisher  [cron: 0 21 * * *, POST publisher-immediate]
```

## GCS Bucket Setup

```bash
# Criar bucket de mídia da pipeline
gcloud storage buckets create gs://vazfy-417019-pipeline-media \
  --project=vazfy-417019 \
  --location=us-central1 \
  --uniform-bucket-level-access

# Lifecycle policy: expirar mídias temporárias após 30 dias
cat > /tmp/lifecycle.json << 'EOF'
{
  "lifecycle": {
    "rule": [{
      "action": {"type": "Delete"},
      "condition": {
        "age": 30,
        "matchesPrefix": ["projects/"]
      }
    }]
  }
}
EOF
gcloud storage buckets update gs://vazfy-417019-pipeline-media \
  --lifecycle-file=/tmp/lifecycle.json
```
