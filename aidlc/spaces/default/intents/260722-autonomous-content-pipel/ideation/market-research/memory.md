<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is maintained by the orchestrator during stage execution. Add observations at the gate ritual, not by editing here directly.

## Interpretations

- 2026-07-22T14:30:00Z — Este estágio tem foco em build-vs-buy, não em competição de mercado. O éozoré não compete no mercado de ferramentas de conteúdo — usa essas ferramentas como insumo. Reorientei a análise para justificar as decisões de fornecedor e parceria.

- 2026-07-22T14:30:00Z — Os preços do HeyGen API pay-as-you-go foram estimados com base no plano Creator (600 créditos = 30 min de Avatar IV ≈ $29/mês → ~$0.96/min). Os preços reais da API PAYG podem diferir — flag para confirmar no feasibility com uma chamada de teste.

## Deviations

- 2026-07-22T14:30:00Z — Não fiz perguntas ao Victor neste estágio. O intent-statement tinha informação suficiente para conduzir a análise de mercado via pesquisa direta. Perguntar sobre "quais concorrentes existem" seria desperdício de tempo para um criador solo que já conhece o mercado de ferramentas de IA. Desviei para pesquisa proativa.

## Tradeoffs

- 2026-07-22T14:30:00Z — Metricool como fallback de publicação: poderia ser a solução permanente (grátis, cobre todas as redes). Rejeitado como permanente porque adiciona dependência de terceiro sem SLA, remove controle do fluxo de aprovação e aumenta complexidade de debugging quando publicações falham. O custo de construir o Publisher Service é justificado pelo controle que traz.

- 2026-07-22T14:30:00Z — Google Chirp 3 HD ($0.03/1k chars) vs ElevenLabs ($0.05/1k chars): Chirp não tem clone de voz do Victor, tornando-o inadequado como primário. Como fallback, é útil se ElevenLabs ficar indisponível. A diferença de custo ($0.30 por vídeo) é insignificante dado o teto de R$100.

## Open questions

- 2026-07-22T14:30:00Z — Confirmar no feasibility: preço exato da HeyGen API PAYG por segundo de vídeo Avatar IV. O cálculo atual é estimativa baseada nos planos de assinatura, não nos preços API reais.

- 2026-07-22T14:30:00Z — ElevenLabs Professional Voice Clone (disponível a partir do plano Creator a $22/mês) vs Instant Voice Clone (disponível a partir do Starter $5/mês): qual a diferença de qualidade perceptível para pt-BR? Impacta decisão de plano.

<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
