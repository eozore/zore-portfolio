> This file is maintained by the orchestrator during stage execution. Add observations at the gate ritual, not by editing here directly.

## Interpretations

- 2026-07-22T13:52:53Z — Interpretei "pipeline autônoma" como um sistema onde Victor participa apenas na cocriação intelectual (sessão CMO) e na aprovação final; toda execução técnica (geração de áudio, vídeo, edição, publicação) é automática. Confirmado explicitamente pelo Victor (Q4: D).

- 2026-07-22T13:52:53Z — Interpretei "os mesmos" (Q5) como reuso do mesmo arquivo de vídeo vertical tanto para YouTube Shorts quanto para Instagram Reels — um único processo de renderização vertical serve ambas as plataformas. Não contradito pelo Victor.

- 2026-07-22T13:52:53Z — Interpretei o painel de controle (Q5 adendo) como um microserviço de configuração separado, não uma aba adicional no CSM Studio — dado que precisa de configuração de keys seguras (Secret Manager) e parâmetros por canal que têm lógica própria. A ser confirmado em feasibility.

## Deviations

- 2026-07-22T13:52:53Z — O escopo enterprise normalmente inclui equipes e processos multi-tenant. Aqui desviei: é enterprise pela complexidade técnica (múltiplos microserviços, 6+ integrações, pipeline de vídeo completa), não pela escala de usuários. Victor é o único usuário. Registrado para não gerar over-engineering de multi-tenancy desnecessário nos estágios de design.

- 2026-07-22T13:52:53Z — A decisão de eliminar o Gemini do alignment (Q6) é uma simplificação arquitetural significativa em relação ao `editor_pipeline.py` existente. O manifesto v2 já tem o campo `slide` por segmento — o Gemini alignment era um workaround para a ausência desse contrato. Com o contrato explícito, o pipeline de edição fica determinístico e mais barato.

## Tradeoffs

- 2026-07-22T13:52:53Z — ElevenLabs vs Google TTS: Victor escolheu ElevenLabs (Q3) priorizando naturalidade sobre custo. Tradeoff: ElevenLabs cobra por caractere (~$0.18/1000 chars para Turbo v2.5); um roteiro de 15 min ≈ 15.000 chars ≈ $2.70 só de TTS. Dentro do teto de R$100 (~$20 ao câmbio atual), deixa margem para HeyGen + Gemini + infra. Registrado para o mapeamento de custos no feasibility.

- 2026-07-22T13:52:53Z — Batch semanal (Q7) vs event-driven: Victor preferiu batch. Tradeoff: batch é mais simples de operar e evita custos de infra idle, mas significa que o conteúdo tem latência de até 1 semana entre criação e publicação. Aceitável dado o modelo de agendamento (gera 5-7 pacotes, publica 1/dia).

- 2026-07-22T13:52:53Z — Pub/Sub como barramento vs chamadas diretas entre serviços: Pub/Sub adiciona complexidade de setup mas é a escolha certa para um sistema onde cada etapa tem latência variável (HeyGen pode levar 5-20 min para renderizar um vídeo). Permite que cada microserviço seja independentemente escalável e reprocessável sem re-executar o pipeline inteiro.

- 2026-07-22T13:52:53Z — Aprovação obrigatória antes de publicar (Q4:D) vs autonomia total: Victor escolheu gate de aprovação. Tradeoff: adiciona fricção mas é a decisão certa dado o risco de ban nas plataformas (Q11:C) e a necessidade de manter o padrão técnico da audiência. O sistema deve tornar o gate de aprovação o mais fluido possível (painel kanban com preview inline).

## Open questions

- 2026-07-22T13:52:53Z — Confirmar em feasibility: qual o modelo exato de ElevenLabs para voz clonada do Victor? Eleven Turbo v2.5 é mais barato e adequado para pt-BR; Eleven Multilingual v2 é mais natural mas ~3x mais caro. Decisão impacta o mapeamento de custo por vídeo.

- 2026-07-22T13:52:53Z — Confirmar em feasibility: HeyGen V2 API aceita áudio externo (ElevenLabs) para sincronização labial? Ou o HeyGen gera seu próprio áudio? A resposta define se precisamos de lip-sync separado (SyncLabs/wav2lip) ou se o HeyGen já faz tudo.

- 2026-07-22T13:52:53Z — Confirmar em application-design: o painel de configuração é uma aba do CSM Studio existente (apps/web) ou um microserviço separado com sua própria UI? Victor mencionou "painel de configuração" sem especificar se é integrado ao CSM Studio ou separado.

- 2026-07-22T13:52:53Z — Confirmar em feasibility: YouTube Data API v3 com service account GCP — confirmar que a conta do canal do Victor está associada ao GCP project correto e que os escopos de upload estão habilitados.

- 2026-07-22T13:52:53Z — Definir em requirements-analysis: o que exatamente constitui "conformidade com políticas de IA" para cada plataforma? YouTube tem a política de disclosure de AI-generated content desde 2024; Instagram/Meta idem. Precisa de campo obrigatório de metadata ou label visual no vídeo?
