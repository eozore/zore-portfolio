# Refined Mockups — Especificações de Tela
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Referências: [wireframes.md](../../ideation/rough-mockups/wireframes.md) | [user-flow.md](../../ideation/rough-mockups/user-flow.md) | [stories.md](../user-stories/stories.md) | [requirements.md](../requirements-analysis/requirements.md) | [team-practices.md](../practices-discovery/team-practices.md)

---

## Tela 1: CsmDashboard — Barra de Abas Expandida

**Mapeia:** US-01 (navegação para nova aba), todas as telas
**Componente:** `CsmDashboard.tsx` — `ActiveTab` type e tab bar

```
+------------------------------------------------------------------------+
|  éozoré CSM Studio                                    [Victor | Sair]  |
+------------------------------------------------------------------------+
| [Bate-Papo] [Geração] [Publicação] [YouTube] [Derivações]             |
| [Projetos ●] [Pipeline] [Configurações] [Telemetria]                  |
+------------------------------------------------------------------------+
  ●  = indicador de notificação (badge vermelho se há projetos com erro)
```

**Estados da aba "Projetos":**
- Padrão: label "Projetos"
- Com erro ativo: `Projetos 🔴` (badge vermelho com número de projetos em erro)
- Com pronto para publicar: `Projetos 🔵` (badge ciano)

**Tipo TypeScript a adicionar em `CsmDashboard.tsx`:**
```typescript
export type ActiveTab =
  | 'idea' | 'generate' | 'publish' | 'youtube'
  | 'repurpose' | 'projects' | 'pipeline'
  | 'settings' | 'telemetry';

export type ProjectStatus =
  | 'creating'
  | 'awaiting_approval'
  | 'generating_media'
  | 'awaiting_publication'
  | 'publishing'
  | 'published'
  | 'error';
```

---

## Tela 2: Aba "Projetos" — Kanban Grid

**Mapeia:** US-02 (visualizar projetos), US-03 (ver detalhes), US-06 (monitorar pipeline), FR-01.2, FR-01.3

### Layout

```
+------------------------------------------------------------------------+
| h1: Projetos de Conteúdo           [+ Novo Projeto]  [🔔 2 alertas]   |
+------------------------------------------------------------------------+
| Filtros (role="tablist"):                                              |
| [Todos(8)] [Em Criação(1)] [Aguardando(2)] [Gerando(1)]               |
| [Pronto(2)] [Publicado(1)] [! Erro(1)]                                |
+------------------------------------------------------------------------+
| Grid (4 colunas desktop / 2 tablet / 1 mobile):                       |
|  [ProjectCard] [ProjectCard] [ProjectCard] [ProjectCard]              |
|  [ProjectCard] [ProjectCard] [ProjectCard] [ProjectCard]              |
+------------------------------------------------------------------------+
```

### Componente: `ProjectCard.tsx`

**Estados visuais por `ProjectStatus`:**

| Status | Badge | Cor Badge | CTA Primário | CTA Secundário |
|---|---|---|---|---|
| `creating` | Em Criação | `#3b82f6` | Abrir CMO | — |
| `awaiting_approval` | Aguardando | `#f59e0b` | Aprovar | Ver |
| `generating_media` | Gerando... | `#8b5cf6` (pulse) | Ver progresso | — |
| `awaiting_publication` | Pronto! | `#06b6d4` | Publicar | Ver |
| `publishing` | Publicando | `#8b5cf6` (pulse) | Ver | — |
| `published` | Publicado ✓ | `#10b981` | Ver resultado | — |
| `error` | !! Erro | `#ef4444` (pulse) | Re-tentar | Ver |

**Anatomia do card (CSS Module):**
```
.card {
  background: rgba(255,255,255,0.04);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 12px;
  padding: 16px;
  transition: border-color 200ms;
}
.card:hover { border-color: rgba(124,58,237,0.4); }
.card:focus-within { outline: 2px solid #7c3aed; }
```

**Conteúdo do card:**
```
+------------------+
| [BADGE STATUS]   |  ← 20px height, uppercase, semibold
| Título do        |  ← h3, 14px, truncate 2 linhas
| Conteúdo         |
|                  |
| TTS  [x]         |  ← ícone check/clock/warning, 12px
| Avatar [x]       |
| Video  [●]       |  ← ● = em progresso
| Publ.  [ ]       |
|                  |
| [████░░] R$45/100|  ← CostMeter: gradiente roxo→ciano
| 21 jul           |  ← 12px, cor cinza
|                  |
| [CTA Primário]   |  ← botão 100% width
| [CTA Secundário] |  ← link text 100% width (se houver)
+------------------+
```

**Erro inline (quando status = error):**
```
| [!! ERRO]        |
| Video Editor:    |  ← 11px, vermelho claro, máx 2 linhas
| Playwright t30s  |
| [Re-tentar] [>]  |
```

**Acessibilidade:**
- `role="article"` no card
- `aria-label="[título], status: [status label]"`
- `role="status"` no badge com `aria-live="polite"` (atualiza automaticamente)
- `aria-label="Custo: R$45 de R$100"` no CostMeter
- CTA primário: `aria-label="[CTA] para [título do projeto]"`

---

## Tela 3: Componente `ProjectDetailPanel.tsx` — Side Panel

**Mapeia:** US-03, US-07 (recuperação), US-04, US-05 (aprovação)

```
Posicionamento: position fixed, right: 0, top: 64px (altura da tabbar)
Dimensões: width 400px desktop / bottom sheet 80vh mobile
Transição: transform translateX(100%) → translateX(0), duration 250ms ease
Overlay: rgba(0,0,0,0.5) no fundo com click para fechar
```

**Estrutura interna:**

