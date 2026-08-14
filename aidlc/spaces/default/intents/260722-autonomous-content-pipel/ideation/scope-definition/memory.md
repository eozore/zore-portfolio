<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is maintained by the orchestrator during stage execution. Add observations at the gate ritual, not by editing here directly.

## Interpretations

- 2026-07-22T15:20:00Z — Interpretei "enterprise scope" como justificado pela complexidade técnica (5 Bolts, 35+ capacidades, 6 integrações externas), não pela escala de usuários. O backlog foi dimensionado para um único operador (Victor) mas com a robustez necessária para operar sem intervenção técnica.

- 2026-07-22T15:20:00Z — Separei "carrosseis/image posts" (Bolt 5) de "vídeo vertical/horizontal" (Bolts 1-3) porque requerem geração de imagens — um problema técnico diferente (não é vídeo, é design estático). O Distribution Agent já gera o conteúdo escrito; a publicação visual requer um Image Generation Service que pode ser adicionado ao Bolt 5.

## Deviations

- 2026-07-22T15:20:00Z — Não incluí perguntas de priorização para Victor neste estágio porque as respostas já foram capturadas nos estágios anteriores (intent-capture Q4, Q5, Q7). Gerar perguntas redundantes desperdiçaria tempo. O backlog reflete exatamente as decisões tomadas.

- 2026-07-22T15:20:00Z — B5-05 (YouTube Shorts) está no Bolt 5 como Must Have, mas tecnicamente usa o mesmo arquivo do Bolt 2 (vídeo vertical). Movi para Bolt 5 porque a publicação como Short usa o YouTube Publisher (Bolt 3) com parâmetros diferentes — não é uma capacidade de edição, é de publicação.

## Tradeoffs

- 2026-07-22T15:20:00Z — Considerei separar o Config Service como microserviço próprio (Cloud Run) em vez de aba no CSM Studio. Decisão: aba no CSM Studio é mais simples, mantém tudo integrado na mesma interface que Victor já usa, e evita o overhead de um deployment separado para um serviço de configuração que é chamado raramente.

- 2026-07-22T15:20:00Z — Bolt 1 como "Walking Skeleton" valida os dois riscos mais altos (ElevenLabs clone qualidade + HeyGen v3 custo real). Se o Bolt 1 falhar em qualquer um desses pontos, o plano inteiro precisa ser revisto antes de construir os Bolts seguintes. Essa é a decisão de sequenciamento mais importante do backlog.

## Open questions

- 2026-07-22T15:20:00Z — B4-01: painel de configuração como nova aba no CSM Studio ou nova página (route) dedicada? Aba é mais rápido de implementar; página dedicada é mais limpa para um painel com múltiplos parâmetros por canal. Decidir em application-design.

- 2026-07-22T15:20:00Z — B5-01/B5-02: carrosseis e image posts requerem geração de imagem (Imagen/DALL-E/Gemini) ou são apenas texto com design template? Se for design template HTML renderizado via Playwright, cai no mesmo pipeline do video editor. Se for geração de imagem com IA, é um componente separado. Decidir em requirements-analysis.

<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
