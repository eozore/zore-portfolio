# Monitoring Design — Bolt 0+1

---

## Cloud Logging — Padrão de Logs

Todos os jobs usam `logging.basicConfig(level=logging.INFO, stream=sys.stdout)`. Cloud Run captura stdout automaticamente no Cloud Logging.

**Labels úteis para filtro:**
- `resource.type = "cloud_run_job"` para jobs
- `resource.type = "cloud_run_revision"` para services
- `jsonPayload.project_id` (adicionado nos logs via `logger.info(f"project_id={project_id} ...")`

## Alertas Críticos (Cloud Monitoring)

| Alerta | Condição | Canal |
|---|---|---|
| Dead-letter com mensagens | `pubsub.googleapis.com/subscription/num_undelivered_messages > 0` em `content-pipeline.dead-letter` | Email Victor |
| Job falhou 3x | `run.googleapis.com/job/execution_count` com status=failed > 2 | Email Victor |
| Custo diário > $5 | Billing alert | Email Victor |
| HeyGen callback timeout | Ausência de `avatar_completed` 90 min após `tts_completed` | Cloud Scheduler check job |

## Observabilidade do Pipeline

O Firestore `content_projects/{id}.stages` serve como painel de observabilidade em tempo real via Firestore listener no frontend. Cada job atualiza o stage com:
- `status`: estado atual
- `retry_count`: tentativas automáticas
- `error_message`: mensagem human-readable
- `started_at` / `completed_at`: timestamps para cálculo de duração

Isso elimina a necessidade de Cloud Monitoring dashboard para o fluxo normal — Victor vê tudo no kanban.