```
+-----------------------------+
| h2: Título do Projeto   [X] |  ← Close: aria-label="Fechar detalhes"
|-----------------------------|
| Status: [BADGE] · 22 jul   |
|-----------------------------|
| ## PIPELINE                 |
|                             |
| [x] TTS Audio               |  ← ícone check verde
|     ElevenLabs · R$4.13    |  ← custo real branco
|     3 segmentos             |
|                             |
| [x] Avatar Video            |
|     HeyGen · R$54.00       |
|     1920×1080 + 1080×1920  |
|                             |
| [●] Video Editor            |  ← ícone spinner roxo
|     Processando...          |
|     Tentativa 1 de 3        |
|                             |
| [ ] Publicação              |  ← ícone lock cinza
|     ~R$2.75 estimado       |  ← âmbar com prefixo ~
|-----------------------------|
| ## CUSTO ACUMULADO          |
| [████████░░] R$58/100       |
|  ElevenLabs:  R$4.13       |
|  HeyGen:      R$54.00      |
|  Gemini:     ~R$0.83       |  ← âmbar (estimado)
|  GCP:        ~R$2.75       |
|-----------------------------|
| ## AÇÕES (contextuais)      |
|                             |
| Se awaiting_approval:       |
| [Aprovar para Produção ►]   |
|                             |
| Se awaiting_publication:    |
| [Publicar / Agendar ►]      |
|                             |
| Se error:                   |
| Etapa: Video Editor         |
| Erro: Playwright timeout    |
| [Re-tentar etapa]           |
| [Pular esta etapa]          |
| [Upload manual .mp4]        |
|                             |
| Sempre:                     |
| [Cancelar projeto]          |  ← text link vermelho
+-----------------------------+
```

**Convenção custo estimado vs real:**
- Custo real executado: `R$4.13` — cor `#f8fafc` (branco)
- Custo estimado (não executado): `~R$0.83` — cor `#f59e0b` (âmbar)
- Não iniciado: `--` — cor `#6b7280` (cinza)

**Acessibilidade:**
- `role="dialog"`, `aria-modal="true"`, `aria-labelledby="[h2 id]"`
- Foco move para o primeiro elemento focável ao abrir
- Foco preso no panel enquanto aberto (focus trap)
- Escape fecha o panel
- Em mobile: `role="dialog"` com swipe down para fechar

---

## Tela 4: `ApprovalModal.tsx` — Modal de Aprovação para Produção

**Mapeia:** US-04, FR-02.1 a FR-02.4

```
Largura: max-width 560px, 100% em mobile
Posicionamento: centralizado com overlay rgba(0,0,0,0.7)
Foco: botão "Cancelar" recebe foco ao abrir; Escape fecha
```

**Layout:**
```
+------------------------------------------------------+
| h2: Aprovar para Produção                       [X]  |
|------------------------------------------------------|
|  "RAG Avançado: Por Que Seu RAG Piora"              |
|                                                      |
|  ## CUSTO ESTIMADO                                  |
|  ElevenLabs (TTS)    ~R$ 4.13   [âmbar]             |
|  HeyGen (Avatar)     ~R$54.00   [âmbar]             |
|  Gemini (geração)    ~R$ 0.83   [âmbar]             |
|  GCP (infra)         ~R$ 2.75   [âmbar]             |
|  ─────────────────────────────────────────────────  |
|  Total estimado:     ~R$61.71                        |
|  Limite:              R$100.00  ✓ Dentro do teto    |
|  [████████░░░░░░░░░░] 61.71%                        |
|                                                      |
|  ## CANAIS                                          |
|  [x] YouTube (1920×1080) + AI disclosure           |
|  [x] Instagram Reels (1080×1920)                   |
|  [x] YouTube Short (1080×1920)                     |
|  [x] LinkedIn (post de texto)                      |
|  [x] Threads (post de texto)                       |
|  [x] Blog (artigo)                                 |
|  [ ] Facebook (desabilitado no painel)             |
|                                                      |
|  ## CONFORMIDADE                                    |
|  [✓] IA Disclosure YouTube                         |
|      Obrigatório desde maio/2026 — pré-marcado     |
|      [campo desabilitado, aria-disabled="true"]    |
|                                                      |
|  [Cancelar]      [Aprovar e Iniciar Pipeline ►]     |
+------------------------------------------------------+
```

**Estado de custo excedido:**
```
|  Total estimado:     ~R$115.00                       |
|  Limite:              R$100.00  ⚠ Excede o teto     |
|  [████████████████████] 115%                        |
|  ─────────────────────────────────────────────────  |
|  ⚠ Estimativa R$115 excede o teto de R$100.         |
|    Desabilite canais ou ajuste o manifesto.         |
|                                                      |
|  [Cancelar]      [Aprovar e Iniciar Pipeline ►]     |
|                   [BOTÃO DESABILITADO, opacity 0.4] |
```

---

## Tela 4B: `PublishModal.tsx` — Modal de Aprovação de Publicação

**Mapeia:** US-05, FR-07.1 a FR-07.3

```
+------------------------------------------------------+
| h2: Publicar Conteúdo                           [X]  |
|------------------------------------------------------|
|  "RAG Avançado: Por Que Seu RAG Piora"              |
|                                                      |
|  [Preview horizontal] [Preview vertical]            |  ← links GCS
|                                                      |
|  ## PUBLICAR AGORA OU AGENDAR                       |
|  (●) Publicar agora                                 |
|  ( ) Agendar para: [23/07/2026] [18:00]            |
|      Fuso: America/Sao_Paulo (UTC-3)               |
|                                                      |
|  ## CANAIS                                          |
|  [x] YouTube (horizontal)                           |
|  [x] YouTube Short (vertical)                      |
|  [x] Instagram Reels                               |
|  [x] LinkedIn                                      |
|  [x] Threads                                       |
|  [x] Blog                                         |
|  [ ] Facebook (desabilitado)                       |
|                                                      |
|  ## CUSTO FINAL REAL                               |
|  ElevenLabs:   R$ 4.13   [branco — executado]      |
|  HeyGen:       R$54.00   [branco — executado]      |
|  Gemini:       R$ 0.83   [branco — executado]      |
|  GCP:          R$ 2.75   [branco — executado]      |
|  Total real:   R$61.71                              |
|                                                      |
|  [Cancelar]         [Publicar / Agendar ►]          |
+------------------------------------------------------+
```

---

## Tela 5: `PipelineTab.tsx` — Aba "Pipeline" (Configuração)

**Mapeia:** US-11 (configurar canais), US-12 (limites custo), US-13 (agenda), FR-08.1 a FR-08.6

### 5A: Seção Canais

