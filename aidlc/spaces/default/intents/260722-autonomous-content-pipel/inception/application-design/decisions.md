# Architecture Decision Records
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Referências: [requirements.md](../requirements-analysis/requirements.md) | [stories.md](../user-stories/stories.md) | [team-practices.md](../practices-discovery/team-practices.md)

---

## ADR-01: Arquitetura de Microserviços via Pub/Sub (não chamadas síncronas encadeadas)

**Status:** Aceito

**Contexto:**
A pipeline tem 4 etapas com latências variáveis e muito altas: TTS (~30s), HeyGen (~5-45 min), VideoEditor (~10-30 min), Publisher (~2-5 min). Uma arquitetura síncrona encadeada resultaria em timeouts inevitáveis e nenhuma observabilidade de progresso.

**Decisão:**
Cada etapa é um Cloud Run Job independente. A comunicação entre etapas é via mensagens Pub/Sub. O estado é persistido no Firestore após cada job, permitindo recovery e observabilidade em tempo real.

**Consequências:**
- (+) Cada job pode ser desenvolvido, testado e deployado independentemente
- (+) Falha em um job não afeta outros; retry granular
- (+) Frontend tem visibilidade em tempo real via Firestore listener
- (-) Complexidade operacional maior (múltiplos containers vs. um monolito)
- (-) Debugging requer correlação de logs entre múltiplos serviços

**Alternativas Rejeitadas:**
- REST chain síncrono: inviável (timeouts > 60 min para HeyGen)
- n8n/Make.com: inadequado para jobs de longa duração (feasibility stage)
- Cloud Workflows: adiciona dependência sem benefício claro vs. Pub/Sub puro

---

## ADR-02: Imagem Docker Unificada para todos os Jobs Python

**Status:** Aceito

**Contexto:**
Os jobs TTS, Avatar, VideoEditor, Publisher e o HeyGenCallbackHandler todos usam Python + GCP clients. O VideoEditorJob precisa adicionalmente de Playwright + FFmpeg (heavy).

**Decisão:**
Um único Dockerfile `agents/pipeline/Dockerfile` gera a imagem `gcr.io/{project}/pipeline`. O job específico é selecionado via `CMD` override no Cloud Run Job definition. A imagem inclui Playwright + FFmpeg (necessário apenas para VideoEditorJob, mas o overhead de imagem é aceitável dado o uso em produção).

**Consequências:**
- (+) Um único cloudbuild-pipeline.yaml faz o build e push de tudo
- (+) Dependências compartilhadas gerenciadas em um único requirements.txt
- (-) Imagem maior (~2GB no disco) do que seriam imagens individuais (~200MB cada)
- (-) Deploy de um job exige rebuild de todos (mitigado por layer caching)
- (-) VideoEditorJob: Playwright + FFmpeg + Python em runtime pode atingir 1.5–1.8 GB de RAM em pico para vídeos de 15 min. Solução: `video-editor-job` configurado com `memory: 4Gi` (não 2 GB). Playwright serializado (um render por vez com `browser.close()` explícito) — nunca paralelizado. Flags Chromium obrigatórias: `--disable-dev-shm-usage --no-sandbox`.

**Alternativas Rejeitadas:**
- Imagens separadas por job: mais builds, mais YAMLs de Cloud Run, sem ganho funcional para uso solo
- Distroless/minimal sem Playwright: impossível para VideoEditorJob

---

## ADR-03: HeyGen via Callback (não polling)

**Status:** Aceito

**Contexto:**
HeyGen Lipsync API v3 pode levar 5-45 minutos para processar. NFR-02 exige alertar em 60 min e falhar em 90 min. Polling a cada 30s por 45 min = ~90 chamadas de API desnecessárias.

**Decisão:**
Usar `callback_url` da Lipsync API v3. O AvatarJob cria os jobs HeyGen e registra os `lipsync_ids` no Firestore. O HeyGenCallbackHandler (Cloud Run Service mínimo) recebe o webhook e publica `avatar_completed` no Pub/Sub. O AvatarJob termina após criar os jobs; não aguarda a conclusão.

**Consequências:**
- (+) Zero polling — nenhuma chamada desnecessária à API HeyGen
- (+) Escalável: callback funciona para vídeos de qualquer duração
- (-) Requer um endpoint HTTP público (`/heygen-callback`) com autenticação
- (-) Complexidade adicional do HeyGenCallbackHandler (novo serviço)

