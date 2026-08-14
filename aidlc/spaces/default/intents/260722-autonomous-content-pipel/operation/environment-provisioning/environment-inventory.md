# Environment Inventory — vazfy-417019

## GCP Resources — Estado Atual

| Recurso | Nome | Status |
|---|---|---|
| Projeto GCP | `vazfy-417019` | ✅ Ativo |
| Pub/Sub `package-approved` | `content-pipeline.package-approved` | ✅ Criado |
| Pub/Sub `tts-completed` | `content-pipeline.tts-completed` | ✅ Criado |
| Pub/Sub `avatar-completed` | `content-pipeline.avatar-completed` | ✅ Criado |
| Pub/Sub `video-ready` | `content-pipeline.video-ready` | ✅ Criado |
| YouTube Data API v3 | `youtube.googleapis.com` | ✅ Ativada |
| Cloud Pub/Sub API | `pubsub.googleapis.com` | ✅ Ativada |
| Secret `elevenlabs-api-key` | — | ✅ Criado |
| Secret `elevenlabs-voice-id` | `5Oz8jx1GZxw1SmDcDANu` | ✅ Criado |
| Secret `elevenlabs-model-id` | `eleven_flash_v2_5` | ✅ Criado |
| Secret `heygen-avatar-id-horizontal` | `32e2ad6b...` | ✅ Criado |
| Secret `heygen-avatar-id-vertical` | `d7fdce29...` | ✅ Criado |
| Secret `youtube-oauth-client-id` | — | ✅ Criado |
| Secret `youtube-oauth-client-secret` | — | ✅ Criado |
| Secret `youtube-oauth-refresh-token` | Canal Victor Zoré | ✅ Criado |

## Pendente (Bolt 1 Deploy)

| Recurso | Ação |
|---|---|
| GCS Bucket `vazfy-417019-pipeline-media` | Criar via `gcloud storage buckets create` |
| Service Account `pipeline-jobs-sa` | Criar via `gcloud iam service-accounts create` |
| Cloud Run Jobs (tts-job, avatar-job, etc.) | Criar via `setup_jobs.sh` |
| Cloud Run Services (heygen-callback) | Deploy via `cloudbuild-pipeline.yaml` |
| Firestore rules + indexes | Deploy via `firebase deploy --only firestore` |