```
## Canais de Publicação

[toggle ON ] YouTube          [Configurar ▼]
  +--------------------------------------------------+
  | Token OAuth:  [•••••••••••••••••] [Renovar]      |
  | Horário:      [18:00] Fuso: [America/Sao_Paulo ▼]|
  | Max/dia:      [1] upload(s)                      |
  | AI Disclosure:[✓] Sempre marcar (obrigatório)    |
  | Status:       ● ATIVO (234ms) [Testar ping]      |
  | Se INATIVO:   ✕ ERRO 401 — API key inválida     |
  |               Verifique em youtube.com/settings  |
  +--------------------------------------------------+

[toggle ON ] Instagram Reels  [Configurar ▼]
[toggle ON ] YouTube Short    [Configurar ▼]
[toggle ON ] LinkedIn         [Configurar ▼]
[toggle ON ] Threads          [Configurar ▼]
[toggle ON ] Blog             [Configurar ▼] (sem keys)
[toggle OFF] Facebook         [Configurar ▼]
```

### 5B: Seção APIs Externas

```
## APIs Externas

ElevenLabs
  API Key:  [•••••••••••••••sk-••••] [Editar] [Testar ping]
  Voice ID: [ZQe5CZNOzWyz••••••••] [Trocar voz]
  Status:   ● ATIVO (189ms)

HeyGen
  API Key:  [•••••••••••••••hg-••••] [Editar] [Testar ping]
  Avatar ID:[db66746ef7d8••••••••] [Trocar avatar]
  Status:   ● ATIVO (312ms)
```

### 5C: Seção Limites de Custo

```
## Limites de Custo

Teto por pacote:    R$ [100   ] — bloqueia se estimativa exceder
Alerta em:          [ 80]% do teto — badge no painel
```

### 5D: Seção Agenda (7 dias)

```
## Agenda Semanal

Horário padrão por dia:
Seg [Off ▼]  Ter [18:00 ▼]  Qua [18:00 ▼]
Qui [18:00 ▼] Sex [Off ▼]  Sáb [Off ▼]

Próximos 7 dias:
  Ter 23 jul · 18:00 ── "RAG Avançado" [Publicar agora]
  Qua 24 jul · 18:00 ── — slot vazio —
  Qui 25 jul · 18:00 ── "Fine-Tuning LLMs" [pendente aprovação]
  Sex 26 jul ──────────── Off (não configurado)
  Sáb 27 jul ──────────── Off (não configurado)
  Dom 28 jul ──────────── Off (não configurado)
  Seg 29 jul ──────────── Off (não configurado)

[Salvar configurações]
```

---

## Componente: `ApiKeyField.tsx`

**Mapeia:** US-11, FR-08.2 — campo seguro para API keys

**Props:**
```typescript
interface ApiKeyFieldProps {
  label: string;               // "ElevenLabs API Key"
  value: string;               // sempre "*****" (mascarado, vindo do backend)
  onSave: (key: string) => Promise<void>;
  onTest?: () => Promise<{ ok: boolean; latencyMs?: number; error?: string }>;
  status?: 'active' | 'inactive' | 'unknown';
  latencyMs?: number;
}
```

**Estados:**
```
Modo view (padrão):
  Label: ElevenLabs API Key
  [sk-••••••••••••••••••••••] [Editar]
  Status: ● ATIVO (189ms)  [Testar ping]

Modo edit (após clicar Editar):
  Label: ElevenLabs API Key
  [_________________________] type="password" autocomplete="off"
  [Cancelar] [Salvar]
  ⚠ Este campo nunca é pré-preenchido com a chave real.

Após ping com erro:
  Status: ✕ INATIVO
  Erro 401: API key inválida ou expirada.
  Verifique em elevenlabs.io/settings/api
  [Testar novamente]
```

**Segurança crítica:** O campo `value` recebe apenas `"*****"` do backend. NUNCA enviar o valor real para o frontend após salvo. O backend lê do Secret Manager e retorna apenas confirmação `{ saved: true }`.

---

## Componente: `CostMeter.tsx`

**Mapeia:** US-12, FR-10.1, FR-10.3

```typescript
interface CostMeterProps {
  actual: number;           // custo real incorrido (R$)
  estimated: number;        // custo estimado adicional (R$)
  limit: number;            // teto configurado (default: 100)
  alertThreshold: number;   // % para alerta (default: 80)
  compact?: boolean;        // true = versão card; false = versão side panel
}
```

**Visual:**
```
// compact = false (side panel)
[████████░░░░░░░] R$58 / R$100
  ████ = real (gradiente roxo→ciano)
  ░░░░ = estimado (cinza translúcido)

// compact = true (card)
[████████] R$58/100
```

**Cores e estados:**
- Normal (< 80%): gradiente `#7c3aed → #06b6d4`
- Alerta (80-99%): gradiente `#f59e0b → #f97316` + badge âmbar
- Excedido (≥ 100%): gradiente `#ef4444 → #dc2626` + badge vermelho

---

## Componente: `PipelineProgress.tsx`

**Mapeia:** US-06 (monitoramento em tempo real), US-14 (retry automático), FR-01.2, FR-11

```typescript
type StageStatus = 'pending' | 'running' | 'retrying' | 'completed' | 'error' | 'skipped';

interface PipelineProgressProps {
  stages: Array<{
    id: string;
    label: string;
    status: StageStatus;
    costReal?: number;
    costEstimated?: number;
    retryCount?: number;         // tentativa atual (1-3)
    maxRetries?: number;         // sempre 3
    errorMessage?: string;
    errorType?: 'transient' | 'permanent'; // transient = tentativas esgotadas, permanent = 401/403
    source?: 'pipeline' | 'manual';
  }>;
  compact?: boolean;
}
```

**Visual por estado — distinção `retrying` vs `error`:**

| Status | Ícone | Cor | Texto | CTAs |
|---|---|---|---|---|
| `pending` | `○` | cinza | `--` | — |
| `running` | `◉` (spin) | roxo | `Processando...` | — |
| `retrying` | `◉` (spin) | âmbar | `Tentativa 2 de 3 (automático)` | **Nenhum** — sistema trabalhando |
| `completed` | `✓` | verde | `R$X.XX` (custo real) | — |
| `error` (transient) | `✕` | vermelho | `Rate limit após 3 tentativas` | Re-tentar / Pular / Upload |
| `error` (permanent) | `✕` | vermelho | `Erro permanente: credencial inválida` | Re-tentar / Pular / Upload |
| `skipped` | `—` | cinza | `Pulado` | — |

**Regra crítica:** CTAs manuais (Re-tentar / Pular / Upload manual) **nunca aparecem** durante `status: 'retrying'`. Victor não deve interferir enquanto o sistema está executando retries automáticos. Os CTAs só aparecem quando `status: 'error'` — ou seja, após os retries automáticos serem esgotados.