**Segurança do callback:**
O HeyGen deve suportar `callback_id` customizado que incluímos como `project_id`. Validação via token secreto compartilhado no header `X-HeyGen-Token` (armazenado no Secret Manager).

**Schema de mapeamento lipsync_id → project_id (Finding 1):**

O AvatarJob registra ambos os `lipsync_id`s no Firestore ao criar os jobs HeyGen:

```
content_projects/{project_id}/stages/avatar/lipsync_jobs:
  horizontal:
    lipsync_id: "string"
    status: "pending" | "completed" | "failed"
    video_url: string | null
  vertical:
    lipsync_id: "string"
    status: "pending" | "completed" | "failed"
    video_url: string | null
```

O HeyGenCallbackHandler resolve `lipsync_id → project_id` via query Firestore:
```python
# Query por lipsync_id em ambos os subcampos
projects = firestore.collection_group('lipsync_jobs')
    .where('lipsync_id', '==', received_lipsync_id)
    .limit(1)
    .get()
# Ou: query simples na coleção content_projects
# com where clause em stages.avatar.lipsync_jobs.horizontal.lipsync_id
# OU stages.avatar.lipsync_jobs.vertical.lipsync_id
```

Atualiza o subcampo correspondente. Só publica `avatar_completed` quando **ambos** horizontal.status e vertical.status são `"completed"`.

**Alternativas Rejeitadas:**
- Polling ativo no AvatarJob (Cloud Run Job não pode ficar ligado por 45 min sem processar — ineficiente)
- Polling via Cloud Scheduler a cada 5 min: adiciona latência desnecessária

---

## ADR-04: Publisher com dois modos — Job (scheduled) e Service (imediato)

**Status:** Aceito

**Contexto:**
"Publicar Agora" (US-05) exige resposta rápida ao frontend. Cloud Run Job tem overhead de ~10s de startup, inaceitável para uma ação do usuário. "Publicação agendada" (US-10) é batch e não precisa de resposta ao frontend.

**Decisão:**
Publisher Service existe em duas formas:
1. `publisher-scheduled` (Cloud Run Job) — disparado pelo Cloud Scheduler, lida com a fila
2. `publisher-immediate` (Cloud Run Service) — endpoint HTTP chamado pela Route Handler quando Victor clica "Publicar Agora"

Ambos usam o mesmo código Python; apenas o modo de invocação difere.

**Consequências:**
- (+) "Publicar Agora" tem latência adequada (< 5s para iniciar publicação)
- (+) Publicação agendada usa Job sem custo de instância idle
- (-) Dois endpoints para a mesma lógica de publicação (gerenciados por feature flag ou argumento de entrada)
- (-) A URL do `publisher-immediate` é resolvida via variável de ambiente obrigatória `PUBLISHER_IMMEDIATE_URL`, injetada no Cloud Run Service `web` via `--set-env-vars` no deploy. O valor é a URL do Cloud Run Service `publisher-immediate` (obtida via `gcloud run services describe publisher-immediate --format='value(status.url)'`). Em desenvolvimento local, aponta para `http://localhost:8092`.

**Alternativas Rejeitadas:**
- Apenas Job mode para "Publicar Agora": latência de startup inaceitável
- Apenas Service mode para tudo: instância idle 24/7 desnecessária

---

## ADR-05: ConfigService embedded em Route Handlers (não microserviço separado)

**Status:** Aceito

**Contexto:**
A configuração é escrita raramente (uma vez por semana no melhor caso). Criar um microserviço Python dedicado para isso seria over-engineering.

**Decisão:**
ConfigService vive nos Route Handlers do Next.js (`/api/csm/pipeline/config`). Firebase Admin SDK lê/escreve Firestore e Secret Manager diretamente. A regra de segurança "NUNCA retornar a key real" é enforced na Route Handler.

**Consequências:**
- (+) Menos um container para gerenciar
- (+) Acesso direto ao Firebase Admin ADC já configurado
- (-) Lógica de configuração não é reutilizável por serviços Python (eles leem o Secret Manager diretamente)

**Alternativas Rejeitadas:**
- Microserviço Python dedicado: overhead injustificável para operação rara
- Acesso direto ao Secret Manager pelo frontend: violação do constraint de segurança

---

## ADR-06: Painel de Configuração como Aba (não rota dedicada)

