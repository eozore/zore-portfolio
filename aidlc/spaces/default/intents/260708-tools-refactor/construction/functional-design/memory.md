# Stage Memory — Functional Design

## Interpretations

- 2026-07-08T12:35:00Z — Escopo refactor sem units-generation prévia. Tratando como unit única "video-editor-api" que cobre o pipeline inteiro.
- 2026-07-08T12:35:30Z — Os artefatos consumes de inception (units-generation, application-design) foram skipped pelo scope refactor. Derivando o design funcional diretamente dos requirements aprovados.
- 2026-07-08T12:36:00Z — O sistema tem dois outputs (horizontal + vertical) que compartilham STT/alignment mas divergem no render. O design deve refletir isso como dois branches do pipeline, não dois pipelines separados.

## Deviations

- 2026-07-08T12:36:30Z — Stage é `for_each: unit-of-work` mas sem unit-of-work.md disponível (skipped). Produzindo artefatos para uma unidade implícita "video-editor-api" cobrindo o refactor completo.

## Tradeoffs

- 2026-07-08T12:37:00Z — Pipeline modular vs monolítico: escolhendo modular (cada step isolado) para facilitar swap de providers (ex: trocar GCP STT por Whisper) sem afetar o resto. Trade-off: mais files, mais interfaces, mas muito mais testável e manutenível.
- 2026-07-08T12:37:30Z — Async com WebSocket vs polling: WebSocket permite UX mais rica (progresso em tempo real) mas adiciona complexidade de infra. Escolhendo WebSocket por ser requisito explícito do usuário.

## Open questions

