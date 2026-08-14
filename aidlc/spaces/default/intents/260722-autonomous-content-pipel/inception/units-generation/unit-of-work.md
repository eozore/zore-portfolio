# Units of Work
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Referências: [components.md](../application-design/components.md) | [component-methods.md](../application-design/component-methods.md) | [services.md](../application-design/services.md) | [component-dependency.md](../application-design/component-dependency.md) | [decisions.md](../application-design/decisions.md) | [requirements.md](../requirements-analysis/requirements.md) | [stories.md](../user-stories/stories.md)

---

## Resumo das Unidades

| ID | Unidade | Componentes | Deployment | Complexidade |
|---|---|---|---|---|
| U-01 | `firestore-schema` | Schema, models, tipos compartilhados | N/A (config/código) | S |
| U-02 | `pubsub-infra` | Tópicos e subscriptions Pub/Sub + Cloud Scheduler | N/A (infra GCP) | S |
| U-03 | `projects-api` | C-07 (ProjectService) como Route Handlers | Next.js (`apps/web`) | M |
| U-04 | `config-api` | C-08 (ConfigService) como Route Handlers | Next.js (`apps/web`) | M |
| U-05 | `projects-tab-ui` | C-01 (ProjectsTab), C-03 (ProjectCard), C-04 (ProjectDetailPanel) | Next.js (`apps/web`) | L |
| U-06 | `pipeline-tab-ui` | C-02 (PipelineTab), C-05 (ApprovalModal, PublishModal) | Next.js (`apps/web`) | M |
| U-07 | `pipeline-shared-lib` | C-13 (CostTrackerService), shared models Python, retry module | Container image `pipeline` | S |
| U-08 | `tts-job` | C-09 (TTSJob) | Cloud Run Job | M |
| U-09 | `avatar-job` | C-10 (AvatarJob) | Cloud Run Job | L |
| U-10 | `heygen-callback` | C-14 (HeyGenCallbackHandler) | Cloud Run Service | S |
| U-11 | `video-editor-job` | C-11 (VideoEditorJob) | Cloud Run Job | XL |
| U-12 | `publisher-service` | C-12 (PublisherService, ambos os modos) | Cloud Run Job + Cloud Run Service | L |
| U-13 | `cloudbuild-pipeline` | `cloudbuild-pipeline.yaml`, Dockerfiles, deploy manifests | CI/CD (Cloud Build) | M |

**Total: 13 unidades**

---

## U-01: `firestore-schema`

**Descrição:** Definição do schema Firestore e dos modelos de dados compartilhados entre frontend e backend.

**Responsabilidades:**
- TypeScript types para `ContentProject`, `ProjectStatus`, `StageStatus`, `CostBreakdown`, `Channel`, `PublicationResult`
- Python dataclasses/TypedDicts equivalentes em `agents/pipeline/shared/models.py`
- Schema Firestore em `firestore.rules` e `firestore.indexes.json` (incluindo índice para `collection_group('lipsync_jobs')`)
- Constantes compartilhadas: `STAGE_IDS`, `CHANNEL_IDS`, `PUB_SUB_TOPICS`

**Deployment:** Código no monorepo — tipos em `apps/web/src/types/pipeline.ts` e `agents/pipeline/shared/models.py`. Regras e índices em `firestore.rules` / `firestore.indexes.json`.

**Complexidade:** S — sem lógica de negócio, apenas tipos e schema.

**Testes Nyquist (1):**
- Validação de schema: dado um documento `content_projects` válido, os types TypeScript e dataclasses Python aceitam sem erro de tipo.

**Constraints:**
- O índice `collection_group` para `lipsync_jobs.lipsync_id` deve ser gerado antes do deploy do U-10 (HeyGenCallbackHandler)
- Deve ser o primeiro a ser implementado — todos os outros dependem deste schema

---

## U-02: `pubsub-infra`

**Descrição:** Provisionamento dos tópicos Pub/Sub, subscriptions push/pull, e configuração do Cloud Scheduler.