---

## Seção de Resultados de Publicação no `ProjectDetailPanel.tsx`

**Mapeia:** US-08, US-09, US-16 (estados pós-publicação), FR-06.5, FR-06.7

Adicionada à Tela 3 quando `project.status` é `'published'` ou `'publishing'` ou publicações parciais existem:

```
|-----------------------------|
| ## PUBLICAÇÕES              |
|                             |
| YouTube      ✓ [ver vídeo ↗]|  ← link para URL do vídeo
| YouTube Short✓ [ver short ↗]|
| Instagram    ✓ [ver reel ↗] |
| LinkedIn     ✓ [ver post ↗] |
| Threads      ✓ [ver post ↗] |
| Blog         ✓ [ver artigo↗]|  ← link para URL do artigo
|                             |
| Falhas (se houver):         |
| Facebook  — desabilitado    |  ← cinza, não contado como falha
| LinkedIn  ✗ throttled       |  ← âmbar, re-tentar disponível
|                             |
| Blog especial:              |
| Se skipped_duplicate:       |
| Blog  ℹ artigo já publicado |  ← ícone info ciano
|        [ver artigo ↗]       |
|-----------------------------|
```

---

## Empty States — Aba "Projetos"

**Mapeia:** US-02 (grid kanban), F4 da revisão

### Estado A: Nenhum projeto no sistema (primeira vez)
```
+------------------------------------------------------------------------+
| h1: Projetos de Conteúdo           [+ Novo Projeto]                   |
+------------------------------------------------------------------------+
|                                                                        |
|         [ícone gradiente: documento + estrelas]                        |
|                                                                        |
|         Nenhum projeto ainda.                                          |
|         Crie seu primeiro projeto com o CMO Agent.                    |
|                                                                        |
|         [+ Criar Primeiro Projeto]                                     |
|                                                                        |
+------------------------------------------------------------------------+
```

### Estado B: Filtro sem resultados
```
+------------------------------------------------------------------------+
| Filtros: ... [! Erro(0)] ← filtro selecionado mas sem resultados       |
+------------------------------------------------------------------------+
|                                                                        |
|         Nenhum projeto com status "Erro".                             |
|         [← Ver todos os projetos]                                      |
|                                                                        |
+------------------------------------------------------------------------+
```

---

## Estado de Alerta OAuth YouTube — Tela 5A

**Mapeia:** US-15, FR-12.2

```
[toggle ON ] YouTube          [Configurar ▼]
  +--------------------------------------------------+
  | Token OAuth:                                     |
  |   ⚠ Expira em 5 dias                [âmbar]     |
  |   [Renovar autorização →]                        |
  |   (Expira em: 27 jul 2026, 14:30 BRT)           |
  |                                                  |
  | Ao clicar "Renovar autorização":                 |
  |   → Abre popup Google OAuth 2.0                 |
  |   → Após autorizar, novo refresh token          |
  |     salvo no Secret Manager                     |
  |   → Badge de alerta desaparece                  |
  |                                                  |
  | Horário:      [18:00] Fuso: [America/Sao_Paulo] |
  | Max/dia:      [1] upload(s)                     |
  | AI Disclosure:[✓] Sempre marcar                 |
  | Status:       ● ATIVO (234ms)                   |
  +--------------------------------------------------+
```

**Se token válido (sem alerta):** campo mostra apenas `● Token OAuth ativo` + botão `[Renovar]` discreto.
**Se token ≤ 7 dias para expirar:** badge âmbar `⚠ Expira em N dias` + CTA proeminente.
**Se token já expirado:** badge vermelho `✕ Token expirado` + `[Reautorizar agora]` em destaque.

---

## Interfaces TypeScript dos Modais

**Mapeia:** US-04, US-05, F6 da revisão

```typescript
// ApprovalModal.tsx
interface CostBreakdown {
  elevenlabs: number;
  heygen: number;
  gemini: number;
  gcp: number;
  total: number;
}

interface Channel {
  id: string;
  label: string;
  enabled: boolean;
  platform: 'youtube' | 'instagram' | 'youtube_short' | 'linkedin' | 'threads' | 'blog' | 'facebook';
}

interface ApprovalModalProps {
  projectId: string;
  projectTitle: string;
  estimatedCost: CostBreakdown;  // vem de GET /projects/[id]/cost-estimate
  costLimit: number;              // vem da config R$100
  channels: Channel[];            // canais habilitados no painel
  isOpen: boolean;
  isSubmitting: boolean;
  onApprove: (channelsApproved: string[]) => Promise<void>;
  onCancel: () => void;
}

// PublishModal.tsx
interface PublishPreview {
  horizontalUrl: string;   // GCS signed URL, TTL 1h
  verticalUrl: string;     // GCS signed URL, TTL 1h
  costBreakdown: CostBreakdown;  // custos reais (já executados)
  channels: Channel[];
  scheduledAt?: string;    // ISO 8601 UTC se já existe agendamento
}

interface PublishModalProps {
  projectId: string;
  projectTitle: string;
  preview: PublishPreview;  // vem de GET /projects/[id]/publish-preview
  isOpen: boolean;
  isSubmitting: boolean;
  onPublish: (payload: {
    mode: 'now' | 'scheduled';
    scheduledAt?: string;   // ISO 8601 UTC
    channels: string[];
  }) => Promise<void>;
  onCancel: () => void;
}
```

---

## Review

**Reviewer:** aidlc-product-lead-agent
**Date:** 2025-07-26
**Verdict:** NOT-READY

---

### Contexto da Revisão

Artefatos revisados: `mockups.md`, `interaction-spec.md`, `design-system-mapping.md`, `accessibility-checklist.md`. Referência cruzada contra `stories.md` (16 US, todos Must Have) e `requirements.md` (FR-01..FR-12 + FR-10, FR-11, FR-12).

---

### Findings

---

**F1 — US-08 (blog publish) sem tela ou componente correspondente — GAP CRÍTICO**

US-16 (FR-06.5, publicação no blog) está aprovada no stories.md como Must Have, e o `PublishModal.tsx` (Tela 4B) lista "Blog" nos checkboxes de canais. Porém, não existe nenhuma especificação de como o resultado da publicação no blog é representado no kanban após a conclusão: o card não especifica exibição de `project.publications.blog.url`, e o side panel não define como renderizar `status: "skipped_duplicate"` (cenário 3 de US-16). O ProjectDetailPanel.tsx define publicação genérica, mas o caso específico de "artigo já publicado" nunca aparece nos mockups. Um desenvolvedor não tem base visual para implementar o feedback do blog publish além do genérico.

