# Wireframes — Rough Mockups
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Referências: [intent-statement.md](../intent-capture/intent-statement.md) | [scope-document.md](../scope-definition/scope-document.md) | [intent-backlog.md](../scope-definition/intent-backlog.md)
>
> Design system: Dark theme (#0a0a0a), glassmorphism nos cards, CSS Modules, accent roxo (#7c3aed) + ciano (#06b6d4).
> Segue padrões do CsmDashboard.tsx existente. Novas abas: "Projetos" e "Pipeline".

---

## Tela 1: CsmDashboard — Navegação Expandida

A barra de abas do `CsmDashboard` ganha duas novas abas inseridas entre "Derivações" e "Configurações":

```
+------------------------------------------------------------------------+
|  eozore CSM Studio                                    [sair]           |
+------------------------------------------------------------------------+
| [Bate-Papo] [Geração] [Publicação] [YouTube] [Derivações] [Projetos*] |
|             [Pipeline*] [Configurações] [Telemetria]                   |
+------------------------------------------------------------------------+
|                                                                        |
|  (conteudo da aba ativa abaixo)                                        |
|                                                                        |
+------------------------------------------------------------------------+
```

`*` = novas abas

**Acessibilidade:** `role="tablist"` no container de abas, `role="tab"` por aba, `aria-selected` no ativo. Foco visível com outline roxo. Navegação por setas esquerda/direita entre abas.

---

## Tela 2: Aba "Projetos" — Visão Kanban

```
+------------------------------------------------------------------------+
|  Projetos de Conteudo                          [+ Novo Projeto]        |
+------------------------------------------------------------------------+
|  [Todos v] [Em Criacao] [Aguardando] [Gerando] [Publicar] [Publicado] |
+------------------------------------------------------------------------+
|                                                                        |
|  +------------------+  +------------------+  +------------------+     |
|  | RAG Avancado     |  | Fine-Tuning LLMs |  | Teste Hipotese   |     |
|  | [=== AGUARDANDO] |  | [====== GERANDO] |  | [========= PUBL] |     |
|  |                  |  |                  |  |                  |     |
|  | TTS   [x]        |  | TTS   [x]        |  | Publicado em:    |     |
|  | Avatar [ ]       |  | Avatar [x]       |  | YouTube [link]   |     |
|  | Video  [ ]       |  | Video  [x]       |  | Instagram [link] |     |
|  | Publi  [ ]       |  | Publi  [ ]       |  | LinkedIn [link]  |     |
|  |                  |  |                  |  |                  |     |
|  | Custo: R$12/100  |  | Custo: R$45/100  |  | Custo: R$67      |     |
|  | 22 jul           |  | 21 jul           |  | 20 jul           |     |
|  |                  |  |                  |  |                  |     |
|  | [Aprovar] [Ver]  |  | [Ver progresso]  |  | [Ver detalhes]   |     |
|  +------------------+  +------------------+  +------------------+     |
|                                                                        |
|  +------------------+                                                  |
|  | Embeddings 101   |                                                  |
|  | [== EM CRIACAO]  |                                                  |
|  |                  |                                                  |
|  | Aguardando       |                                                  |
|  | aprovacao do CMO |                                                  |
|  |                  |                                                  |
|  | Custo: --        |                                                  |
|  | 22 jul           |                                                  |
|  |                  |                                                  |
|  | [Abrir CMO]      |                                                  |
|  +------------------+                                                  |
|                                                                        |
+------------------------------------------------------------------------+
```

**Cards — especificação visual:**
- Fundo: `rgba(255,255,255,0.04)` com `backdrop-filter: blur(12px)`
- Borda: `1px solid rgba(255,255,255,0.08)`
- Border-radius: `12px`
- Status badge cores:
  - Em Criação: `#3b82f6` (azul)
  - Aguardando Aprovação: `#f59e0b` (âmbar)
  - Gerando Mídia: `#8b5cf6` (roxo, pulsante)
  - Aguardando Publicação: `#06b6d4` (ciano)
  - Publicado: `#10b981` (verde)
  - Erro: `#ef4444` (vermelho)
- Progress bar: gradiente roxo→ciano na barra de preenchimento
- Hover: `border-color: rgba(124, 58, 237, 0.4)`, leve elevação

**Acessibilidade (h1–h3):**
- `h1`: "Projetos de Conteúdo" (heading da página)
- `h3`: título de cada card
- `role="status"` no badge de estado para screen readers
- `aria-label="Custo: R$12 de R$100"` na barra de custo

---

## Tela 3: Modal de Detalhes do Projeto

Clicando "Ver" ou no título do card abre um modal lateral (side panel, não modal central):

```
+------------------------------------------------------------------------+
|  [fundo da tela anterior, escurecido]                                  |
|                                          +-----------------------------+
|                                          |  RAG Avancado        [X]   |
|                                          |-----------------------------|
|                                          |  Status: AGUARDANDO APROVA |
|                                          |  22 jul 2026 14:30          |
|                                          |-----------------------------|
|                                          |  PIPELINE                  |
|                                          |                            |
|                                          |  [x] TTS Audio             |
|                                          |      3 segmentos gerados   |
|                                          |      ElevenLabs R$0.75     |
|                                          |                            |
|                                          |  [ ] Avatar Video          |
|                                          |      Aguardando...         |
|                                          |                            |
|                                          |  [ ] Edicao de Video       |
|                                          |  [ ] Publicacao            |
|                                          |-----------------------------|
|                                          |  CUSTO ACUMULADO           |
|                                          |  [########------] R$12/100 |
|                                          |  ElevenLabs: R$4           |
|                                          |  HeyGen:     R$8 (estim.)  |
|                                          |  Gemini:     R$0.80        |
|                                          |-----------------------------|
|                                          |  ACOES                     |
|                                          |  [Aprovar para Producao]   |
|                                          |  [Re-tentar etapa]         |
|                                          |  [Cancelar projeto]        |
|                                          +-----------------------------+
+------------------------------------------------------------------------+
```

---

## Tela 4: Modal de Aprovação para Produção

```
+------------------------------------------------------+
|  Aprovar para Producao                          [X]  |
|------------------------------------------------------|
|  Voce esta aprovando:                               |
|  "RAG Avancado"                                     |
|                                                      |
|  CUSTO ESTIMADO:                                    |
|  ElevenLabs (TTS)    R$ 4.13                        |
|  HeyGen (Avatar)     R$ 54.00 (estim.)              |
|  Gemini (geracao)    R$ 0.83                        |
|  GCP (infra)         R$ 2.75                        |
|  --------------------------------                   |
|  Total estimado:     R$ 61.71                       |
|  Limite:             R$ 100.00  [OK, dentro do teto]|
|                                                      |
|  CANAIS QUE SERAO PUBLICADOS:                       |
|  [x] YouTube (horizontal 1920x1080)                 |
|  [x] Instagram Reels + YouTube Shorts               |
|  [x] Blog (artigo ja publicado)                     |
|  [x] LinkedIn                                       |
|  [x] Threads                                        |
|  [ ] Facebook (desabilitado)                        |
|                                                      |
|  AI DISCLOSURE:                                     |
|  [x] Marcar vídeo como gerado com IA no YouTube     |
|      (obrigatório pela política YouTube maio/2026)   |
|                                                      |
|  [Cancelar]           [Aprovar e Iniciar Pipeline]   |
+------------------------------------------------------+
```

**Nota de acessibilidade:** `role="dialog"`, `aria-modal="true"`, foco preso no modal enquanto aberto. Botão de cancelar recebe foco ao abrir. Escape fecha o modal.

---

## Tela 5: Aba "Pipeline" — Painel de Configuração

```
+------------------------------------------------------------------------+
|  Configuracao da Pipeline                                              |
+------------------------------------------------------------------------+
|                                                                        |
|  CANAIS DE PUBLICACAO                                                  |
|  +------------------------------------------------------------------+  |
|  |  YouTube          [toggle: ON ]  [Configurar v]                  |  |
|  |  +---------------------------------------------------------+     |  |
|  |  |  Token OAuth:   [*************] [Renovar]               |     |  |
|  |  |  Horario:       [18:00]  Fuso: [America/Sao_Paulo v]    |     |  |
|  |  |  Max por dia:   [1]                                     |     |  |
|  |  |  AI Disclosure: [x] Sempre marcar como IA              |     |  |
|  |  +---------------------------------------------------------+     |  |
|  +------------------------------------------------------------------+  |
|  |  Instagram        [toggle: ON ]  [Configurar v]                  |  |
|  |  LinkedIn         [toggle: ON ]  [Configurar v]                  |  |
|  |  Threads          [toggle: ON ]  [Configurar v]                  |  |
|  |  Facebook         [toggle: OFF]  [Configurar v]                  |  |
|  |  Blog             [toggle: ON ]  (sem config extra)              |  |
|  +------------------------------------------------------------------+  |
|                                                                        |
|  APIS EXTERNAS                                                         |
|  +------------------------------------------------------------------+  |
|  |  ElevenLabs                                                      |  |
|  |  API Key:    [sk-*********************] [Editar] [Testar ping]   |  |
|  |  Voice ID:   [ZQe5CZNOzWyzPSCn1a...] [Trocar voz]               |  |
|  |  Status:     o ATIVO (200ms latency)                             |  |
|  +------------------------------------------------------------------+  |
|  |  HeyGen                                                          |  |
|  |  API Key:    [hg-*********************] [Editar] [Testar ping]   |  |
|  |  Avatar ID:  [db66746ef7d848cca675...] [Trocar avatar]           |  |
|  |  Status:     o ATIVO (340ms latency)                             |  |
|  +------------------------------------------------------------------+  |
|                                                                        |
|  LIMITES DE CUSTO                                                      |
|  +------------------------------------------------------------------+  |
|  |  Teto por pacote:    R$ [100]  (bloqueia se estimativa exceder)  |  |
|  |  Alerta em:          [80]% do teto  (notifica no painel)         |  |
|  +------------------------------------------------------------------+  |
|                                                                        |
|  AGENDA SEMANAL                                                        |
|  +------------------------------------------------------------------+  |
|  |  Dia e horario de publicacao de conteudo novo:                   |  |
|  |  Seg [Nao publicar v]  Ter [18:00 v]  Qua [18:00 v]             |  |
|  |  Qui [18:00 v]  Sex [Nao publicar v]  Sab [Nao publicar v]      |  |
|  |                                                                  |  |
|  |  Proximo conteudo agendado:                                      |  |
|  |  "RAG Avancado" — Ter 23 jul, 18:00                             |  |
|  +------------------------------------------------------------------+  |
|                                                                        |
|  [Salvar configuracoes]                                                |
|                                                                        |
+------------------------------------------------------------------------+
```

**Nota de acessibilidade:**
- `h2`: seções "Canais de Publicação", "APIs Externas", "Limites de Custo", "Agenda Semanal"
- `role="switch"` nos toggles com `aria-checked` e `aria-label="YouTube publicação habilitada"`
- Campos de API key: `type="password"` com `autocomplete="off"`, nunca em texto claro no DOM
- Status "ATIVO" / "INATIVO": não depende apenas de cor — inclui texto e ícone

---

## Tela 6: Aba "Projetos" — Estado Erro (Tela de Recuperação)

```
+------------------------------------------------------------------------+
|  ...                                                                   |
|                                                                        |
|  +------------------+                                                  |
|  | RAG Avancado     |                                                  |
|  | [!! ERRO]        | <- badge vermelho pulsante                       |
|  |                  |                                                  |
|  | TTS   [x]        |                                                  |
|  | Avatar [x]       |                                                  |
|  | Video  [!] <- erro aqui                                            |
|  | Publi  [ ]       |                                                  |
|  |                  |                                                  |
|  | "Playwright:     |                                                  |
|  |  timeout 30s"    | <- mensagem de erro inline                       |
|  |                  |                                                  |
|  | [Re-tentar] [>]  |                                                  |
|  +------------------+                                                  |
|                                                                        |
+------------------------------------------------------------------------+
```

**Nota de acessibilidade:** `role="alert"` na mensagem de erro para que screen readers anunciem automaticamente.

---

## Componentes Novos a Criar

| Componente | Arquivo | Tipo |
|---|---|---|
| `ProjectsTab.tsx` | `tabs/ProjectsTab.tsx` + `.module.css` | Nova aba — kanban de projetos |
| `PipelineTab.tsx` | `tabs/PipelineTab.tsx` + `.module.css` | Nova aba — configuração da pipeline |
| `ProjectCard.tsx` | `components/csm/ProjectCard.tsx` | Card reutilizável do kanban |
| `ProjectDetailPanel.tsx` | `components/csm/ProjectDetailPanel.tsx` | Side panel de detalhes |
| `ApprovalModal.tsx` | `components/csm/ApprovalModal.tsx` | Modal de aprovação para produção |
| `ChannelToggle.tsx` | `components/csm/ChannelToggle.tsx` | Toggle de canal com config expandível |
| `ApiKeyField.tsx` | `components/csm/ApiKeyField.tsx` | Campo mascarado para API keys |
| `PipelineProgress.tsx` | `components/csm/PipelineProgress.tsx` | Barra de progresso das etapas |
| `CostMeter.tsx` | `components/csm/CostMeter.tsx` | Indicador de custo R$XX/R$100 |

**Novos tipos no `CsmDashboard.tsx`:**
```typescript
export type ActiveTab = 'idea' | 'generate' | 'publish' | 'youtube'
                      | 'repurpose' | 'projects' | 'pipeline'   // novos
                      | 'settings' | 'telemetry';

export type ProjectStatus =
  | 'creating'       // Em Cocriação (IdeaTab ativo)
  | 'awaiting_approval'  // Aguardando Aprovação do Victor
  | 'generating_media'   // Pipeline rodando (TTS → Avatar → Editor)
  | 'awaiting_publication' // Pronto, aguardando aprovação de publicação
  | 'publishing'     // Publisher Service ativo
  | 'published'      // Concluído
  | 'error';         // Alguma etapa falhou
```


---

## Review

> **Revisor:** Product Lead Agent | **Data:** 2026-07

**Verdict:** NOT-READY

---

### Findings

#### Problemas Críticos (bloqueantes)

**F1 — Fluxo de "Aguardando Publicação" está incompleto**
O user-flow mostra um "Modal de publicação" com checkboxes por canal e horário opcional, mas esse modal não tem wireframe correspondente. A Tela 4 é o modal de *aprovação para produção* (antes da geração de mídia), não o modal de publicação final. Falta desenhar a tela de aprovação final — a diferença entre "aprovar para gerar" e "aprovar para publicar" é uma distinção arquitetural crítica documentada no scope-document (estados: `Gerando Mídia → Aguardando Publicação → Publicado`). O usuário vai encontrar um fluxo de aprovação em dois momentos distintos; apenas um foi wireframado.

**F2 — Nenhum fluxo de "Pular etapa" ou "Upload manual" está wireframado**
O user-flow (Fluxo de Recuperação) lista três opções de recuperação: `[Re-tentar]`, `[Pular esta etapa]` e `[Upload manual]`. A Tela 3 (Side Panel) e a Tela 6 (card em estado erro) mostram apenas `[Re-tentar etapa]` e `[Cancelar projeto]`. O scope-document (constraint COP-01) exige "endpoint de invocação manual como fallback" para cada etapa automatizada. O wireframe da Tela 3 precisa incluir o fluxo de upload manual — especialmente para o caso em que o HeyGen falha e Victor quer subir um vídeo de avatar gravado localmente.

**F3 — Custo estimado vs. custo real: dois momentos distintos não tratados**
A Tela 4 (aprovação) mostra custo estimado com HeyGen marcado como `(estim.)`. Mas a Tela 3 (side panel) mistura custo acumulado real com estimativas no mesmo bloco, sem distinção visual clara. Para um sistema onde o teto de R$100 é um gate arquitetural, o usuário precisa entender em todo momento o que é estimativa e o que é custo já incorrido. Falta uma especificação visual explícita dessa distinção (ex: valores estimados em cor diferente, label `~R$XX`).

---

#### Problemas Moderados (devem ser resolvidos antes do design refinado)

**F4 — Estado "Aguardando Publicação" não tem ação explícita no card do kanban**
O card "Teste Hipotese" na Tela 2 está no estado `PUBL` com links de resultado — parece já publicado. Mas falta mostrar como é o card no estado `awaiting_publication` (geração concluída, aguardando aprovação manual de publicação). Qual CTA aparece nesse estado? `[Publicar Agora]`? `[Agendar]`? Isso é o gatilho para o fluxo de publicação final que está descrito no user-flow mas não no wireframe.

**F5 — Filtros do kanban não refletem todos os estados do `ProjectStatus`**
Os filtros na Tela 2 são: `[Todos]`, `[Em Criacao]`, `[Aguardando]`, `[Gerando]`, `[Publicar]`, `[Publicado]`. Mas o tipo `ProjectStatus` define 7 estados incluindo `error` e `publishing`. O estado `error` é especialmente importante — Victor vai querer filtrar "só os projetos com erro" para triagem rápida. Adicionar `[Erro]` como filtro explícito.

**F6 — Tela 5 não mostra feedback de validação de API key**
O botão `[Testar ping]` existe, mas o wireframe não especifica o estado de resposta de erro: o que aparece se a API key for inválida (401) ou se o serviço estiver fora do ar (503)? A especificação visual atual só mostra o estado "ATIVO". Falta o estado "INATIVO / ERRO" com mensagem inline abaixo do campo da key.

**F7 — Agenda semanal não trata conflito de slots**
A Tela 5 mostra `Próximo conteúdo agendado: "RAG Avancado" — Ter 23 jul, 18:00`. Mas se Victor tem dois projetos em estado `awaiting_publication` para o mesmo dia, o que acontece? O wireframe não mostra nenhuma indicação de fila ou conflito de agendamento. Precisa de ao menos um estado que indique "slot ocupado" ou lista de próximos N agendamentos.

---

#### Pontos Fortes (confirmar e preservar no design refinado)

**P1 — AI Disclosure integrada ao fluxo de aprovação** — A Tela 4 trata a checkbox de AI disclosure como parte obrigatória do modal de aprovação, com nota da política YouTube maio/2026. Isso reflete o princípio "conformidade desde o início" do scope-document. Manter.

**P2 — Custo com teto visível em todo ponto de decisão** — A Tela 4 mostra o limite (R$100) com status `[OK, dentro do teto]` na mesma linha do total estimado. É o padrão certo: a decisão de custo está inline com a ação, não em outra tela.

**P3 — Side panel em vez de modal central para detalhes** — A escolha de `ProjectDetailPanel` como painel lateral preserva o contexto do kanban. Correto para um usuário solo que precisa revisar o estado sem perder a visão geral.

**P4 — Estado de erro com mensagem inline no card** — A Tela 6 mostra a mensagem de erro do log (`Playwright: timeout 30s`) diretamente no card, sem exigir navegação para descobrir a causa. Isso reduz o ciclo de diagnóstico para um usuário solo que opera sem suporte técnico.

**P5 — Campos de API key com mascaramento e `type="password"`** — A especificação da Tela 5 é explícita: `type="password"`, `autocomplete="off"`, nunca em texto claro no DOM. Isso captura a constraint de segurança corretamente.

**P6 — Componentes bem decompostos e reutilizáveis** — A tabela de novos componentes (`ProjectCard`, `CostMeter`, `ApiKeyField`, etc.) tem granularidade adequada para um solo developer. Cada componente tem responsabilidade única e será reutilizável entre as duas abas.

---

### O que deve ser entregue antes de avançar para Refined Mockups

1. **Wireframe da Tela 4B** — Modal de aprovação de *publicação* (distinto da aprovação de produção), com checkboxes por canal, opção "Publicar Agora" vs "Agendar", e validação de conflito de slot.
2. **Tela 3 revisada** — Side panel com opções de recuperação completas: `[Re-tentar]`, `[Pular etapa]`, `[Upload manual]` — e especificação do fluxo de upload manual (pelo menos o estado de seleção de arquivo).
3. **Distinção visual custo estimado vs. real** — Definir a convenção tipográfica/cromática (ex: prefixo `~` e cor âmbar para estimativas, valor real em branco).
4. **Card kanban em estado `awaiting_publication`** — CTA explícita, diferenciada dos outros estados.
5. **Filtro `[Erro]` no kanban** — Adicionar à barra de filtros da Tela 2.
6. **Estado de erro no campo de API key** — Inline na Tela 5, abaixo do campo, após `[Testar ping]` retornar falha.

---

## Revisão Pós-Review — Iteração 2

*Endereçando todos os findings do Product Lead Agent antes do gate.*

---

### Tela 4B: Modal de Aprovação de Publicação (novo)

*Distinto da Tela 4 (aprovação para produção). Este modal aparece quando o projeto está em `awaiting_publication` — a mídia já foi gerada e está pronta para ir ao ar.*

```
+------------------------------------------------------+
|  Publicar Conteudo                              [X]  |
|------------------------------------------------------|
|  "RAG Avancado"                                     |
|  Videos prontos em GCS  [preview horizontal] [v]    |
|                                                      |
|  PUBLICAR AGORA OU AGENDAR:                         |
|  (*) Publicar agora                                  |
|  ( ) Agendar para:  [23/07/2026] [18:00]            |
|      Fuso: America/Sao_Paulo                        |
|                                                      |
|  CANAIS (confirme cada canal):                      |
|  [x] YouTube  — video horizontal + disclosure IA    |
|  [x] YouTube Shorts — video vertical                |
|  [x] Instagram Reels — video vertical               |
|  [x] LinkedIn — post derivado                       |
|  [x] Threads — post derivado                        |
|  [x] Blog — artigo ja publicado (22 jul)            |
|  [ ] Facebook — desabilitado no painel              |
|                                                      |
|  CUSTO FINAL CONFIRMADO:                            |
|  ElevenLabs (TTS)    R$  4.13  [real]               |
|  HeyGen (Avatar)     R$ 54.00  [real]               |
|  Gemini (geracao)    R$  0.83  [real]               |
|  GCP (infra)         R$  2.75  [real]               |
|  Total:              R$ 61.71                        |
|                                                      |
|  [Cancelar]             [Publicar / Agendar]         |
+------------------------------------------------------+
```

*Diferença da Tela 4: aqui os custos são reais (não estimativas), os vídeos já existem no GCS, e o usuário pode agendar um horário específico.*

---

### Tela 3 Revisada — Side Panel com Recuperação Completa

Substituindo a seção ACOES do side panel original:

```
|                                          |-----------------------------|
|                                          |  ACOES                     |
|                                          |                            |
|                                          |  [Aprovar para Producao]   |
|                                          |   (se awaiting_approval)   |
|                                          |                            |
|                                          |  [Publicar / Agendar]      |
|                                          |   (se awaiting_publication)|
|                                          |                            |
|                                          |  SE ERRO:                  |
|                                          |  Etapa: Video Editor       |
|                                          |  Erro: Playwright timeout  |
|                                          |                            |
|                                          |  [Re-tentar etapa]         |
|                                          |  [Pular esta etapa]        |
|                                          |  [Upload manual]           |
|                                          |    -> abre file picker     |
|                                          |       aceita .mp4 (H ou V) |
|                                          |                            |
|                                          |  [Cancelar projeto]        |
|                                          +-----------------------------+
```

*Upload manual: ao clicar, abre um file picker nativo (`<input type="file" accept="video/mp4">`). O usuário seleciona o arquivo, que é enviado diretamente ao GCS. A pipeline retoma a partir da etapa seguinte (publicação).*

---

### Convenção Visual: Custo Estimado vs. Real

```
Estimativa (antes da execucao):
  HeyGen (Avatar)   ~R$ 54.00   <- prefixo "~", cor ambar (#f59e0b)

Real (apos execucao):
  HeyGen (Avatar)    R$ 54.00   <- sem prefixo, cor branco (#f8fafc)

Nao executado ainda:
  Video Editor       --          <- tracejado, cor cinza (#6b7280)
```

Esta convenção aplica-se na Tela 3 (side panel custo) e na Tela 4B (custo final).

---

### Tela 2 Revisada — Card em `awaiting_publication` e Filtro Erro

**Card no estado `awaiting_publication`:**

```
|  +------------------+                                                  |
|  | RAG Avancado     |                                                  |
|  | [====PRONTO] ciano                                                  |
|  |                  |                                                  |
|  | TTS   [x]        |                                                  |
|  | Avatar [x]       |                                                  |
|  | Video  [x]       |                                                  |
|  | Publi  [ ] aguar |                                                  |
|  |                  |                                                  |
|  | Custo: R$61/100  |                                                  |
|  | Pronto: 22 jul   |                                                  |
|  |                  |                                                  |
|  | [Publicar] [Ver] |  <- CTA principal muda para "Publicar"           |
|  +------------------+                                                  |
```

**Barra de filtros atualizada (Tela 2):**

```
+------------------------------------------------------------------------+
|  [Todos] [Em Criacao] [Aguardando] [Gerando] [Pronto] [Publicado] [!Erro]|
+------------------------------------------------------------------------+
```

`[!Erro]` tem cor vermelha `#ef4444` quando há projetos em estado erro; neutro quando vazio.

---

### Tela 5 Revisada — Estado de Erro em API Key

Após clicar `[Testar ping]` e receber erro:

```
|  ElevenLabs                                                          |
|  API Key:    [sk-*********************] [Editar] [Testar ping]       |
|  Status:     x INATIVO                                               |
|              Erro 401: API key invalida ou expirada.                 |
|              Verifique a key em elevenlabs.io/settings/api           |
|              [Testar novamente]                                       |
```

*O ícone `x` + texto "INATIVO" + mensagem inline garantem que o estado de erro não depende apenas de cor. O link para a página de settings do ElevenLabs reduz o tempo de resolução.*

---

### Tela 5B — Agenda com Fila de Próximos Agendamentos

Substituindo "Próximo conteúdo agendado" por uma fila visível:

```
|  AGENDA SEMANAL                                                        |
|  +------------------------------------------------------------------+  |
|  |  Horario padrao:                                                 |  |
|  |  Seg [Off v]  Ter [18:00 v]  Qua [18:00 v]                      |  |
|  |  Qui [18:00 v]  Sex [Off v]  Sab [Off v]                        |  |
|  |                                                                  |  |
|  |  PROXIMOS AGENDAMENTOS:                                          |  |
|  |  Ter 23 jul 18:00 — "RAG Avancado"                              |  |
|  |  Qua 24 jul 18:00 — [vazio — nenhum projeto na fila]            |  |
|  |  Qui 25 jul 18:00 — "Fine-Tuning LLMs" (pendente aprovacao)     |  |
|  |                                                                  |  |
|  |  Se dois projetos aprovados disputarem o mesmo slot:            |  |
|  |  o mais antigo tem prioridade. O segundo fica para o            |  |
|  |  proximo slot disponivel.                                        |  |
|  +------------------------------------------------------------------+  |
```


---

## Review (Iteração 2)

> **Revisor:** Product Lead Agent | **Data:** 2026-07 | **Iteração:** 2

**Verdict:** READY

---

### Findings Resolvidos

| # | Finding | Status | Observação |
|---|---|---|---|
| F1 | Wireframe da Tela 4B (modal de aprovação de publicação) | **RESOLVIDO** | Tela 4B entregue e completa: custos reais vs. estimados, opções "Publicar agora" / "Agendar", canais confirmatórios, distinção arquitetural clara da Tela 4 |
| F2 | Opções de recuperação completas (Re-tentar, Pular, Upload manual) | **RESOLVIDO** | Side panel revisado com as três opções, CTAs condicionais por estado, fluxo de upload manual especificado (file picker → GCS → retomada da pipeline) |
| F3 | Distinção visual custo estimado vs. real | **RESOLVIDO** | Convenção completa: prefixo `~` + âmbar (#f59e0b) para estimativas; branco (#f8fafc) para reais; tracejado + cinza (#6b7280) para não executados |
| F4 | Card `awaiting_publication` com CTA | **RESOLVIDO** | Card explícito com badge ciano `[====PRONTO]`, checklist de etapas, custo real, e CTA `[Publicar]` diferenciada |
| F5 | Filtro `[!Erro]` no kanban | **RESOLVIDO** | `[!Erro]` adicionado à barra de filtros com semântica de cor condicional; renomeação para `[Pronto]` é mais precisa que `[Publicar]` — mantida |
| F6 | Estado de erro na API key | **RESOLVIDO** | Estado INATIVO com ícone `x`, mensagem "Erro 401" inline, link direto para settings do provedor, botão `[Testar novamente]` |
| F7 | Fila de agendamentos | **RESOLVIDO** | Tela 5B com lista de próximos N slots (incluindo vazios e pendentes), e regra explícita de prioridade para conflito de slots |

---

### Observações Finais para o Design Refinado

**Inconsistência menor a normalizar (não bloqueante):**
A Tela 4B usa o label literal `[real]` nos itens de custo (`R$ 4.13 [real]`). A convenção definida na seção de distinção visual não prevê esse label — usa cor (branco) e ausência do `~` como sinal. No design refinado, remover o label `[real]` e aplicar apenas a convenção cromática para manter consistência. Usar `[real]` como text literal pode confundir quando o componente `CostMeter` for internacionalizado ou lido por screen readers.

**Pontos para preservar no design refinado:**
- Todos os pontos fortes P1–P6 identificados na Iteração 1 continuam válidos e presentes nos wireframes.
- A hierarquia de estados do `ProjectStatus` agora está completamente representada em wireframe: todos os 7 estados (`creating`, `awaiting_approval`, `generating_media`, `awaiting_publication`, `publishing`, `published`, `error`) têm representação visual correspondente.
- A distinção custo estimado / real / não executado definida aqui deve ser documentada como token de design no design system antes da implementação de `CostMeter.tsx`.
- O fluxo de upload manual (F2) implica uma rota nova na API (`POST /projects/:id/stages/:stage/manual-upload`); garantir que o scope-document e o backlog reflitam esse endpoint antes do código-geração.