**Status:** Aceito — resolve OQ-03

**Contexto:**
O painel de configuração precisa de acesso à Session do CSM Studio (tenantId, autenticação). Uma rota dedicada (`/pipeline`) exigiria replicar o AuthGate e o layout do Dashboard.

**Decisão:**
Aba "Pipeline" no `CsmDashboard` existente (`ActiveTab: 'pipeline'`). Segue exatamente o mesmo padrão de todas as outras abas existentes (IdeaTab, GenerateTab, etc.).

**Consequências:**
- (+) Zero mudanças no routing Next.js
- (+) Reutiliza autenticação existente
- (-) Não é bookmarkável como URL independente (aceitável para uso solo)

---

## ADR-07: Scheduler por Projeto, não por Canal

**Status:** Aceito — resolve OQ-07/OQ-08

**Contexto:**
OQ-07/OQ-08 questionavam se o Cloud Scheduler deveria selecionar projetos por canal (publicar projeto A no LinkedIn, projeto B no YouTube no mesmo disparo) ou por projeto inteiro.

**Decisão:**
O Scheduler opera por projeto — seleciona o projeto mais antigo em `awaiting_publication` e tenta publicar em todos os seus canais habilitados. Se um canal está throttled, registra `publications.{canal}.status: "throttled"` mas não bloqueia os outros canais. O mesmo projeto será re-selecionado no próximo disparo do Scheduler para re-tentar os canais throttled.

**Consequências:**
- (+) Lógica simples: um projeto por disparo do Scheduler
- (+) Canais throttled são re-tentados automaticamente no dia seguinte
- (-) Um projeto com muitos canais throttled pode ocupar o "slot do dia" por vários dias (Victor pode resolver via "Pular canal" no side panel)

**Alternativas Rejeitadas:**
- Scheduler por canal (multi-projeto por disparo): lógica de conflito complexa, concorrência de escrita no Firestore

---

## ADR-08: CostTrackerService como módulo, não microserviço

**Status:** Aceito

**Contexto:**
O rastreamento de custo precisa ser chamado por cada Job (TTS, Avatar, Editor). Um microserviço HTTP adicional criaria latência e um ponto adicional de falha para cada chamada de API paga.

**Decisão:**
`CostTrackerService` é um módulo Python (shared library) importado pelos Jobs. Acessa Firestore diretamente. Implementado em `agents/pipeline/shared/cost_tracker.py`.

**Consequências:**
- (+) Zero latência adicional (chamada local, não HTTP)
- (+) Sem ponto de falha adicional
- (-) Lógica de custo duplicada se precisarmos chamar de Next.js (Route Handlers usarão um cálculo estimado próprio)
- (-) Taxa de câmbio: campo `exchange_rate_usd_brl` em `pipeline_config/{tenantId}` (default: 5.50). Victor atualiza quando necessário. O `CostTrackerService` lê do Firestore no início de cada job — sem dependência de API de câmbio externa. Isso evita variações cambiais silenciosas quebrando o `check_cost_gate()`.

---

## ADR-09: Carrosseis via Template HTML + Playwright (não Gemini Imagen)

**Status:** Aceito — resolve OQ-04

**Contexto:**
Carrosseis (FR-06 Bolt 5) podem ser gerados via template HTML renderizado pelo mesmo pipeline do VideoEditorJob, ou via geração de imagem por IA (Gemini Imagen, DALL-E).

**Decisão:**
Template HTML estático renderizado via Playwright pelo VideoEditorJob. O manifesto pode incluir um deck de "slides estáticos" (`DECKS.carousel`) com layout responsivo para imagem quadrada (1:1) ou retrato (4:5). Saída: PNG por slide, enviado via Meta Carousel API.

**Consequências:**
- (+) Zero custo adicional de API de geração de imagem
- (+) Consistência visual garantida (mesmo design system dos slides de vídeo)
- (+) Playwright já está no container — sem nova dependência
- (-) Menos "criatividade" visual que um modelo generativo
- (-) Requer design de templates HTML para cada estilo de carrossel

**Alternativas Rejeitadas:**
- Gemini Imagen: custo adicional, qualidade imprevisível, dependência de aprovação de conteúdo gerado

---

## Review

**Verdict: NOT-READY — 1 gap bloqueante, 2 moderados, 2 menores. Todos resolvíveis antes de Units Generation.**

