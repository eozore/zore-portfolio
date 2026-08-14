# Delivery Planning — Decisões de Sequenciamento
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Referências: [requirements.md](../requirements-analysis/requirements.md) | [stories.md](../user-stories/stories.md) | [mockups.md](../refined-mockups/mockups.md) | [components.md](../application-design/components.md) | [unit-of-work.md](../units-generation/unit-of-work.md) | [unit-of-work-dependency.md](../units-generation/unit-of-work-dependency.md) | [unit-of-work-story-map.md](../units-generation/unit-of-work-story-map.md) | [team-practices.md](../practices-discovery/team-practices.md)

---

### DP1. Heurística de sequenciamento

[Answer]: **Risk-first para o Bolt 1 (Walking Skeleton), Value-first para os Bolts seguintes.** Bolt 1 valida as duas integrações de maior risco (ElevenLabs + HeyGen v3) antes de construir qualquer outra coisa. Os Bolts 2-5 maximizam valor entregue por Bolt (funcionalidade que Victor pode usar imediatamente).

### DP2. Granularidade dos Bolts

[Answer]: **Múltiplas units por Bolt**, agrupadas por coesão funcional. Um Bolt entrega uma capacidade end-to-end utilizável. Evitar Bolts que produzem apenas infra sem capacidade visível (exceto o Bolt 0 de fundação que é necessariamente pré-requisito).

### DP3. Parallelismo de Bolts

[Answer]: **Sequencial** (Walking Skeleton section do team.md: "sem gates entre Bolts, exceto falhas"). Victor opera sozinho — não tem benefício real de paralelismo de equipe. Dentro de cada Bolt, unidades independentes podem ser implementadas em paralelo pelo Developer Agent.

### DP4. Dependências externas críticas

[Answer]: ElevenLabs (conta + clone de voz), HeyGen (API key + avatar), YouTube OAuth (canal de Victor no GCP), GCP Pub/Sub API ativada. Todas são pré-condições humanas identificadas no team-formation stage — devem ser configuradas antes do Bolt 1.

### DP5. Riscos prioritários para early resolution

[Answer]: (1) Custo real HeyGen Lipsync API PAYG — validado no Bolt 1 antes de qualquer Bolt de produção; (2) Playwright em Alpine Cloud Run — validado no Bolt 2; (3) YouTube OAuth upload — validado no Bolt 3.
