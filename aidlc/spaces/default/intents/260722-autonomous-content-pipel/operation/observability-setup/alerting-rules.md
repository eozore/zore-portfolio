# Alerting Rules

| Alerta | Condição | Canal |
|---|---|---|
| Dead-letter com mensagens | num_undelivered_messages > 0 em content-pipeline.dead-letter | Email |
| Job falhou 3x | execution_count com status=failed > 2 | Email |
| Custo diário > $5 | Billing alert | Email |