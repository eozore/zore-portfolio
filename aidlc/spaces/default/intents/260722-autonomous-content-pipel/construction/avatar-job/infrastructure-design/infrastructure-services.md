# Infrastructure Services — Bolt 0+1

---

## Serviços GCP Ativos (verificados)

| Serviço | API Name | Status | Ativado por |
|---|---|---|---|
| Cloud Firestore | `firestore.googleapis.com` | ✅ Ativo | Projeto existente |
| Cloud Storage | `storage.googleapis.com` | ✅ Ativo | Projeto existente |
| Cloud Pub/Sub | `pubsub.googleapis.com` | ✅ Ativado | Setup manual (sessão atual) |
| Secret Manager | `secretmanager.googleapis.com` | ✅ Ativo | Projeto existente |
| Cloud Run | `run.googleapis.com` | ✅ Ativo | Projeto existente |
| YouTube Data API v3 | `youtube.googleapis.com` | ✅ Ativado | Setup manual (sessão atual) |
| Artifact Registry | `artifactregistry.googleapis.com` | Verificar | Necessário para imagens Docker |

## Secrets Criados (verificados na sessão)

| Secret Name | Criado | Conteúdo |
|---|---|---|
| `elevenlabs-api-key` | ✅ | Chave API ElevenLabs |
| `elevenlabs-voice-id` | ✅ | `5Oz8jx1GZxw1SmDcDANu` |
| `elevenlabs-model-id` | ✅ | `eleven_flash_v2_5` |
| `heygen-avatar-id-horizontal` | ✅ | `32e2ad6b3e5a45bf8c61cbf7220912f4` |
| `heygen-avatar-id-vertical` | ✅ | `d7fdce2942a244649820a0b5c989766f` |
| `youtube-oauth-client-id` | ✅ | Client ID Web App |
| `youtube-oauth-client-secret` | ✅ | Client Secret Web App |
| `youtube-oauth-refresh-token` | ✅ | Refresh token canal Victor Zoré |

## Variáveis de Ambiente por Serviço

```bash
# Aplicadas via --set-env-vars no cloudbuild-pipeline.yaml
# Comuns a todos os jobs:
GCP_PROJECT_ID=vazfy-417019
GCS_BUCKET=vazfy-417019-pipeline-media
TENANT_ID=default

# Específico do avatar-job:
HEYGEN_CALLBACK_URL=https://heygen-callback-<HASH>-uc.a.run.app

# Específico do video-editor-job:
PLAYWRIGHT_CHROMIUM_ARGS=--disable-dev-shm-usage --no-sandbox --disable-gpu
```

## Ativações Pendentes (antes do primeiro deploy)

```bash
# Verificar/ativar Artifact Registry
gcloud services enable artifactregistry.googleapis.com --project=vazfy-417019

# Criar repositório de imagens Docker
gcloud artifacts repositories create pipeline-images \
  --repository-format=docker \
  --location=us-central1 \
  --project=vazfy-417019
# Nota: cloudbuild.yaml usa gcr.io (Container Registry legado) — manter por compatibilidade
```
