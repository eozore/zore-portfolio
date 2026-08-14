# Refined Mockups — Decisões de Design
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Referências: [wireframes.md](../../ideation/rough-mockups/wireframes.md) | [user-flow.md](../../ideation/rough-mockups/user-flow.md) | [stories.md](../user-stories/stories.md) | [requirements.md](../requirements-analysis/requirements.md) | [team-practices.md](../practices-discovery/team-practices.md)

---

### D1. Representação de estados de loading nos jobs

[Answer]: Skeleton loaders com shimmer animado (CSS animation) nos cards enquanto o Firestore listener aguarda o primeiro dado. Spinner inline por etapa no side panel quando o job está processando. Sem spinners globais que bloqueiam toda a UI.

### D2. Padrão de notificações em tempo real

[Answer]: Toast notifications no canto inferior direito para eventos críticos (job completado, erro, custo atingindo 80%). Duração 5s com dismiss manual. Não modal — Victor pode continuar trabalhando. Cores: verde (sucesso), âmbar (alerta), vermelho (erro).

### D3. Responsive breakpoints

[Answer]: Desktop-first. Breakpoints: lg (≥1024px) = grid 4 colunas; md (≥768px) = grid 2 colunas; sm (<768px) = grid 1 coluna. Side panel: em desktop ocupa 400px fixo à direita; em mobile torna-se bottom sheet de 80vh. Modais: sempre centralizados, max-width 560px, 100% em mobile.

### D4. WCAG target

[Answer]: WCAG 2.1 AA. Contraste mínimo 4.5:1 no texto. Todos os controles interativos atingíveis por teclado com outline visível roxo (#7c3aed, 2px).