Revisor: aidlc-architecture-reviewer-agent  
Artefatos revisados: `components.md`, `services.md`, `component-methods.md`, `component-dependency.md`, `decisions.md`

---

### Finding 1 — `lipsync_id → project_id`: gap de mapeamento no HeyGenCallbackHandler
**Severidade: Bloqueante**

O fluxo documentado é: AvatarJob cria dois jobs HeyGen (horizontal + vertical) via `POST /v3/lipsyncs` e recebe dois `lipsync_id`s. O HeyGenCallbackHandler recebe o webhook com `{ lipsync_id, status, video_url }` e precisa publicar `avatar_completed` com o `project_id` correspondente — mas **nenhum artefato documenta como esse mapeamento é feito**.

ADR-03 diz "registra os `lipsync_ids` no Firestore" sem especificar o schema. O `component-dependency.md` mostra que C-14 lê do Firestore (`✓ (R)`) mas não há campo `lipsync_id` descrito no schema de `content_projects`. Sem esse mapeamento, o HeyGenCallbackHandler não tem como correlacionar o callback ao projeto.

**Adicionalmente:** o AvatarJob cria **dois** jobs HeyGen (horizontal e vertical). O callback chega para cada um separadamente. O HeyGenCallbackHandler precisa aguardar os dois antes de publicar `avatar_completed` — essa lógica de "ambos completaram?" também está ausente. Se publicar `avatar_completed` no primeiro callback, o VideoEditorJob recebe apenas um dos vídeos.

**Resolução requerida antes de Units Generation:**
1. Adicionar ao schema de `content_projects` um subcampo `stages.avatar.lipsync_jobs: { horizontal: { lipsync_id, status, video_url }, vertical: { lipsync_id, status, video_url } }`
2. AvatarJob escreve ambos os `lipsync_id`s nesse subcampo ao criar os jobs HeyGen
3. HeyGenCallbackHandler: ao receber callback, faz query Firestore por `stages.avatar.lipsync_jobs.*.lipsync_id == lipsync_id` para resolver o `project_id`, atualiza o subcampo correspondente, e só publica `avatar_completed` quando **ambos** os status forem `completed`
4. Documentar esse subcampo no `component-dependency.md` na tabela "Dados Compartilhados e Ownership"

---

### Finding 2 — VideoEditorJob: risco de OOM em vídeos longos
**Severidade: Moderado**

A imagem unificada soma ~2GB no disco, mas o uso de RAM em runtime é o problema. Para um vídeo de 15 min com slides HTML:

- Playwright/Chromium: 300–500 MB por instância (o processo Chromium é pesado)
- FFmpeg `filter_complex` para composição de avatar + slides em HD: 400–800 MB dependendo do buffer de decode/encode e da resolução
- Python process + GCP clients + libs: ~150–200 MB
- Vídeo avatar em RAM durante composição: para 15 min em 1080p, o buffer intermediário pode chegar a 500 MB

**Total estimado: 1.5–1.8 GB em pico.** Com o limite configurado em 2 GB, o headroom é de apenas 200–500 MB. Qualquer vazamento de memória no Playwright ou buffer extra do FFmpeg causa OOM kill sem log de erro útil.

Agravante: se os slides forem renderizados em batches sem liberar o processo Chromium entre slides, a pressão sobe rapidamente.

**Resolução recomendada:**
- Aumentar o `memory` do `video-editor-job` para **4 GB** no YAML de Cloud Run Job
- No VideoEditorJob, serializar renderização de slides (um Playwright por vez, com `page.close()` e `browser.close()` explícitos entre renders) — não paralelizar
- Passar `--disable-dev-shm-usage` e `--no-sandbox` nas flags do Chromium
- Documentar essa decisão em ADR-02 (consequências da imagem unificada)

---

### Finding 3 — URL do `publisher-immediate`: não documentada
**Severidade: Moderado**

O método `approveForPublication` (C-07) com `mode='now'` deve "chamar publisher-immediate via HTTP", mas nenhum artefato documenta:
- Como a URL do Cloud Run Service `publisher-immediate` é resolvida pelo Next.js
- Se é uma variável de ambiente (`PUBLISHER_IMMEDIATE_URL`), um endpoint fixo, ou service discovery via metadata server
- Quem injeta essa variável no Cloud Run Service `web` no deploy

