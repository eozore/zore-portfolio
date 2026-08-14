# Application Design — Decisões Arquiteturais
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Referências: [requirements.md](../requirements-analysis/requirements.md) | [stories.md](../user-stories/stories.md) | [team-practices.md](../practices-discovery/team-practices.md)

---

### Q1. OQ-03: Painel de configuração como aba ou rota dedicada?

[Answer]: Aba no `CsmDashboard` (ActiveTab 'pipeline'). Razão: mantém o padrão existente do CSM Studio, sem mudança de routing Next.js, menos overhead de uma nova página com seu próprio layout. O painel de configuração é visitado raramente — uma vez por semana na melhor das hipóteses — não justifica rota dedicada.

### Q2. OQ-07/OQ-08: Cloud Scheduler + throttler multi-canal

[Answer]: O Scheduler executa por projeto, não por canal. Comportamento quando throttler de um canal está no limite:
- O project é publicado nos canais disponíveis (sem throttler)
- Os canais com throttler recebem `status: "throttled"` no Firestore
- O projeto NÃO move para `published` até que todos os canais obrigatórios tenham publicado OU sejam marcados como `throttled_skip` por Victor no side panel
- Um segundo job do Scheduler no dia seguinte re-tenta os canais throttled
- Se o projeto tem apenas canais opcionais throttled, move para `published` mesmo assim

### Q3. Carrosseis e image posts: template HTML ou Gemini Imagen?

[Answer]: Template HTML renderizado por Playwright no mesmo pipeline do video editor. Razão: (1) consistência com a pipeline existente; (2) zero custo adicional de API; (3) o manifesto já pode conter um deck de "slides-estáticos" para este formato. Geração de imagem por IA (Imagen) fica para Bolt 5 como upgrade opcional.

### Q4. Localização do Publisher Service — Cloud Run Service ou Job?

[Answer]: Cloud Run Job para publicações batch (scheduled). Cloud Run Service para publicações imediatas via "Publicar Agora" (chamado pelo frontend via endpoint Next.js). Dois modos: Job assíncrono (via Scheduler) e Service síncrono (via POST /publish).
