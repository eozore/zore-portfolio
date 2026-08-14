# Wireframes — Content Studio Bugfixes

## BUG1 — Slide Designer Output (por beat type)

### beat: "teoria" — 1920×1080

```
┌─────────────────────────────────────────────────────────────────┐
│  background: #0d0f14  │  grid sutil laranja 10% opacidade       │
│                                                                  │
│  [fd1 — visível]                                                 │
│  ┌──────────────────────────────────────────────────────┐       │
│  │  SÉRIE IA PARA LÍDERES                               │       │
│  │                                                      │       │
│  │       LoRA = W₀ + ΔW   onde   ΔW = A × B            │       │
│  │                                                      │       │
│  │    A ∈ ℝ^{d×r}        B ∈ ℝ^{r×k}    r << min(d,k) │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                  │
│  [fd2 — display:none, revelado por âncora "duas menores"]       │
│  ┌──────────────────────────────────────────────────────┐       │
│  │  Duas matrizes MENORES em vez de uma GRANDE          │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                  │
│                                              [logo éozoré] ░░░  │
└─────────────────────────────────────────────────────────────────┘
```

### beat: "hook" — 1920×1080

```
┌─────────────────────────────────────────────────────────────────┐
│  background: #0d0f14                                             │
│                                                                  │
│         ┌─────────────────────────────────────────┐             │
│         │                                         │             │
│         │            1%                           │             │
│         │   ────────────────────────────          │             │
│         │   dos parâmetros originais              │             │
│         │                                         │             │
│         │   MESMO resultado de fine-tuning        │             │
│         │   completo com 100%                     │             │
│         └─────────────────────────────────────────┘             │
│                                                              ░░░ │
└─────────────────────────────────────────────────────────────────┘
```

### beat: "demo" — barras comparativas

```
┌─────────────────────────────────────────────────────────────────┐
│  COMPARATIVO DE CUSTO DE FINE-TUNING                             │
│                                                                  │
│  Full Fine-Tuning  [██████████████████████████████] $2,400/h    │
│  LoRA              [████] $48/h                                  │
│  QLoRA             [██] $12/h                                    │
│                                                                  │
│  [b1, b2, b3 — revelados por âncoras]                           │
│                                                              ░░░ │
└─────────────────────────────────────────────────────────────────┘
```

## BUG3 — Artigo com gráfico (antes/depois)

**Antes (quebrado):**
```tsx
// RichArticleRenderer tentava parsear código Python com regex
// → InteractiveChart component → erro silencioso
<InteractiveChart code="import matplotlib..." />
```

**Depois (correto):**
```tsx
// code_executor.py salva PNG no GCS e retorna:
// "![grafico_comparativo](https://storage.googleapis.com/vazfy.../plot_abc123.png)"
// RichArticleRenderer renderiza como:
<img src="https://storage.googleapis.com/vazfy.../plot_abc123.png" 
     alt="grafico_comparativo" 
     className="w-full rounded-lg" />
```

## BUG6 — Campo tipo_artigo na pauta (UI mínima)

```
CsmDashboard IdeaTab (chat CMO)
  ┌──────────────────────────────────────────────────────┐
  │  Pauta definida:                                     │
  │    Título: "LoRA: Fine-Tuning Eficiente..."          │
  │    Tipo: [tecnico ▼]  ◄── novo badge/tag             │
  │    Público: "Líderes de IA..."                       │
  │    ...                                               │
  └──────────────────────────────────────────────────────┘
```

Tipo artigo é exibido como badge colorido:
- `tecnico` → badge azul
- `conceitual` → badge roxo  
- `estrategico` → badge verde
