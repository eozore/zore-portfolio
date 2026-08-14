# Shared Infrastructure — Bolt 0+1

---

## Recursos Compartilhados por Todas as Unidades

| Recurso | Tipo | Compartilhado por |
|---|---|---|
| `gcr.io/vazfy-417019/pipeline` | Container Registry | tts-job, avatar-job, video-editor-job, heygen-callback, publisher-* |
| `vazfy-417019-pipeline-media` | GCS Bucket | Todos os jobs (read/write) |
| `pipeline-jobs-sa@vazfy-417019.iam.gserviceaccount.com` | Service Account | Todos os Cloud Run Jobs/Services |
| `content-pipeline.*` | Pub/Sub Topics | Todos os jobs (producer + consumer) |
| `content_projects` | Firestore Collection | Todos os jobs + frontend |
| `pipeline_config` | Firestore Collection | Todos os jobs (leitura de config) |

## Imagem Unificada — `gcr.io/vazfy-417019/pipeline`

Tamanho estimado:
- python:3.12-slim base: ~130 MB
- ffmpeg: ~80 MB
- playwright + chromium: ~400 MB
- Python packages: ~250 MB
- **Total: ~860 MB comprimido**

Pull time no cold start: ~15-30s (aceitável para jobs assíncronos)
