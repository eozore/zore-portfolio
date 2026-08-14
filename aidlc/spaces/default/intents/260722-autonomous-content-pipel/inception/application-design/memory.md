<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is maintained by the orchestrator during stage execution. Add observations at the gate ritual, not by editing here directly.

## Interpretations

- 2026-07-22T17:16:35Z — A decisão de usar `collection_group('lipsync_jobs')` para resolver `lipsync_id → project_id` no Firestore requer um índice composto. Firestore Collection Group queries exigem índice explícito no `firestore.indexes.json`. Isso precisa ser documentado nas units do C-14.

- 2026-07-22T17:16:35Z — O Firestore não tem operador `OR` em queries. Para buscar por `lipsync_id == X` nos campos horizontal.lipsync_id OR vertical.lipsync_id, a query mais simples é usar `collection_group` no subcampo. Alternativa: fazer duas queries e combinar. Collection_group é mais limpo mas requer índice.

## Deviations

- 2026-07-22T17:16:35Z — AWS Platform Agent foi adaptado para GCP. Os princípios de Well-Architected foram aplicados (IAM, custo, operabilidade) mas com os serviços GCP equivalentes: Cloud Run = Lambda/ECS, Pub/Sub = SQS/SNS, Firestore = DynamoDB, Secret Manager = Secrets Manager.

## Tradeoffs

- 2026-07-22T17:16:35Z — Imagem Docker unificada vs. imagens separadas: escolha foi unificada para simplicidade operacional (1 build, 1 YAML, 1 requirements.txt). O custo é uma imagem maior (~2GB disco), mas o VideoEditorJob de qualquer forma precisaria de Playwright+FFmpeg. A memória de runtime foi corrigida para 4GB para o VideoEditorJob especificamente.

- 2026-07-22T17:16:35Z — Publisher com dois modos (Job + Service) é a decisão mais interessante: Cloud Run Jobs têm startup overhead de ~10s, inaceitável para "Publicar Agora". Mas usar apenas Service desperdiçaria recursos com instância idle. A solução dual é o melhor dos dois mundos — com o custo de manter dois endpoints para o mesmo código.

## Open questions

- (todas as questões abertas foram resolvidas nos ADRs: OQ-03=ADR-06, OQ-07/OQ-08=ADR-07, OQ-04=ADR-09, Finding 1=ADR-03 schema, Finding 3=ADR-04 env var)

<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