**Responsabilidades:**
- Criar tópicos Pub/Sub: `content-pipeline.package-approved`, `content-pipeline.tts-completed`, `content-pipeline.avatar-completed`, `content-pipeline.video-ready`
- Criar subscriptions: push subscription para cada Cloud Run Job receptor
- Configurar Cloud Scheduler: job diário por horário configurável chamando `publisher-scheduled`
- Permissões IAM: cada Cloud Run Service/Job com a service account mínima necessária

**Deployment:** `gcloud` CLI ou Terraform — executado uma vez no setup do projeto GCP.

**Complexidade:** S — são comandos de provisionamento, não código de aplicação.

**Testes Nyquist (1):**
- Smoke test: publicar mensagem de teste no tópico `package-approved` e verificar que a subscription a entrega (via `gcloud pubsub subscriptions pull`).

**Constraints:**
- Deve existir antes de qualquer Job ser deployado
- IAM: Pub/Sub service account deve ter `roles/pubsub.publisher` para o Next.js e os Jobs

---

## U-03: `projects-api`

**Descrição:** Route Handlers Next.js que implementam o C-07 (ProjectService) — CRUD de projetos, aprovação, publicação, fallback manual.

**Responsabilidades:**
- `GET/POST /api/csm/projects` — listar e criar projetos
- `GET /api/csm/projects/[id]` — detalhes do projeto
- `GET /api/csm/projects/[id]/cost-estimate` — estimar custo
- `POST /api/csm/projects/[id]/approve` — gate de aprovação para produção
- `GET /api/csm/projects/[id]/publish-preview` — GCS signed URLs + custo real
- `POST /api/csm/projects/[id]/publish` — gate de aprovação de publicação
- `POST /api/csm/projects/[id]/retry-stage` — re-disparar job
- `POST /api/csm/projects/[id]/skip-stage` — pular etapa
- `POST /api/csm/projects/[id]/stages/[stage]/manual-upload` — upload manual de MP4

**Deployment:** Parte do build `apps/web` no Cloud Run Service `web`.

**Complexidade:** M — múltiplos endpoints, lógica de validação, integração com Firestore + Pub/Sub + GCS.

**Testes Nyquist (3):**
- `POST /approve`: dado projeto com custo estimado ≤ teto, retorna `{ ok: true }` e estado muda para `generating_media` no Firestore
- `POST /approve`: dado custo estimado > teto, retorna `CostExceedsLimitError` (HTTP 422)
- `POST /stages/[stage]/manual-upload`: dado arquivo MP4 válido, salva no GCS e retoma pipeline via Pub/Sub

**Constraints:**
- Requer `PUBLISHER_IMMEDIATE_URL` env var para `POST /publish` modo `now`
- Depende de U-01 (tipos) e U-02 (Pub/Sub tópicos)

---

## U-04: `config-api`

**Descrição:** Route Handlers Next.js que implementam o C-08 (ConfigService) — configuração segura de pipeline, keys, OAuth.

**Responsabilidades:**
- `GET/POST /api/csm/pipeline/config` — CRUD de configurações globais
- `POST /api/csm/pipeline/config/keys` — salvar API keys no Secret Manager
- `GET /api/csm/pipeline/config/ping` — testar autenticação de provider
- `POST /api/csm/pipeline/config/youtube-oauth` — iniciar fluxo OAuth
- `GET /api/csm/pipeline/config/youtube-oauth/callback` — receber callback OAuth

**Deployment:** Parte do build `apps/web`.

**Complexidade:** M — integração com Secret Manager + OAuth 2.0 + múltiplos providers.

**Testes Nyquist (2):**
- `POST /keys`: dado uma API key válida do ElevenLabs, salva no Secret Manager e retorna `{ saved: true }` sem retornar o valor
- `GET /ping`: dado provider `elevenlabs` com key válida no Secret Manager, retorna `{ ok: true, latencyMs: number }`

**Constraints:**
- NUNCA retornar o valor de API keys para o frontend
- Depende de U-01 (tipos Firestore para `channel_config`)

---

## U-05: `projects-tab-ui`

**Descrição:** Componentes React da aba "Projetos" — kanban com estado em tempo real, side panel e ações contextuais.