Sem isso, a implementação vai exigir uma decisão ad-hoc no momento do código, provavelmente hardcoded — o que cria um problema de configuração entre ambientes (dev local vs. Cloud Run prod).

**Resolução recomendada:**
- Adicionar `PUBLISHER_IMMEDIATE_URL` como variável de ambiente obrigatória no Cloud Run Service `web`
- Documentar em `services.md` na tabela de Cloud Run Services, coluna "Variáveis de Ambiente"
- No `component-methods.md`, explicitar: `const url = process.env.PUBLISHER_IMMEDIATE_URL` no método `approveForPublication`
- O valor em prod é a URL do Cloud Run Service `publisher-immediate` (disponível via `gcloud run services describe`)

---

### Finding 4 — Taxa de câmbio fixa R$5.50/USD
**Severidade: Menor**

`CostTrackerService.update_actual_cost()` usa taxa fixa. O `cost_limit` está em BRL (strings "R$/min", "R$/char" nos estimators). HeyGen cobra em USD. Com variação cambial de ±15% (cenário realista para o real), um projeto com custo estimado de R$275 pode custar R$317 na taxa real — excedendo o teto silenciosamente. O sistema nunca bloquearia porque `check_cost_gate()` compara valores em BRL calculados pela mesma taxa fixa.

Para operação solo com volumes baixos, o impacto financeiro é pequeno. O risco principal é mais de previsibilidade do que de perda financeira.

**Resolução recomendada (menor esforço):**
- Adicionar `exchange_rate_usd_brl` como campo configurável em `pipeline_config/{tenantId}` (já lido pelos jobs no início)
- Victor atualiza manualmente quando necessário — sem dependência de API de câmbio
- `update_actual_cost()` lê do Firestore em vez de usar constante hardcoded
- Documentar em ADR-08: "taxa de câmbio configurável, default R$5.50/USD"

---

### Finding 5 — Dependência PublisherService → Next.js Route Handler (blog) e margem do AvatarJob timeout
**Severidade: Menor**

**5a. Ciclo backend→frontend→backend:**  
C-12 (PublisherService Python) chama `POST /api/csm/publish` no Next.js (C-06) para publicar no blog. Isso cria uma dependência do serviço Python em um endpoint HTTP do frontend — arquiteturalmente invertida. Se o Cloud Run Service `web` reiniciar durante uma publicação, o PublisherService falha no canal blog. Como é uso solo e o blog já tem essa rota implementada, o impacto é baixo, mas merece ser documentado explicitamente em `component-dependency.md` como dependência intencional (não acidental).

**5b. Margem do AvatarJob:**  
`await_lipsync_completion()` tem timeout de 90 min. O AvatarJob tem timeout de 120 min. Os outros passos do AvatarJob (concatenação de áudio, upload para HeyGen Assets API) podem levar 5–15 min para conteúdo longo. A margem efetiva é de 15–30 min — válida para o caso normal (HeyGen em 45 min), mas sem headroom para um HeyGen lento. Se HeyGen levar 90 min + startup + uploads, o Cloud Run Job vai expirar antes do callback.

Resolução: aumentar o timeout do `avatar-job` de 120 para **150 min** no YAML de Cloud Run Job. O custo de compute idle é negligenciável (Cloud Run Job não cobra pelo tempo aguardando IO).

---

### Observações para Units Generation

1. **Schema Firestore obrigatório:** Antes de gerar units para C-10 e C-14, o schema de `content_projects` deve incluir `stages.avatar.lipsync_jobs` com os subcampos do Finding 1. Units sem esse schema vão gerar interfaces TypeScript e dataclasses Python incompatíveis.

2. **Variável de ambiente `PUBLISHER_IMMEDIATE_URL`:** Deve aparecer nos manifests de Cloud Run (`services.yaml` ou `cloudbuild`) e no `.env.local` de desenvolvimento. Units para C-06/C-07 dependem disso.

3. **Configuração do VideoEditorJob:** O YAML do Cloud Run Job deve especificar `memory: 4Gi` e as flags Chromium. Units para C-11 devem incluir esses parâmetros na fixture de configuração.

4. **Dois callbacks, uma publicação:** A unit do HeyGenCallbackHandler deve incluir test cases para: (a) primeiro callback chega → não publica `avatar_completed`; (b) segundo callback chega → publica. Essa lógica de "ambos completados" é o coração do C-14.

