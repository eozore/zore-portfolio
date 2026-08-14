# Business Rules — U-02: pubsub-infra

> Referências: [unit-of-work.md](../../../inception/units-generation/unit-of-work.md) | [requirements.md](../../../inception/requirements-analysis/requirements.md) | [components.md](../../../inception/application-design/components.md) | [component-methods.md](../../../inception/application-design/component-methods.md) | [services.md](../../../inception/application-design/services.md) | [unit-of-work-story-map.md](../../../inception/units-generation/unit-of-work-story-map.md)

---

| Regra | Detalhe |
|---|---|
| BR-PUB-01 | `ack-deadline = 600s` — jobs de longa duração precisam de deadline generoso |
| BR-PUB-02 | `max-delivery-attempts = 5` — após 5 tentativas, mensagem vai para dead-letter |
| BR-PUB-03 | Dead-letter topic `content-pipeline.dead-letter` — alertas configurados no Cloud Monitoring |
| BR-PUB-04 | Mensagens são idempotentes — consumidor verifica estado no Firestore antes de processar |
| BR-PUB-05 | Cloud Scheduler dispara às 21:00 UTC (18:00 BRT) por padrão — configurável por tenant |
| BR-PUB-06 | Service account `pipeline-jobs-sa` tem apenas as permissões mínimas necessárias |