**Responsabilidades:**
- `ProjectsTab.tsx` — layout, filtros, grid responsivo, Firestore listener para `content_projects`
- `ProjectCard.tsx` — card com 7 estados visuais, CostMeter compacto, PipelineProgress compacto
- `ProjectDetailPanel.tsx` — side panel com etapas expandidas, custo real vs estimado, ações de recuperação, seção de publicações
- Hooks: `useProjects()`, `useProject(id)` com Firestore listeners
- CSS Modules para todos os componentes

**Deployment:** Parte do build `apps/web`.

**Complexidade:** L — múltiplos estados, Firestore listeners, interações com U-03.

**Testes Nyquist (2):**
- `ProjectCard` com `status: 'retrying'`: renderiza spinner âmbar + "Tentativa N de 3 (automático)" + **sem CTAs manuais**
- `ProjectsTab` com filtro `error`: exibe apenas cards com `status === 'error'` em < 200ms

**Constraints:**
- CSS Modules exclusivamente (constraint C-03, descoberto em practices-discovery)
- Depende de U-01 (tipos), U-03 (endpoints de aprovação/publicação)
- Pode ser desenvolvido em paralelo com U-08/U-09/U-10/U-11 após U-01 estar disponível

---

## U-06: `pipeline-tab-ui`

**Descrição:** Componentes React da aba "Pipeline" — configuração de canais, keys, limites, agenda + modais de aprovação.

**Responsabilidades:**
- `PipelineTab.tsx` — painel de config com 4 seções (canais, APIs, custo, agenda)
- `ApiKeyField.tsx` — campo mascarado com modo edit, ping e estados de loading
- `ChannelToggle.tsx` — toggle com config expandível por canal
- `ApprovalModal.tsx` — modal de aprovação para produção (custo estimado, AI disclosure)
- `PublishModal.tsx` — modal de aprovação de publicação (custo real, agendamento)
- `CostMeter.tsx` — barra de custo com gradiente e estados alerta/excedido
- `PipelineProgress.tsx` — progresso das etapas com estados `retrying`/`error`/`completed`

**Deployment:** Parte do build `apps/web`.

**Complexidade:** M — muitos componentes mas lógica relativamente simples; maior complexidade é `ApprovalModal` e `PublishModal`.

**Testes Nyquist (2):**
- `ApprovalModal` com custo estimado > teto: botão "Aprovar" desabilitado + alerta visível
- `ApiKeyField` em modo edit: campo `type="password"` com `autocomplete="off"`, campo vazio (nunca pré-preenchido)

**Constraints:**
- Depende de U-01 (tipos: `ApprovalModalProps`, `PublishModalProps`)
- Depende de U-04 (endpoints `/config/keys`, `/config/ping`)
- Pode ser desenvolvido em paralelo com U-05

---

## U-07: `pipeline-shared-lib`

**Descrição:** Código Python compartilhado entre todos os Cloud Run Jobs — modelos de dados, retry, CostTrackerService.

**Responsabilidades:**
- `agents/pipeline/shared/models.py` — dataclasses para `ContentProject`, `Manifest`, `Segment`, `AudioResult`, `PublicationResult`, `LipsyncJob`
- `agents/pipeline/shared/retry.py` — `with_retry()` com backoff [1,4,16]s + distinção transitório/permanente
- `agents/pipeline/shared/cost_tracker.py` — `CostTrackerService` com estimativas e `check_cost_gate()`
- `agents/pipeline/shared/firestore_client.py` — wrapper do Firestore Admin SDK
- `agents/pipeline/shared/pubsub_client.py` — wrapper do Pub/Sub client

**Deployment:** Código em `agents/pipeline/shared/` incluído na imagem unificada `gcr.io/{project}/pipeline`.

**Complexidade:** S — sem lógica de negócio complexa; o mais interessante é o retry e o CostTracker.

**Testes Nyquist (2):**
- `with_retry()`: dado função que lança HTTP 429 duas vezes e sucede na terceira, executa 3 vezes e retorna sucesso
- `CostTrackerService.check_cost_gate()`: dado custo acumulado R$85 + estimativa R$20 + limite R$100, retorna `False` e atualiza `cost_blocked` no Firestore

**Constraints:**
- Deve ser a base de todos os Jobs Python (U-08 a U-12)
- `exchange_rate_usd_brl` lido do Firestore `pipeline_config`, não hardcoded