5. **Sem gaps circulares bloqueantes:** A dependência C-12→C-06 (blog) é intencional e documentada. Não há ciclo que impeça a ordem de deploy (C-06 sobe antes de C-12 ser invocado em produção).


---

## Review (Iteração 2)

**Verdict: READY**

Revisor: aidlc-architecture-reviewer-agent | Iteração: 2  
Artefatos verificados: `decisions.md`, `services.md`, `component-dependency.md`

---

### Tabela de Resolução — Findings 1–5

| # | Finding | Severidade | Status | Evidência |
|---|---|---|---|---|
| 1 | Schema `lipsync_jobs.{horizontal,vertical}` + lógica "ambos completados antes de `avatar_completed`" | Bloqueante | **RESOLVIDO** | Schema em `services.md` §Firestore Collections; lógica com snippet Python e condição explícita em ADR-03 `decisions.md` |
| 2 | Memory `video-editor-job` = 4 GB + serialização Playwright + flags Chromium | Moderado | **RESOLVIDO** | Tabela Cloud Run Jobs em `services.md` mostra `4 GB`; ADR-02 consequências documenta serialização e `--disable-dev-shm-usage --no-sandbox` |
| 3 | `PUBLISHER_IMMEDIATE_URL` documentada em ADR-04 + tabela de comunicação | Moderado | **RESOLVIDO** | ADR-04 consequências detalha a env var, como injetá-la e o valor em dev/prod; `component-dependency.md` tabela de comunicação menciona `URL via env var PUBLISHER_IMMEDIATE_URL` |
| 4 | Campo `exchange_rate_usd_brl` em `pipeline_config` + ADR-08 | Menor | **RESOLVIDO** | `services.md` §Firestore Collections inclui o campo com `default: 5.50`; ADR-08 consequências documenta a leitura do Firestore e a ausência de dependência de API externa |
| 5a | Dependência C-12→C-06 (blog) como intencional em `component-dependency.md` | Menor | **RESOLVIDO** | Tabela de comunicação: linha `C-12 → C-06 (blog)` marcada como "Dependência intencional — reusa rota existente; falha isolada não afeta outros canais" |
| 5b | Timeout `avatar-job` = 150 min em `services.md` | Menor | **RESOLVIDO** | Tabela Cloud Run Jobs em `services.md` mostra `150 min` |

---

### Observações para Units Generation

Nenhum bloqueante remanescente. Os artefatos estão prontos para Units Generation com os seguintes pontos de atenção:

1. **Schema `lipsync_jobs` como contrato de interface:** O schema `stages.avatar.lipsync_jobs.{horizontal,vertical}` é o ponto de acoplamento entre C-10 (AvatarJob), C-14 (HeyGenCallbackHandler) e C-11 (VideoEditorJob). As units desses três componentes devem usar o mesmo schema — recomendar geração de um `dataclass` ou `TypedDict` Python compartilhado em `agents/pipeline/shared/models.py` para evitar drift.

2. **Unit do HeyGenCallbackHandler — dois casos obrigatórios:** (a) primeiro callback (`horizontal` ou `vertical`) → atualiza subcampo, **não** publica `avatar_completed`; (b) segundo callback → atualiza subcampo, verifica que ambos `status == "completed"`, **publica** `avatar_completed`. Esses dois casos são o núcleo funcional de C-14 e não podem ser omitidos das units.

3. **`PUBLISHER_IMMEDIATE_URL` como dependência de deploy explícita:** A unit de C-06/C-07 (`approveForPublication` modo `now`) deve incluir fixture de env var `PUBLISHER_IMMEDIATE_URL`. O YAML de Cloud Run Service `web` deve declarar a variável como obrigatória — ausência em deploy deve ser um erro explícito, não silencioso.

4. **`exchange_rate_usd_brl` como parâmetro de fixture:** Units do `CostTrackerService` devem receber a taxa de câmbio via `pipeline_config` mockado (não hardcoded `5.50`). Isso valida o caminho de leitura do Firestore e facilita testes com taxas variadas.

5. **Ordem de deploy sem dependência circular:** C-06 (Next.js `web`) deve ser deployado antes de C-12 (PublisherService) ser invocado em produção — a dependência C-12→C-06 é call-time, não boot-time, portanto não há bloqueio no pipeline de CI/CD. Units podem ser desenvolvidas em paralelo.