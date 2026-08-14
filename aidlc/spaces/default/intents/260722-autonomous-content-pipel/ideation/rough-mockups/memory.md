<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is maintained by the orchestrator during stage execution. Add observations at the gate ritual, not by editing here directly.

## Interpretations

- 2026-07-22T15:30:00Z — Rough mockups para um projeto solo com interface existente: focou em wireframes das duas novas telas (abas "Projetos" e "Pipeline") em vez de redesenhar as abas existentes. O CSM Studio existente tem padrões visuais estabelecidos (glassmorphism, dark theme, CSS Modules) que foram estendidos, não redefinidos.

- 2026-07-22T15:30:00Z — A distinção de dois gates de aprovação (aprovar para produção vs. aprovar para publicação) surgiu durante o review como um ponto não tratado originalmente. A Tela 4 (aprovação de produção) e a Tela 4B (aprovação de publicação) são arquiteturalmente distintas e precisam ser documentadas separadamente nos Refined Mockups.

## Deviations

- 2026-07-22T15:30:00Z — O reviewer identificou a necessidade de um endpoint novo na API (`POST /projects/:id/stages/:stage/manual-upload`) que não estava no backlog original. Esse endpoint precisa ser adicionado ao intent-backlog como capacidade do Bolt 4 (fallback manual). Registrado como open question.

## Tradeoffs

- 2026-07-22T15:30:00Z — Side panel vs. modal central para detalhes do projeto: side panel preserva o contexto do kanban (Victor vê o estado geral enquanto trabalha num projeto específico). Modal central seria mais simples de implementar mas destrói o contexto. Side panel é a escolha certa para um usuário solo que gerencia múltiplos projetos simultaneamente.

## Open questions

- 2026-07-22T15:30:00Z — O endpoint de upload manual (`POST /projects/:id/stages/:stage/manual-upload`) precisa ser adicionado ao intent-backlog e ao requirements-analysis. Implica uma rota nova no Next.js + integração com GCS. Garantir que esse endpoint apareça nos requisitos antes da fase de construção.

- 2026-07-22T15:30:00Z — A label `[real]` na Tela 4B deve ser removida no Refined Mockups e substituída pela convenção cromática definida (branco = real, sem prefixo). O `CostMeter.tsx` deve usar essa convenção como token de design.

<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