---

## U-08: `tts-job`

**Descrição:** Cloud Run Job Python que processa TTS via ElevenLabs API para todos os segmentos do manifesto.

**Responsabilidades:**
- Entry point: consome `package_approved` do Pub/Sub
- Lê manifesto HTML do GCS, extrai segmentos
- Chama ElevenLabs API por segmento (com retry via U-07)
- Salva MP3 por segmento no GCS
- Reporta custo via U-07 CostTrackerService
- Publica `tts_completed` no Pub/Sub

**Deployment:** Cloud Run Job, CMD `python -m tts_job`, usa imagem `gcr.io/{project}/pipeline`.

**Complexidade:** M — integração com ElevenLabs API, GCS, Pub/Sub.

**Testes Nyquist (1):**
- Happy path: dado manifesto com 3 segmentos e ElevenLabs mock retornando MP3 válido, 3 arquivos são salvos no GCS e `tts_completed` é publicado no Pub/Sub com `segment_count: 3`

**Constraints:**
- Depende de U-07 (shared lib) e U-02 (Pub/Sub topics)
- ElevenLabs API key via Secret Manager
- Independente de U-09, U-10, U-11 no código (mas sequencial na pipeline em runtime)

---

## U-09: `avatar-job`

**Descrição:** Cloud Run Job Python que processa geração de avatar via HeyGen Lipsync API v3.

**Responsabilidades:**
- Entry point: consome `tts_completed` do Pub/Sub
- Concatena áudios por formato (horizontal + vertical)
- Faz upload para HeyGen Assets API
- Cria dois jobs Lipsync (`POST /v3/lipsyncs`) com `callback_url`
- Registra `stages.avatar.lipsync_jobs.{horizontal,vertical}` no Firestore
- O job termina após criar os jobs HeyGen; não aguarda conclusão

**Deployment:** Cloud Run Job, CMD `python -m avatar_job`, timeout 150 min.

**Complexidade:** L — integração com HeyGen API v3, dois jobs simultâneos, schema `lipsync_jobs`.

**Testes Nyquist (2):**
- Happy path: dado áudios concatenados e HeyGen mock retornando `lipsync_id`, os dois `lipsync_id`s são salvos no Firestore em `stages.avatar.lipsync_jobs`
- Custo gate: dado custo acumulado próximo do teto, `check_cost_gate()` bloqueia antes de chamar HeyGen

**Constraints:**
- Depende de U-07 (shared lib, schema `lipsync_jobs`)
- HeyGen API key via Secret Manager
- Depende de U-10 (HeyGenCallbackHandler) estar deployado antes do primeiro uso em produção — o callback precisa de destino

---

## U-10: `heygen-callback`

**Descrição:** Cloud Run Service Python que recebe webhooks HeyGen e orquestra a publicação de `avatar_completed`.

**Responsabilidades:**
- `POST /heygen-callback` com payload `{ lipsync_id, status, video_url }`
- Valida token secreto no header `X-HeyGen-Token`
- Resolve `lipsync_id → project_id` via query Firestore `collection_group('lipsync_jobs')`
- Atualiza `stages.avatar.lipsync_jobs.{horizontal|vertical}` no Firestore
- Quando **ambos** horizontal e vertical estão `completed`, publica `avatar_completed` no Pub/Sub

**Deployment:** Cloud Run Service (sempre online), CMD `uvicorn heygen_callback:app --port 8091`.

**Complexidade:** S — endpoint simples; a lógica de "ambos completados" é o núcleo.

**Testes Nyquist (2):**
- Primeiro callback chega (horizontal): atualiza Firestore, **não** publica `avatar_completed`
- Segundo callback chega (vertical): atualiza Firestore, **publica** `avatar_completed`

**Constraints:**
- Requer índice Firestore `collection_group` para `lipsync_jobs` (U-01)
- Token secreto `HEYGEN_CALLBACK_TOKEN` no Secret Manager
- URL pública deste serviço é o `callback_url` passado ao HeyGen na U-09

---

## U-11: `video-editor-job`

**Descrição:** Cloud Run Job Python que compõe o vídeo final (horizontal + vertical) com slides e avatar.