**Correção necessária:** Adicionar ao `ProjectDetailPanel.tsx` (Tela 3) a representação do resultado de publicação no blog, incluindo os três estados de US-16: (1) publicado com URL clicável, (2) falha com mensagem, (3) `skipped_duplicate` com texto "Blog: artigo já publicado" — conforme critério BDD aprovado no stories.md.

---

**F2 — US-14 (retry automático) sem representação visual diferenciada do retry manual — GAP FUNCIONAL**

O `PipelineProgress.tsx` mostra `retryCount?: number` como prop e exibe "Tentativa N de 3" quando `status: 'running'`. Isso é necessário mas insuficiente. US-14 exige distinção visual entre **retry automático em andamento** (sistema trabalhando sem intervenção) e **estado de erro após 3 tentativas automáticas** (onde Victor deve agir manualmente). Os mockups atuais colapsam esses dois estados no mesmo `status: 'error'` com o mesmo conjunto de CTAs ("Re-tentar", "Pular", "Upload manual"). Resultado: Victor não consegue distinguir visualmente se o sistema está no meio de um retry automático ou se já exauriu todas as tentativas e está aguardando intervenção manual.

**Correção necessária:** Separar `StageStatus` em dois estados distintos:
- `'retrying'` — sistema executando retry automático; mostrar spinner roxo + "Tentativa 2 de 3 (automático)" + **sem CTAs de ação manual** (Victor não deve interferir)
- `'error'` (somente após esgotar retries) — mostrar ícone vermelho + "3 tentativas esgotadas" + CTAs "Re-tentar", "Pular", "Upload manual"

Adicionar também distinção visual para erro permanente vs. erro transitório esgotado, conforme US-14: `"Erro permanente: credencial inválida"` vs. `"Rate limit após 3 tentativas"`.

---

**F3 — US-15 (YouTube OAuth expiry badge) sem representação no painel de configuração — GAP DE US**

US-15 exige: "badge de alerta no painel de configuração do canal YouTube com link 'Renovar autorização'". A Tela 5A (`PipelineTab.tsx`) mostra o campo de token OAuth com `[Renovar]` genérico, mas não especifica: (a) como o badge de alerta de expiração aparece (inline no item de canal? badge no header da seção?), (b) o texto "expira em N dias", (c) o comportamento do link de renovação (popup OAuth vs. redirect). O `ApiKeyField.tsx` cobre API keys sem OAuth; o token OAuth do YouTube é um objeto diferente com expiração temporal, mas não há componente ou interface específica para isso.

**Correção necessária:** Adicionar à Tela 5A a especificação do estado de alerta do token OAuth YouTube: visual do badge de expiração, texto com dias restantes, comportamento do CTA "Renovar autorização". Criar ou estender o componente de configuração do YouTube para ter um `OAuthTokenField` distinto do `ApiKeyField` (sem campo de input direto — o refresh é por redirect OAuth, não por colar texto).

---

**F4 — Empty state da aba "Projetos" não especificado**

A Tela 2 define o skeleton loader (estado de carregamento inicial via Firestore) e o estado populado (grid de cards), mas não define o **empty state** — o que aparece quando a query retorna `[]` (nenhum projeto). Para um produto novo na primeira sessão de uso, ou após filtrar por um status sem projetos, isso é o primeiro estado que Victor vai ver. Sem especificação, o desenvolvedor vai implementar um espaço em branco, o que é uma experiência de produto ruim.

**Correção necessária:** Especificar empty state para dois casos: (a) nenhum projeto existe no sistema — exibir ilustração + texto "Nenhum projeto ainda. Crie seu primeiro projeto com o CMO Agent." + botão "+ Novo Projeto"; (b) filtro ativo sem resultados — exibir texto "Nenhum projeto com status '[filtro]'." + link "Ver todos os projetos".

---

**F5 — Endpoints da interaction-spec não cobrem FR-10 (CostTrackerService) nem FR-11 (retry interno)**

A tabela de endpoints (seção 4 da interaction-spec) cobre corretamente US-01..US-07, US-11..US-13. Mas há dois gaps:

- **FR-10.2 (bloqueio de job por custo):** Não há endpoint para o frontend consultar o estado de bloqueio por custo. Quando o CostTrackerService bloqueia um job porque o próximo step excederia R$100, o Firestore deve refletir isso — mas a interaction-spec não define o payload do Firestore nesse estado nem como o frontend detecta e exibe a condição. O card deve mostrar algo diferente de um erro genérico: "Custo estimado ultrapassaria R$100" (conforme US-12 critério 2).

- **FR-11 (retry automático):** Não existe endpoint `GET /projects/[id]/stages` ou equivalente que retorne `retry_count` por stage. Os dados de `retryCount` no `PipelineProgressProps` presumem que chegam via Firestore listener, o que é correto arquiteturalmente — mas a interaction-spec não documenta o shape do documento Firestore que o listener escuta. Um desenvolvedor implementando o listener não sabe quais campos de `project.stages[].retry_count` esperar.

**Correção necessária:** (a) Documentar o shape do subdocumento Firestore `project.stages[]` que o `PipelineProgress` listener escuta. (b) Especificar como o estado de bloqueio por custo (FR-10.2) aparece no Firestore e é renderizado no card/side panel.

---

**F6 — Props TypeScript insuficientes para `PublishModal.tsx`**

A Tela 4B especifica o layout do `PublishModal.tsx` com preview de vídeos, date/time picker, e checkboxes de canais — mas não define a interface TypeScript do componente. O `ApprovalModal.tsx` não tem props definidas em nenhum dos artefatos; apenas o `ApiKeyField.tsx`, `CostMeterProps`, e `PipelineProgressProps` têm interfaces completas. Para `PublishModal` especificamente, falta:

- Como os links de preview chegam ao componente (GCS URLs do Firestore? pré-assinadas?)
- O tipo do `scheduled_at` (string ISO? Date object?)
- O estado de loading do submit (`isSubmitting: boolean`)
- Como `channels` é inicializado (array de channels do projeto? ou da config global?)

