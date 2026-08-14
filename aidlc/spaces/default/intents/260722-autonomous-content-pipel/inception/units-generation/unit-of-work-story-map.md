# Unit of Work Story Map
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Referências: [components.md](../application-design/components.md) | [component-methods.md](../application-design/component-methods.md) | [services.md](../application-design/services.md) | [component-dependency.md](../application-design/component-dependency.md) | [decisions.md](../application-design/decisions.md) | [requirements.md](../requirements-analysis/requirements.md) | [stories.md](../user-stories/stories.md)

---

## Mapa de Histórias por Unidade

| User Story | Unidade(s) Implementadora(s) | Notas |
|---|---|---|
| US-01 — Criar projeto de conteúdo | U-03 (projects-api), U-05 (projects-tab-ui) | API cria o projeto; UI exibe o botão |
| US-02 — Visualizar projetos em kanban | U-05 (projects-tab-ui), U-01 (schema) | Card + filtros + grid |
| US-03 — Ver detalhes de um projeto | U-05 (projects-tab-ui), U-01 (schema) | ProjectDetailPanel com listener Firestore |
| US-04 — Aprovar pacote para produção | U-06 (pipeline-tab-ui/ApprovalModal), U-03 (projects-api/approve) | Modal + endpoint de aprovação |
| US-05 — Aprovar e agendar publicação | U-06 (pipeline-tab-ui/PublishModal), U-03 (projects-api/publish) | Modal + endpoint de publicação |
| US-06 — Monitorar progresso em tempo real | U-05 (projects-tab-ui), U-01 (schema Firestore listener) | Listener com SLA ≤ 3s |
| US-07 — Recuperar de falha de job | U-05 (projects-tab-ui), U-03 (retry/skip/upload) | Side panel + 3 endpoints de fallback |
| US-08 — Publicar no YouTube com AI disclosure | U-12 (publisher-service) | YouTube Data API v3 |
| US-09 — Publicar em Instagram, Shorts, Threads, LinkedIn | U-12 (publisher-service) | Meta Graph API + LinkedIn API |
| US-10 — Publicação agendada automática | U-12 (publisher-service), U-02 (Cloud Scheduler) | Modo Job + Scheduler |
| US-11 — Configurar canais de publicação | U-06 (pipeline-tab-ui), U-04 (config-api) | PipelineTab + ConfigService |
| US-12 — Gerenciar limites de custo | U-06 (pipeline-tab-ui), U-07 (CostTrackerService) | UI config + CostTracker backend |
| US-13 — Visualizar agenda de publicações | U-06 (pipeline-tab-ui), U-04 (config-api) | ScheduleEditor na PipelineTab |
| US-14 — Retry automático em falhas transitórias | U-07 (pipeline-shared-lib/retry), U-08/U-09/U-10/U-11 (aplicam retry) | Shared lib + cada Job |
| US-15 — YouTube OAuth com refresh automático | U-04 (config-api/youtube-oauth), U-12 (publisher-service) | Fluxo OAuth + refresh no publish |
| US-16 — Publicar artigo no blog | U-12 (publisher-service), U-03 (projects-api/publish existente) | Publisher chama rota existente |

---

## Histórias Cross-Cutting (span múltiplas unidades)

**US-04 e US-07** — A experiência de aprovação e recuperação envolve tanto UI (U-05/U-06) quanto API (U-03). O contrato entre UI e API é definido pelas interfaces TypeScript dos modais em `refined-mockups/mockups.md`.

**US-06** — "Monitorar em tempo real" não é uma feature de uma única unidade: depende de U-05 (UI com listener) + U-07/U-08/U-09/U-10/U-11 (Jobs que escrevem no Firestore). O SLA de ≤ 3s é end-to-end.

**US-14** — Retry automático atravessa U-07 (módulo de retry) e todas as 4 unidades de Jobs (U-08 a U-11). O módulo é implementado uma vez em U-07 e consumido pelas demais.

---

## Cobertura de Requisitos por Unidade

| Unidade | FRs Cobertos | NFRs Relevantes |
|---|---|---|
| U-01 | FR-01 a FR-12 (schema base) | NFR-09 (idempotência) |
| U-02 | FR-03, FR-04, FR-05, FR-06, FR-11 (mensageria) | NFR-05 (disponibilidade) |
| U-03 | FR-01, FR-02, FR-07, FR-09 | NFR-03 (segurança), NFR-06 (testabilidade) |
| U-04 | FR-08, FR-12 | NFR-03 (Secret Manager) |
| U-05 | FR-01 (UI), FR-09 (fallback UI) | NFR-07 (observabilidade) |
| U-06 | FR-02, FR-07, FR-08 (UI) | NFR-07 (observabilidade) |
| U-07 | FR-10 (CostTracker), FR-11 (retry) | NFR-01 (custo), NFR-09 (idempotência) |
| U-08 | FR-03 (TTS) | NFR-02 (latência), NFR-11 (retry) |
| U-09 | FR-04 (Avatar) | NFR-02 (latência HeyGen) |
| U-10 | FR-04 (callback HeyGen) | NFR-02 (timeout) |
| U-11 | FR-05 (Video Editor) | NFR-05 (memória 4GB) |
| U-12 | FR-06 (Publisher) | NFR-04 (AI disclosure), NFR-08 (APIs oficiais) |
| U-13 | — (infra) | NFR-10 (portabilidade) |

---

## Verificação de Completude

**Todas as 16 US têm pelo menos uma unidade implementadora:** ✅

**Todas as 13 unidades têm pelo menos uma US:** ✅
- U-01: base de todas as US
- U-02: US-10 (Scheduler) + infraestrutura de mensageria
- U-03: US-01, 04, 05, 07
- U-04: US-11, 12, 13, 15
- U-05: US-02, 03, 06, 07
- U-06: US-04, 05, 11, 12, 13
- U-07: US-14 (retry compartilhado)
- U-08: US-14 (usa retry)
- U-09: US-14 (usa retry)
- U-10: US-09 (resultado de publicação do avatar)
- U-11: US-06 (geração de vídeo)
- U-12: US-08, 09, 10, 16
- U-13: infra que habilita U-08 a U-12

**Todos os FRs Must Have têm cobertura de unidade:** ✅ (FR-01 a FR-12 mapeados acima)