**Responsabilidades:**
- Entry point: consome `avatar_completed` do Pub/Sub
- Renderiza cada slide HTML via Playwright (serializado, um por vez)
- Compõe vídeo com FFmpeg: avatar + slides nos timestamps do manifesto
- Aplica jump cuts (remoção de silêncios > 0.8s)
- Salva vídeos finais no GCS
- Publica `video_ready` no Pub/Sub

**Deployment:** Cloud Run Job, CMD `python -m video_editor_job`, **memory: 4Gi**, timeout 60 min.

**Complexidade:** XL — Playwright + FFmpeg + composição determinística; maior Job da pipeline.

**Testes Nyquist (2):**
- Composição horizontal: dado manifesto com 3 segmentos e avatarvídeo mock, `final_horizontal_cut.mp4` é gerado no GCS com duração = soma das durações dos segmentos
- Playwright serialização: Chromium é fechado (`browser.close()`) entre cada slide render (verificado via mock de Playwright)

**Constraints:**
- Imagem deve ter Playwright + FFmpeg + flags `--disable-dev-shm-usage --no-sandbox`
- Memory: 4 GB no Cloud Run Job definition
- Depende de U-07 (shared lib)

---

## U-12: `publisher-service`

**Descrição:** Cloud Run Service/Job Python que publica conteúdo em todos os canais habilitados.

**Responsabilidades:**
- Modo Job (`publisher-scheduled`): consome `video_ready` ou é disparado pelo Cloud Scheduler
- Modo Service (`publisher-immediate`): endpoint HTTP para "Publicar Agora"
- Verifica `approval_status: "approved"` antes de publicar
- Publica independentemente em cada canal: YouTube, YouTube Short, Instagram Reel, Threads, LinkedIn, Blog
- **Canal Blog:** escrita direta no Firestore `articles` via Firebase Admin SDK Python (sem chamar o Route Handler Next.js) — elimina acoplamento HTTP Python → Next.js identificado pelo Architecture Reviewer (Finding 4, Opção B)
- Registra resultado em `project.publications` no Firestore
- Respeita throttler por canal

**Deployment:** Duas formas da mesma imagem. Job: CMD `python -m publisher_job`. Service: CMD `uvicorn publisher_immediate:app --port 8092`.

**Complexidade:** L — 6 integrações externas com lógica de isolamento de falha.

**Testes Nyquist (3):**
- YouTube publish: dado `approval_status: "approved"` e YouTube habilitado, chama YouTube Data API v3 com `selfDeclaredAiGeneratedContent: True`
- Isolamento de falha: dado Instagram retornando 503, outros canais (LinkedIn, Threads) prosseguem normalmente
- Throttler: dado LinkedIn no limite diário, pula LinkedIn e registra `status: "throttled"`

**Constraints:**
- Depende de U-07 (shared lib), U-01 (schema `publications`)
- Todos os OAuth tokens via Secret Manager
- Depende de U-03 (`/api/csm/publish` para o canal Blog)

---

## U-13: `cloudbuild-pipeline`

**Descrição:** Pipeline CI/CD dedicada para os microserviços da content pipeline.

**Responsabilidades:**
- `agents/pipeline/Dockerfile` — imagem unificada com Python + Playwright + FFmpeg
- `cloudbuild-pipeline.yaml` — build, push e deploy de todos os Cloud Run Jobs/Services da pipeline
- Cloud Run Job definitions para TTS, Avatar, VideoEditor, PublisherScheduled
- Cloud Run Service definitions para HeyGenCallback, PublisherImmediate
- Variáveis de ambiente e `--set-secrets` para cada serviço

**Deployment:** Cloud Build trigger separado do `cloudbuild.yaml` do web app.

**Complexidade:** M — YAML complexo mas sem lógica de negócio.

**Testes Nyquist (1):**
- Build bem-sucedido: `gcloud builds submit` sem erros; imagem `gcr.io/{project}/pipeline:latest` disponível no Artifact Registry

**Constraints:**
- Separado do `cloudbuild.yaml` do web app (ADR em decisions.md)
- Deve ser deployado antes de qualquer Job ser testado em Cloud Run
