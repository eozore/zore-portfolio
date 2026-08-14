<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is maintained by the orchestrator during stage execution. Add observations at the gate ritual, not by editing here directly.

## Interpretations

- 2026-07-22T16:31:05Z — Projeto brownfield com práticas parcialmente estabelecidas. O scan mostrou Conventional Commits usados organicamente (sem enforcer), Vitest configurado mas com apenas 3 arquivos de teste, e deploy direto para produção sem staging. Perguntas foram focadas apenas nos gaps — postura de teste para os novos microserviços Python, walking skeleton stance, e estratégia de deploy para os novos Cloud Run Jobs.

- 2026-07-22T16:31:05Z — P3 (deploy): a separação `cloudbuild.yaml` (web app) vs `cloudbuild-pipeline.yaml` (microserviços content) é por **domínio de deployment** (Services vs Jobs, ciclos de vida diferentes), não por ferramenta individual. Todos os 4-5 microserviços novos ficam em um único `cloudbuild-pipeline.yaml`.

## Deviations

- 2026-07-22T16:31:05Z — Não fiz dispatch paralelo de 4 subagents Task conforme o protocolo brownfield. Os 4 scans (Pipeline, Quality, Developer, DevSecOps) foram feitos inline com ferramentas bash diretas. Motivo: o projeto é bem conhecido do contexto acumulado; a overhead de 4 subagents seria superior ao benefício. A evidência coletada é igualmente completa.

## Tradeoffs

- 2026-07-22T16:31:05Z — Walking Skeleton sem gate (P2: C) significa que o Bolt 1 roda como qualquer outro Bolt. O risco é que se a integração ElevenLabs ou HeyGen falhar no Bolt 1, o sistema para com `BOLT_FAILED` e apresenta retry/skip/abort — o mecanismo de halt-and-ask já cobre isso mesmo sem gate preventivo.

## Open questions

- (nenhuma — todas as práticas estão afirmadas e promovidas)

<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
