# Reliability Requirements — Bolt 0 + Bolt 1

> Referências: [requirements.md](../../inception/requirements-analysis/requirements.md) | [functional-design (todas as unidades)](../firestore-schema/functional-design/business-logic-model.md)

---

## Idempotência (NFR-09)

Todos os Cloud Run Jobs verificam estado no Firestore antes de executar. Se já estão em `completed`, retornam sem reprocessar. Garante que re-entrega de mensagem Pub/Sub não causa duplicação.

| Job | Verificação | Campo |
|---|---|---|
| TTSJob | `stages.tts.status == "completed"` → retorna | `get_project()` no início |
| AvatarJob | `stages.avatar.status in ("completed", "pending_callback")` → retorna | `get_project()` no início |
| HeyGenCallback | `lipsync_jobs.{orientation}.status == "completed"` já processado | Verifica antes de re-download |

## Retry Automático (NFR-11, FR-11)

| Código HTTP | Classificação | Comportamento |
|---|---|---|
| 429 | Transitório | Retry com backoff [1s, 4s, 16s] — máx 3 tentativas |
| 503 | Transitório | Retry com backoff [1s, 4s, 16s] |
| 401, 403 | Permanente | Falha imediata, sem retry |
| Outros 4xx | Permanente | Falha imediata, sem retry |
| 5xx (exceto 503) | Transitório | Retry |

## Tolerância a Falhas

| Cenário | Comportamento |
|---|---|
| HeyGen timeout (> 90 min sem callback) | `stages.avatar.status = "error"` — Victor pode re-tentar manualmente |
| Pub/Sub dead-letter (5 tentativas) | Mensagem em `content-pipeline.dead-letter` — alerta Cloud Monitoring |
| GCS upload falha | Propagado como `TransientError` → retry automático |
| Firestore indisponível | Propagado como exceção → Cloud Run Job reinicia via retry do Pub/Sub |

## Disponibilidade (NFR-05)

Target: 5 pacotes/semana processados end-to-end sem intervenção manual.
Com retry automático de falhas transitórias, a taxa esperada de falhas permanentes por vídeo é < 5% (baseado em disponibilidade ElevenLabs 99.9% × HeyGen 99.5% × GCS 99.99%).
