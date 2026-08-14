# Scope Definition — Registro de Decisões
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Derivado dos estágios anteriores. Decisões confirmadas pelo contexto acumulado.

---

### S1. Sequenciamento de entrega

Qual critério de sequenciamento priorizar?

A. **Risk-first** — resolver primeiro as integrações mais incertas (HeyGen v3, ElevenLabs clone)
B. **Value-first** — entregar primeiro o que desbloqueia uso real mais rápido
C. **Dependency-first** — seguir a ordem natural do pipeline (manifesto → TTS → avatar → editor → publisher)
D. Outro

[Answer]: C+A — dependency-first com ajuste risk-first: seguir a ordem do pipeline mas resolver as integrações de maior risco (ElevenLabs clone + HeyGen Lipsync v3) no primeiro Bolt para validar o fluxo end-to-end antes de construir o restante.

---

### S2. O que é hard deadline?

Alguma capacidade tem data limite por razão externa?

[Answer]: HeyGen v2 descontinua outubro/2026 — migração para v3 deve ser feita antes disso. Fora isso, sem hard deadlines.

---

### S3. O que está fora do escopo desta entrega?

[Answer]: Multi-tenancy (plataforma SaaS para outros criadores), monetização do conteúdo, análise de performance/métricas de crescimento de canal, geração de thumbnails automatizada, integração com TikTok, automação de respostas a comentários.