Sem interface TypeScript, dois desenvolvedores vão implementar contratos incompatíveis entre o componente e o chamador.

**Correção necessária:** Adicionar a interface `PublishModalProps` e `ApprovalModalProps` com tipagem completa, análoga ao nível de detalhe do `ApiKeyFieldProps`.

---

**F7 — `PipelineTab.tsx` sem estados de loading/error/success para ações de configuração**

A interaction-spec documenta os estados de loading de `ProjectCard`, `ApprovalModal` e `ApiKeyField`, mas a seção de configuração do `PipelineTab` (Telas 5A, 5B, 5C, 5D) não especifica estados de UI para as ações de salvar configuração. Quando Victor clica "Salvar configurações" (Tela 5D), o que acontece? A spec não define: (a) botão em loading com spinner, (b) feedback de sucesso inline ("✓ Configuração salva"), (c) estado de erro se o POST `/pipeline/config` falhar. A interaction-spec cobre `ApiKeyField` individualmente mas não o botão de save global da seção Agenda (5D).

**Correção necessária:** Adicionar à seção de estados (seção 3 da interaction-spec) uma tabela `PipelineTab — Estados de Loading` análoga à tabela de `ApprovalModal`, cobrindo: salvar configuração de agenda, salvar teto de custo, salvar toggle de canal.

---

**F8 — US-10 (publicação agendada automática) sem representação de UI para o feedback do Cloud Scheduler**

US-10 é um fluxo background (Cloud Scheduler dispara, Publisher Service executa). Quando isso acontece enquanto Victor tem o CSM Studio aberto, o que ele vê? A aba "Projetos" deve atualizar o card de `awaiting_publication` para `publishing` para `published` via Firestore listener — isso está coberto pelos estados do `ProjectCard`. Porém, a interaction-spec não especifica o toast notification para este evento específico: a tabela de toasts (seção 1.2) cobre "Publicação concluída" como `success | "✓ Publicado em N canais"`, o que resolve o caso feliz. Mas não há entrada para o caso de **publicação agendada iniciada automaticamente** — Victor pode não saber que a publicação começou se ele não estiver olhando para o card específico.

**Correção necessária:** Adicionar à tabela de toasts (interaction-spec seção 1.2) uma entrada para `Publicação agendada iniciada`: `info | "⏰ Publicando '[título]' — agendado para [horário]" | 5s`. Isso fecha o loop visual para US-10 sem precisar criar nova tela.

---

### Cobertura das 16 User Stories nos Mockups

| US | Tela / Componente Mapeado | Status de Cobertura |
|---|---|---|
| US-01 | Tela 2 (botão "+ Novo Projeto"), Tela 1 (tab bar) | ✅ Coberta |
| US-02 | Tela 2 (kanban grid + filtros + ProjectCard) | ✅ Coberta |
| US-03 | Tela 3 (ProjectDetailPanel) | ✅ Coberta |
| US-04 | Tela 4 (ApprovalModal) | ✅ Coberta |
| US-05 | Tela 4B (PublishModal) | ✅ Coberta (com gap F6) |
| US-06 | Tela 2 (skeleton + Firestore listener) + Tela 3 (PipelineProgress) | ✅ Coberta |
| US-07 | Tela 3 (ações contextuais no side panel: Re-tentar / Pular / Upload) | ✅ Coberta |
| US-08 | Tela 4B (canal YouTube com AI disclosure) | ✅ Parcial — resultado pós-publicação no blog ausente (F1) |
| US-09 | Tela 4B (canais) + Toast "Publicado em N canais" | ✅ Coberta |
| US-10 | Toast de publicação concluída | ⚠️ Parcial — toast de início de publicação agendada ausente (F8) |
| US-11 | Tela 5A (canais) + Tela 5B (APIs externas) + ApiKeyField | ✅ Coberta |
| US-12 | Tela 5C (limites) + CostMeter | ✅ Coberta |
| US-13 | Tela 5D (agenda 7 dias) | ✅ Coberta |
| US-14 | PipelineProgress (`retryCount`) + card erro inline | ⚠️ Parcial — sem distinção `'retrying'` vs `'error'` (F2) |
| US-15 | Tela 5A (campo OAuth YouTube) | ⚠️ Parcial — badge de expiração e fluxo de renovação não especificados (F3) |
| US-16 | PublishModal canal Blog | ⚠️ Parcial — resultado pós-publicação blog não especificado (F1) |

**Cobertura total:** 10 US completamente cobertas, 6 com gaps (US-08, US-10, US-14, US-15, US-16 — mais F4 de empty state ortogonal às US).

---

### Estados Críticos: Lacunas por Componente

| Componente | Loading | Error | Success | Empty | Observação |
|---|---|---|---|---|---|
| `ProjectCard` | ✅ Skeleton | ✅ Badge erro + inline | ✅ Badge publicado | ❌ **Ausente** | F4: empty state da grid não especificado |
| `ProjectDetailPanel` | ✅ Implícito (Firestore listener) | ✅ Ações contextuais | ✅ Checklist completo | — | Adicionar estado `skipped_duplicate` blog (F1) |
| `ApprovalModal` | ✅ Spinner no bloco de custo | ✅ "Erro ao calcular" + retry | ✅ Modal fecha + toast | — | Props não tipadas (F6) |
| `PublishModal` | ❌ **Não especificado** | ❌ **Não especificado** | ✅ Implícito | — | F6: interface e estados de loading ausentes |
| `PipelineProgress` | ✅ `running` + spinner | ✅ `error` + mensagem | ✅ `completed` + custo | — | F2: `retrying` ausente como estado separado |
| `ApiKeyField` | ✅ Saving + Ping loading | ✅ Ping error + link | ✅ "✓ Salvo" + Ping success | — | Completo |
| `CostMeter` | — | ✅ Excedido (vermelho) | ✅ Normal (roxo→ciano) | — | Completo |
| `PipelineTab` | ❌ **Loading de save ausente** | ❌ **Error de save ausente** | ❌ **Success de save ausente** | — | F7: estados de save global ausentes |
| `ChannelToggle` | — | — | ✅ Implícito (toggle ON/OFF) | — | Sem estado de error ao salvar toggle |

---

### Consistência de Endpoints × FRs

