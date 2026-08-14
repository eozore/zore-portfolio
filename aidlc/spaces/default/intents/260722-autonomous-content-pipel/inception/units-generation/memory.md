<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is maintained by the orchestrator during stage execution. Add observations at the gate ritual, not by editing here directly.

## Interpretations

- 2026-07-22T17:28:02Z — Units geradas por deployment target + feature cohesion. 13 unidades em vez das 14 originais (C-01 a C-14) porque algumas unidades agrupam múltiplos componentes coesos (ex: U-05 agrupa C-01+C-03+C-04 que sempre evoluem juntos) e U-01 é novo (schema centralizado não tinha componente explícito no application-design).

- 2026-07-22T17:28:02Z — Decisão pós-review: canal Blog em U-12 passa a usar Firestore Admin SDK Python diretamente em vez de chamar o Route Handler Next.js. Isso elimina o acoplamento HTTP entre serviços de tecnologias diferentes e a questão de autenticação serviço-a-serviço. A dependência U-12 → U-03 foi removida do DAG.

## Deviations

- 2026-07-22T17:28:02Z — O stage diz "Stage 2.7 NÃO deve recomendar ordem de implementação". Os "Conjuntos de Paralelismo" descrevem topologia (o que pode rodar em paralelo dado o DAG), não prioridade de implementação. A ordem econômica é de 2.8.

## Tradeoffs

- 2026-07-22T17:28:02Z — U-12 canal Blog via Firestore vs. via Route Handler: escolhida Opção B (Firestore direto) do reviewer. Custo: o PublisherService Python precisa importar e usar o Firebase Admin SDK para escrever no Firestore — já é uma dependência existente via U-07. Benefício: elimina acoplamento de disponibilidade e autenticação serviço-a-serviço.

## Open questions

- (a tech debt do `/lipsync_index` para substituir a `collection_group` query em U-10 foi registrada como observação de baixa prioridade pelo reviewer — pode ser adicionada ao backlog de Bolt 2)

<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
