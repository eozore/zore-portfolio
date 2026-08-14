<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is maintained by the orchestrator during stage execution. Add observations at the gate ritual, not by editing here directly.

## Interpretations

- 2026-07-22T17:05:25Z — Refined mockups = especificações de implementação, não protótipos visuais. Todos os artefatos foram escritos para serem consumíveis diretamente pelo Developer Agent — props TypeScript, CSS classes nomeadas, estados de Firestore, endpoints de API. Não há imagens ou ferramentas de prototipagem envolvidas; tudo é texto estruturado e código.

- 2026-07-22T17:05:25Z — A seção 5 da interaction-spec (Shape Firestore) foi adicionada na iteração 2 por sugestão do reviewer. Esta é a única fonte de verdade do schema que o frontend escuta — um documento crucial que normalmente só aparece no Application Design, mas que foi adiantado aqui por ser diretamente necessário para especificar os componentes.

## Deviations

- 2026-07-22T17:05:25Z — Não segui o template de `component-spec-template.md` do knowledge do Design Agent (mencionado na spec do estágio) porque o template padrão não está disponível no knowledge base. Em vez disso, usei um padrão consistente de: Mapeia, Props TypeScript, Estados visuais, Acessibilidade — que cobre as mesmas dimensões do template.

## Tradeoffs

- 2026-07-22T17:05:25Z — Decidi incluir o schema Firestore completo na interaction-spec (seção 5) em vez de deixar para o Application Design. O tradeoff: adiciona responsabilidade ao Design Agent para algo que é tipicamente domínio do Architect Agent. Justificativa: o `PipelineProgress` não pode ser especificado completamente sem saber o shape do `project.stages[]` — é uma dependência direta. O Application Design pode refiná-lo, mas o esqueleto precisava estar aqui.

## Open questions

- (todas as questões abertas relevantes foram passadas para Application Design nas observações do reviewer — OAuthTokenField vs extensão ApiKeyField, endpoint de renovação OAuth YouTube)

<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