| FR | Endpoints Cobertos | Status |
|---|---|---|
| FR-01 (Kanban) | `GET /projects`, `POST /projects`, `GET /projects/[id]` | ✅ |
| FR-02 (Gate produção) | `GET /projects/[id]/cost-estimate`, `POST /projects/[id]/approve` | ✅ |
| FR-07 (Gate publicação) | `GET /projects/[id]/publish-preview` (implícito), `POST /projects/[id]/publish` | ✅ (publish-preview não está na tabela, mas está no fluxo US-05) |
| FR-08 (Configuração) | `GET /pipeline/config`, `POST /pipeline/config`, `POST /pipeline/config/keys`, `GET /pipeline/config/ping` | ✅ |
| FR-09 (Fallback) | `POST /projects/[id]/retry-stage`, `POST /projects/[id]/skip-stage`, `POST /projects/[id]/stages/[stage]/manual-upload` | ✅ |
| FR-10 (CostTracker) | ❌ **Shape do Firestore `project.cost_breakdown` não documentado** | ⚠️ Gap (F5) |
| FR-11 (Retry automático) | ❌ **Shape do Firestore `project.stages[].retry_count` não documentado** | ⚠️ Gap (F5) |
| FR-12 (YouTube OAuth) | ❌ **Endpoint de renovação OAuth ausente da tabela** | ⚠️ Gap (F3) — o fluxo existe na US-15 mas não tem endpoint definido |
| FR-06.5 (Blog) | `POST /api/csm/publish` referenciado na US-16 | ⚠️ Não na tabela da interaction-spec; endpoint externo já existente, mas contrato não documentado nos mockups |

**Endpoint ausente crítico:** `GET /projects/[id]/publish-preview` não está na tabela da seção 4, mas o fluxo US-05 o usa (`Modal faz GET /api/csm/projects/{id}/publish-preview`). Deve ser adicionado.

---

### Observações para Application Design

1. **`OAuthTokenField` vs. `ApiKeyField`:** O token OAuth do YouTube tem semântica diferente de uma API key — tem expiração, requer fluxo OAuth (não colar texto), e tem `refresh_token` distinto do `access_token`. Application Design deve decidir se cria um componente `OAuthTokenField` ou estende `ApiKeyField` com props de expiração (`expiresAt?: Date`, `onRenew?: () => void`). Esta decisão impacta a Tela 5A e US-15.

2. **Shape do documento Firestore `project.stages[]`:** A interaction-spec documenta hooks Firestore para o projeto inteiro, mas não o schema do subdocumento de stages. Application Design deve definir e documentar o shape de `project.stages[]` com campos: `id`, `label`, `status`, `retry_count`, `error_message`, `cost_real`, `cost_estimated`, `source` (`'pipeline'` | `'manual'`). Isso desbloqueia os F2 e F5.

3. **`publish-preview` endpoint:** O fluxo US-05 usa `GET /api/csm/projects/{id}/publish-preview` que retorna os links GCS dos vídeos para o `PublishModal`. Application Design deve definir o contrato de resposta: `{ horizontal_url: string, vertical_url: string, cost_breakdown: CostBreakdown, channels: Channel[] }` — e se os links são GCS signed URLs com TTL ou links públicos.

4. **Endpoint de renovação OAuth YouTube:** FR-12 e US-15 exigem um fluxo OAuth. Application Design deve definir se a renovação usa um endpoint Next.js Route Handler (`POST /api/csm/pipeline/config/youtube-oauth`) com redirect ou um popup window. Esta decisão impacta a especificação da Tela 5A.

5. **Estado `skipped_duplicate` do blog:** US-16 critério 3 especifica `project.publications.blog.status: "skipped_duplicate"` com texto "Blog: artigo já publicado" no side panel. O `ProjectDetailPanel` precisa de uma seção de "Resultados de Publicação" que ainda não existe nos mockups — as ações contextuais são pré-publicação. Esta seção deve aparecer quando o projeto está em `published` ou quando publicações parciais existem.

---

### Para READY: ações obrigatórias

| # | Ação | Arquivo a modificar |
|---|---|---|
| F1 | Adicionar ao `ProjectDetailPanel` seção "Resultados de Publicação" com estados: publicado (URL), falha, `skipped_duplicate` (blog) | `mockups.md` Tela 3 |
| F2 | Adicionar `StageStatus: 'retrying'` com visual distinto (spinner + "automático" + sem CTAs) e distinguir erro transitório esgotado de erro permanente | `mockups.md` `PipelineProgress` |
| F3 | Especificar estado de alerta do token OAuth YouTube na Tela 5A com badge de expiração, texto "expira em N dias", CTA "Renovar autorização" | `mockups.md` Tela 5A |
| F4 | Especificar empty state da aba "Projetos" para: (a) sem projetos no sistema, (b) filtro sem resultados | `mockups.md` Tela 2 |
| F5 | Documentar shape Firestore de `project.stages[]` e como o estado de bloqueio por custo (FR-10.2) é renderizado | `interaction-spec.md` seção 1.1 ou nova seção 5 |
| F6 | Adicionar interfaces TypeScript `PublishModalProps` e `ApprovalModalProps` com tipagem completa | `mockups.md` Tela 4 / 4B |
| F7 | Adicionar tabela de estados de loading/error/success para ações de save no `PipelineTab` | `interaction-spec.md` seção 3 |
| F8 | Adicionar entrada de toast para "publicação agendada iniciada automaticamente" | `interaction-spec.md` seção 1.2 |

**Ações recomendadas (não bloqueantes):**
- Adicionar `GET /projects/[id]/publish-preview` à tabela de endpoints da seção 4 da interaction-spec.
- Documentar que `ChannelToggle` tem estado de error ao salvar (PUT falhou).
- No `design-system-mapping.md`, adicionar `.retrying` e `.retryingText` às convenções de nomes de classes CSS Modules.

---

*Documento aprovado para iteração. Resolver F1–F8 para avançar para Application Design.*

---

## Review (Iteração 2)

**Reviewer:** aidlc-product-lead-agent
**Date:** 2025-07-26
**Iteração:** 2 (follow-up à iteração 1 — NOT-READY com F1–F8)
**Verdict:** ✅ READY

---

### Tabela de Verificação F1–F8

