<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is maintained by the orchestrator during stage execution. Add observations at the gate ritual, not by editing here directly.

## Interpretations

- 2026-07-22T15:10:00Z — Adaptei a perspectiva do AWS Platform Agent para GCP — o projeto é 100% GCP-first, não AWS. A análise de infraestrutura seguiu os mesmos princípios (Well-Architected equivalente no GCP, IAM, Secret Manager) mas com os serviços corretos do Google Cloud.

- 2026-07-22T15:10:00Z — A descoberta mais crítica do estágio: o fluxo correto não é HeyGen gerando áudio a partir do texto — é ElevenLabs gerando o áudio e o HeyGen Lipsync API recebendo o áudio externo para sincronizar o avatar. Isso resolve o problema de voz e naturalidade ao mesmo tempo. A HeyGen Lipsync API v3 (`POST /v3/lipsyncs`) aceita `audio.type: "asset_id"` após upload via Assets API — confirmado via documentação oficial.

## Deviations

- 2026-07-22T15:10:00Z — Não incluí análise de conformidade SOC2/PCI/HIPAA. O projeto não processa dados financeiros nem de saúde, e opera como ferramenta interna de um criador solo (não SaaS). O único framework regulatório relevante é LGPD (dados biométricos: voz clonada do Victor) e as políticas das plataformas sociais. Foquei nessas duas dimensões.

## Tradeoffs

- 2026-07-22T15:10:00Z — Cloud Run Jobs vs. Cloud Run Services para TTS/Avatar/Editor: Jobs são a escolha certa para processos de longa duração (até 24h de timeout vs. 60 min dos Services). O timeout de renderização HeyGen (potencialmente 45+ min) exige Jobs, não Services.

- 2026-07-22T15:10:00Z — Polling vs. Webhook para HeyGen: HeyGen v3 Lipsync API suporta `callback_url` para notificação quando renderização completa. Usar callback é mais elegante que polling mas requer URL pública do Publisher Service. Como Cloud Run Services têm URL pública, usar callback do HeyGen é a abordagem correta — evita polling a cada 30s por até 45 min.

## Open questions

- 2026-07-22T15:10:00Z — Issue I01: confirmar custo real da HeyGen Lipsync API v3 PAYG. A documentação de enterprise pricing indica $0.05/sec para Photo Avatar — se for o mesmo para Lipsync, 15 min de vídeo = 900s × $0.05 = $45, o que ultrapassaria o teto. Precisa ser verificado antes de commitar à arquitetura de custo.

- 2026-07-22T15:10:00Z — Issue I03: HeyGen Lipsync API — melhor qualidade com avatar foto estática ou vídeo loop? Foto é mais simples mas pode ter lip-sync menos natural em expressões. Vídeo loop (avatar andando/respirando) tende a ser mais natural. Testar antes de decidir o formato do avatar base.

<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
