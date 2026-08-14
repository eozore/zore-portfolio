<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is maintained by the orchestrator during stage execution. Add observations at the gate ritual, not by editing here directly.

## Interpretations

- 2026-07-22T17:34:38Z — Walking Skeleton stance: team.md confirma "sem gates inter-Bolt, exceto falhas" → `Construction Autonomy Mode: autonomous`. O Bolt 1 é o Walking Skeleton mas não requer gate especial além do Go/No-Go de custo.

- 2026-07-22T17:34:38Z — Bolt 0 (`foundations`) não está no DAG original de units mas é necessário para não dispersar U-01 e U-02 nos Bolts de feature. São pré-requisitos sem valor incremental direto — um "Bolt 0" é a escolha correta para isolá-los.

## Deviations

- 2026-07-22T17:34:38Z — Bolt 5 (`distribution`) é deliberadamente vago em termos de unidades. As capacidades de Bolt 5 (carrosseis, Community Posts) dependem de APIs não testadas (OQ-05) e de extensões de U-11/U-12 que só serão conhecidas após os Bolts anteriores. Mantido como Bolt intencionalmente aberto — o scope será refinado durante a execução do Bolt 4.

## Tradeoffs

- 2026-07-22T17:34:38Z — U-03 (projects-api) e U-12 (publisher-service) no mesmo Bolt 3 vs. U-03 em Bolt 3 e U-12 em Bolt 4: agrupados porque a hipótese de confiança do Bolt 3 exige que a pipeline completa funcione. U-03 sozinho entrega apenas aprovação sem publicação — isso não valida o valor do Bolt.

## Open questions

- (todas as questões abertas capturadas em `external-dependency-map.md` e `phase-check-inception.md`)

<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
