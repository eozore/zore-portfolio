# Rough Mockups — Registro de Decisões de Design
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Derivado do código existente do CSM Studio + decisões dos estágios anteriores.
> Referências: [intent-statement.md](../intent-capture/intent-statement.md) | [scope-document.md](../scope-definition/scope-document.md) | [intent-backlog.md](../scope-definition/intent-backlog.md)

---

### D1. Onde ficam as novas telas no CSM Studio?

[Answer]: Duas novas abas no `CsmDashboard.tsx`:
1. **"Projetos"** (`ActiveTab: 'projects'`) — kanban de pacotes de conteúdo
2. **"Pipeline"** (`ActiveTab: 'pipeline'`) — painel de configuração de canais, keys e horários

---

### D2. Estética e design system

[Answer]: Seguir o design system existente: dark background (#0a0a0a), glassmorphism nos cards (backdrop-filter blur, borda translúcida), CSS Modules (sem Tailwind), cores accent roxo/violeta (#7c3aed) e ciano (#06b6d4).

---

### D3. Acessibilidade

[Answer]: WCAG 2.1 AA. Navegação por teclado em todos os controles. Contraste mínimo 4.5:1 no texto. ARIA labels em status badges e botões de ação.

---

### D4. Dispositivos

[Answer]: Desktop-first (Victor usa no computador de trabalho). Mobile-friendly para revisão rápida do kanban.