| # | Finding | Status | Evidência |
|---|---|---|---|
| F1 | Seção "Resultados de Publicação" no `ProjectDetailPanel` com estados publicado / falha / `skipped_duplicate` blog | ✅ RESOLVIDO | Seção `## Seção de Resultados de Publicação no ProjectDetailPanel.tsx` adicionada ao `mockups.md`. Cobre: link clicável por canal publicado, `LinkedIn ✗ throttled` (âmbar), `Blog ℹ artigo já publicado` com link e ícone info ciano para `skipped_duplicate`. Três estados de US-16 completamente representados. |
| F2 | Estado `'retrying'` distinto em `PipelineProgress` sem CTAs manuais | ✅ RESOLVIDO | `StageStatus` inclui `'retrying'` na interface TypeScript. Tabela de estados visuais tem linha dedicada: spinner âmbar + "Tentativa 2 de 3 (automático)" + CTA = **Nenhum**. Regra crítica explícita: "CTAs manuais nunca aparecem durante `status: 'retrying'`". Distinção `error (transient)` vs `error (permanent)` também presente. |
| F3 | Badge de alerta OAuth YouTube na Tela 5A com "expira em N dias" e CTA de renovação | ✅ RESOLVIDO | Seção `## Estado de Alerta OAuth YouTube — Tela 5A` adicionada. Define três estados: token válido (badge discreto), ≤ 7 dias (badge âmbar + "⚠ Expira em N dias" + data exata + `[Renovar autorização →]`), expirado (badge vermelho + `[Reautorizar agora]`). Fluxo do popup OAuth documentado. |
| F4 | Empty states da aba "Projetos" (sem projetos + filtro sem resultados) | ✅ RESOLVIDO | Seção `## Empty States — Aba "Projetos"` com Estado A (primeira vez — ilustração + CTA `[+ Criar Primeiro Projeto]`) e Estado B (filtro sem resultados — texto contextual + link `[← Ver todos os projetos]`). |
| F5 | Shape Firestore `project.stages[]` com `retry_count`, `error_type`, `cost_blocked` documentado | ✅ RESOLVIDO | Seção 5 da `interaction-spec.md` documenta `ContentProject` completo incluindo `stages[]` com todos os campos exigidos (`retry_count`, `max_retries`, `error_type`, `source`), `cost_blocked` com campos `blocked_stage`, `current_cost`, `estimated_next`, e `publications` por canal. Snippet TypeScript de detecção de bloqueio por custo presente. |
| F6 | `PublishModalProps` e `ApprovalModalProps` com interfaces TypeScript completas | ✅ RESOLVIDO | Seção `## Interfaces TypeScript dos Modais` no `mockups.md` define: `CostBreakdown`, `Channel`, `ApprovalModalProps` (com `estimatedCost`, `costLimit`, `channels`, `isSubmitting`, `onApprove`, `onCancel`), `PublishPreview`, `PublishModalProps` (com `mode: 'now' \| 'scheduled'`, `scheduledAt?: string` ISO 8601, `isSubmitting`, `onPublish`, `onCancel`). Contrato de GCS signed URLs documentado. |
| F7 | Tabela de estados loading/error/success para ações de save no `PipelineTab` | ✅ RESOLVIDO | Seção 6 `## Estados de Loading/Error/Success — PipelineTab` na `interaction-spec.md` cobre: salvar agenda semanal (spinner + campos desabilitados → `✓ Configuração salva` → toast error), salvar teto de custo (inline por campo), toggle de canal (spinner 500ms → reverter em erro), salvar config expandida de canal. |
| F8 | Toast "publicação agendada iniciada" adicionado | ✅ RESOLVIDO | Seção 7 `## Toasts — Tabela Completa` na `interaction-spec.md` inclui entrada: `Publicação agendada iniciada \| info \| "⏰ Publicando '[título]' — agendado para [horário]" \| 5s`. Complementada por entradas para token OAuth expirando (warning, 10s) e token expirado (error, persistente). |

---

### Cobertura Revisada — 16 User Stories

| US | Status Iteração 1 | Status Iteração 2 |
|---|---|---|
| US-01 | ✅ | ✅ |
| US-02 | ✅ | ✅ |
| US-03 | ✅ | ✅ |
| US-04 | ✅ | ✅ |
| US-05 | ✅ | ✅ |
| US-06 | ✅ | ✅ |
| US-07 | ✅ | ✅ |
| US-08 | ⚠️ Parcial (F1) | ✅ |
| US-09 | ✅ | ✅ |
| US-10 | ⚠️ Parcial (F8) | ✅ |
| US-11 | ✅ | ✅ |
| US-12 | ✅ | ✅ |
| US-13 | ✅ | ✅ |
| US-14 | ⚠️ Parcial (F2) | ✅ |
| US-15 | ⚠️ Parcial (F3) | ✅ |
| US-16 | ⚠️ Parcial (F1) | ✅ |

**Cobertura total iteração 2:** 16/16 US cobertas. ✅

---

### Observações para Application Design

As quatro recomendações estruturais da iteração 1 permanecem válidas e devem ser resolvidas no Application Design — não são bloqueantes para avançar, mas impactam decisões de implementação:

1. **`OAuthTokenField` vs. extensão de `ApiKeyField`:** A Tela 5A agora especifica o comportamento visual do token OAuth YouTube, mas Application Design ainda deve decidir a estratégia de componente. Recomendação: criar `OAuthTokenField` separado com props `expiresAt: Date | null`, `onRenew: () => void`, `renewUrl: string` — a semântica é fundamentalmente diferente de uma API key (sem campo de input, sem colar texto, fluxo popup).

2. **Endpoint de renovação OAuth YouTube:** A interaction-spec documenta o fluxo visual (popup → novo refresh token → badge desaparece), mas o contrato do endpoint de backend ainda não está na tabela da seção 5. Application Design deve definir: `POST /api/csm/pipeline/config/youtube-oauth/refresh` ou redirect handler. Sem isso, o desenvolvedor de frontend não sabe como iniciar o popup.

3. **`publish-preview` na tabela de endpoints:** O endpoint `GET /projects/[id]/publish-preview` foi adicionado à tabela da seção 5 da interaction-spec, fechando o gap apontado na iteração 1. Confirmado presente. ✅

4. **`ChannelToggle` em estado de erro:** A tabela da seção 6 da interaction-spec agora especifica que o toggle reverte ao estado anterior se o save falhar + toast de erro. Confirmado resolvido. ✅

---

*Artefatos prontos para avançar para Application Design. Resolver os itens (1) e (2) acima como primeiras decisões de design de componentes/API na fase de construção.*
