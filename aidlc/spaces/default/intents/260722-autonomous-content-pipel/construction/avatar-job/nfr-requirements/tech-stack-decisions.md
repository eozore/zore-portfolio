# Tech Stack Decisions — Bolt 0 + Bolt 1

> Referências: [requirements.md](../../inception/requirements-analysis/requirements.md) | [decisions.md](../../inception/application-design/decisions.md)

---

## Stack Confirmada (sem desvios dos ADRs)

| Componente | Tecnologia | Versão | ADR Ref |
|---|---|---|---|
| Jobs Python | Python 3.12-slim | 3.12 | ADR-02 |
| TTS | ElevenLabs Flash v2.5 | API REST | — |
| Avatar | HeyGen Lipsync API v3 | speed mode | ADR-03 |
| Webhook | FastAPI + Uvicorn | 0.111 / 0.29 | ADR-03 |
| Audio concat | pydub + ffmpeg | 0.25.1 + system | ADR-02 |
| Retry | asyncio custom (`shared/retry.py`) | — | ADR-01 |
| Custo | `shared/cost_tracker.py` módulo | — | ADR-08 |
| Container | Single Dockerfile multi-purpose | — | ADR-02 |
| CI/CD | `cloudbuild-pipeline.yaml` separado | — | practices-discovery |
| Infra GCP | Cloud Run Jobs + Services | — | ADR-01 |
| Mensageria | GCP Pub/Sub | — | ADR-01 |
| Estado | Firestore (Firebase Admin SDK) | — | ADR-01 |
| Secrets | GCP Secret Manager | — | SEC-01 |

## Dependências Externas Confirmadas

| Serviço | Custo real (spike) | Secret configurado |
|---|---|---|
| ElevenLabs Flash v2.5 | $0.00005/char | ✅ `elevenlabs-api-key`, `elevenlabs-voice-id` |
| HeyGen Lipsync speed | $0.0335/s | ✅ via Firestore `HEYGEN_API_KEY` |
| YouTube Data API v3 | Gratuito até quota | ✅ `youtube-oauth-refresh-token`, `youtube-oauth-client-id`, `youtube-oauth-client-secret` |
| GCS | ~$0.02/GB/mês | — (projeto já tem bucket) |
| Cloud Run Jobs | $0.00002/vCPU-sec | — (billing on-demand) |
