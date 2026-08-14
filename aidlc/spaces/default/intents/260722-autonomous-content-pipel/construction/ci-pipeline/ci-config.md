# CI Config — Pipeline Content éozoré

## Pipeline Principal: `cloudbuild-pipeline.yaml`

O arquivo `cloudbuild-pipeline.yaml` na raiz do repositório implementa o CI/CD completo para os microserviços Python da content pipeline. Separado do `cloudbuild.yaml` do web app conforme ADR da practices-discovery.

**Steps (todos paralelos após push da imagem):**

| Step | Serviço | Tipo | Timeout | Memória |
|---|---|---|---|---|
| 1 | build imagem | Docker build | — | — |
| 2 | push imagem | Docker push | — | — |
| 3 | heygen-callback | Cloud Run Service | 60s | 512Mi |
| 4 | publisher-immediate | Cloud Run Service | 300s | 512Mi |
| 5 | tts-job | Cloud Run Job | 1800s | 512Mi |
| 6 | avatar-job | Cloud Run Job | 9000s | 512Mi |
| 7 | video-editor-job | Cloud Run Job | 3600s | **4Gi** |
| 8 | publisher-scheduled | Cloud Run Job | 1800s | 512Mi |

## Trigger Recomendado (Cloud Build)

```yaml
# Trigger: mudanças em agents/pipeline/**
includedFiles:
  - "agents/pipeline/**"
  - "cloudbuild-pipeline.yaml"
```

## CI Complementar: Web App

O `cloudbuild.yaml` existente continua deployando o web app (Next.js + CMO Agent) separadamente.
