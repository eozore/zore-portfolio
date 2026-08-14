# Design System Mapping
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Referências: [wireframes.md](../../ideation/rough-mockups/wireframes.md) | [stories.md](../user-stories/stories.md) | [requirements.md](../requirements-analysis/requirements.md) | [team-practices.md](../practices-discovery/team-practices.md)
> Regra: CSS Modules exclusivamente — sem Tailwind no CSM Studio (constraint C-03).

---

## Tokens de Design

### Cores

```css
/* tokens definidos em apps/web/src/app/globals.css ou vars.module.css */

/* Superfície */
--surface-card: rgba(255,255,255,0.04);
--surface-modal: rgba(18,18,27,0.95);
--surface-panel: rgba(10,10,20,0.98);

/* Texto */
--text-primary: #f8fafc;
--text-secondary: #94a3b8;
--text-disabled: #475569;
--text-estimated-cost: #f59e0b;  /* âmbar para estimados */
--text-real-cost: #f8fafc;       /* branco para reais */

/* Accent */
--accent-violet: #7c3aed;
--accent-cyan: #06b6d4;
--accent-gradient: linear-gradient(135deg, #7c3aed 0%, #06b6d4 100%);

/* Status */
--status-creating: #3b82f6;
--status-awaiting: #f59e0b;
--status-generating: #8b5cf6;
--status-ready: #06b6d4;
--status-published: #10b981;
--status-error: #ef4444;
--status-publishing: #8b5cf6;

/* Border */
--border-default: rgba(255,255,255,0.08);
--border-hover: rgba(124,58,237,0.4);
--border-focus: #7c3aed;

/* Cost meter */
--cost-normal-start: #7c3aed;
--cost-normal-end: #06b6d4;
--cost-alert-start: #f59e0b;
--cost-alert-end: #f97316;
--cost-exceeded-start: #ef4444;
--cost-exceeded-end: #dc2626;
```

### Tipografia

```css
/* Hierarquia nos novos componentes */
h1 { font-size: 1.5rem; font-weight: 700; }   /* Título da aba "Projetos" */
h2 { font-size: 1.25rem; font-weight: 600; }  /* Título de modal/panel */
h3 { font-size: 0.875rem; font-weight: 600; } /* Título do card */

.status-badge {
  font-size: 0.6875rem;  /* 11px */
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.cost-label {
  font-size: 0.75rem;    /* 12px */
  font-variant-numeric: tabular-nums; /* alinhamento em colunas */
}

.meta-text {
  font-size: 0.6875rem;  /* 11px */
  color: var(--text-secondary);
}
```

### Espaçamento

```css
/* Grid de 4px */
--space-1: 4px;
--space-2: 8px;
--space-3: 12px;
--space-4: 16px;
--space-5: 20px;
--space-6: 24px;
--space-8: 32px;
--space-10: 40px;
```

### Efeitos Visuais

```css
.glassmorphism {
  background: var(--surface-card);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--border-default);
  border-radius: 12px;
}

.pulse {
  animation: pulse 2s cubic-bezier(0.4,0,0.6,1) infinite;
}
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }
```

---

## Mapeamento de Componentes Existentes → Novos

| Componente Existente | Padrão Reutilizável | Novos Componentes que Herdam |
|---|---|---|
| `IdeaTab.module.css` — `.chatContainer` | Layout de painel com scroll | `ProjectDetailPanel` — estrutura geral |
| `RepurposeTab.module.css` — cards de status | Status badges coloridos | `ProjectCard` — badges de estado |
| `SettingsTab.module.css` — campos de configuração | Form fields com labels | `ApiKeyField`, `ChannelToggle` |
| `GenerateTab.module.css` — progress indicator | Loading states | `PipelineProgress` — estados de job |
| `TelemetryTab.module.css` — métricas numéricas | Tabular nums, gauge | `CostMeter` — barra de progresso |

---

## Novos Arquivos CSS Modules a Criar

```
apps/web/src/components/csm/
  ProjectCard.module.css
  ProjectDetailPanel.module.css
  ApprovalModal.module.css     ← compartilhado por ApprovalModal e PublishModal
  ApiKeyField.module.css
  CostMeter.module.css
  PipelineProgress.module.css
  ChannelToggle.module.css

apps/web/src/components/csm/tabs/
  ProjectsTab.module.css
  PipelineTab.module.css
```

---

## Breakpoints Responsivos

```css
/* Mobile-first dentro dos CSS Modules */
.grid {
  display: grid;
  grid-template-columns: 1fr;          /* mobile: 1 coluna */
  gap: var(--space-4);
}

@media (min-width: 768px) {            /* tablet */
  .grid { grid-template-columns: repeat(2, 1fr); }
}

@media (min-width: 1024px) {           /* desktop */
  .grid { grid-template-columns: repeat(4, 1fr); }
}

/* Side Panel: drawer em desktop, bottom sheet em mobile */
.sidePanel {
  position: fixed;
  right: 0;
  top: 64px;
  width: 400px;
  height: calc(100vh - 64px);
}

@media (max-width: 768px) {
  .sidePanel {
    width: 100%;
    top: auto;
    bottom: 0;
    height: 80vh;
    border-radius: 16px 16px 0 0;
  }
}
```

---

## Convenção de Nomes de Classes (CSS Modules)

```
.container    — wrapper raiz do componente
.header       — seção de cabeçalho
.body         — conteúdo principal
.footer       — ações/botões (sempre no bottom)
.badge        — badges de estado inline
.badgePulse   — badge com animação de pulse
.stage        — item individual de pipeline stage
.stageIcon    — ícone do stage (check/spinner/x)
.stageLabel   — texto do stage
.stageCost    — custo do stage
.meter        — barra de progresso do CostMeter
.meterFill    — preenchimento da barra
.meterText    — texto "R$XX / R$YY"
```
