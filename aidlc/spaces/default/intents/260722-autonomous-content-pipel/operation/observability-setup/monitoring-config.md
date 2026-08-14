# Monitoring Config

## Cloud Logging
- Todos os jobs usam `logging.basicConfig(level=INFO, stream=sys.stdout)`
- Cloud Run captura stdout automaticamente

## Alertas Cloud Monitoring (configurar manualmente)
```bash
gcloud alpha monitoring policies create --notification-channels=EMAIL --policy-from-file=monitoring_policy.json
```

## Observabilidade Principal: CSM Studio Kanban
- `stages.{id}.status`, `retry_count`, `error_message` via Firestore listener
- Atualização em tempo real para Victor sem Cloud Monitoring dashboard