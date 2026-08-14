# Units Generation — Decisões de Decomposição
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Referências: [components.md](../application-design/components.md) | [component-methods.md](../application-design/component-methods.md) | [services.md](../application-design/services.md) | [component-dependency.md](../application-design/component-dependency.md) | [decisions.md](../application-design/decisions.md) | [requirements.md](../requirements-analysis/requirements.md) | [stories.md](../user-stories/stories.md)

---

### UQ1. Estratégia de boundary das unidades

[Answer]: Por deployment target + feature cohesion. Cada unidade = um Cloud Run Service/Job OU um conjunto coeso de componentes frontend que podem ser desenvolvidos e testados juntos. Isso alinha com a estrutura de Bolts definida no scope-definition.

### UQ2. Granularidade

[Answer]: Médio-grossa. Unidades são deployáveis independentemente e testáveis com 1-3 testes Nyquist. Evitar granularidade ultra-fina (um componente por unidade = 14 unidades sem valor incremental real).

### UQ3. Paralelismo

[Answer]: Maximizar paralelismo onde as dependências permitem. Frontend (ProjectsTab, PipelineTab) pode ser desenvolvido em paralelo com Backend Jobs se o schema Firestore estiver definido (como está). Cada Job Python é independente dos outros no código, mas sequencial na execução da pipeline.

### UQ4. Contrato de integração

[Answer]: Schema Firestore (interaction-spec seção 5) e mensagens Pub/Sub (services.md) são os contratos. Cada unidade valida contra esses contratos nos seus testes Nyquist.
