# Components
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Referências: [requirements.md](../requirements-analysis/requirements.md) | [stories.md](../user-stories/stories.md) | [team-practices.md](../practices-discovery/team-practices.md)

---

## Visão Geral da Arquitetura

```
+------------------------------------------------------------------+
|  FRONTEND (Next.js App Router — apps/web)                        |
|                                                                  |
|  CsmDashboard                                                    |
|  +--ProjectsTab     +--PipelineTab                              |
|     (kanban UI)        (config UI)                              |
|                                                                  |
|  API Routes (Route Handlers)                                    |
|  /api/csm/projects/[id]/*    /api/csm/pipeline/config/*         |
+------------------------------------------------------------------+
                    |  HTTP/REST  |  Firestore Listener
                    v             v
+------------------------------------------------------------------+
|  GOOGLE CLOUD PLATFORM                                           |
|                                                                  |
|  +---------------+  Pub/Sub  +-------------+  Pub/Sub          |
|  | CMO Agent     |---------->| TTS Job     |---------->         |
|  | (Cloud Run    |           | (Cloud Run  |                   |
|  |  Service)     |           |  Job)       |                   |
|  +---------------+           +-------------+                   |
|                                    |                            |
|                              Pub/Sub: tts_completed             |
|                                    v                            |
|                              +-------------+  Pub/Sub           |
|                              | Avatar Job  |---------->          |
|                              | (Cloud Run  |                    |
|                              |  Job)       |                    |
|                              +-------------+                    |
|                                    |                            |
|                              Pub/Sub: avatar_completed          |
|                                    v                            |
|                              +------------------+               |
|                              | Video Editor Job |               |
|                              | (Cloud Run Job)  |               |
|                              +------------------+               |
|                                    |                            |
|                              Pub/Sub: video_ready               |
|                                    v                            |
|                              +------------------+               |
|                              | Publisher Service|               |
|                              | (Cloud Run Job)  |               |
|                              +------------------+               |
|                                                                  |
|  Infrastructure:                                                |
|  Firestore  GCS  Pub/Sub  Secret Manager  Cloud Scheduler       |
+------------------------------------------------------------------+
```

---

## Componentes Frontend

### C-01: `ProjectsTab` (React Component)

**Propósito:** Kanban principal — lista todos os `content_projects` com estado em tempo real.

**Responsabilidades:**
- Subscribir ao Firestore listener em `content_projects` (coleção inteira, filtrada por `tenantId`)
- Renderizar grid responsivo de `ProjectCard` (4/2/1 colunas)
- Gerenciar filtro de estado (`ProjectStatus`)
- Orquestrar abertura do `ProjectDetailPanel` e dos modais

**Interface Pública:**
- `onCreateProject()` — navegação para IdeaTab com projeto vazio criado
- Estado local: `filter: ProjectStatus | 'all'`, `selectedProjectId: string | null`

**Não faz:** chamadas de API diretas — delega para hooks React; não contém lógica de negócio.

---

### C-02: `PipelineTab` (React Component)

**Propósito:** Painel de configuração da pipeline — canais, API keys, limites de custo, agenda.

**Responsabilidades:**
- Gerenciar CRUD de configurações de canais via `usePipelineConfig` hook
- Orquestrar `ApiKeyField`, `ChannelToggle`, `CostLimitConfig`, `ScheduleEditor`
- Executar pings de status de API via `GET /api/csm/pipeline/config/ping`
- Disparar fluxo OAuth YouTube (popup)

**Interface Pública:**
- Nenhuma prop externa — lê e escreve config via hook
- Emite `onConfigSaved()` para notificações toast

---

### C-03: `ProjectCard` (React Component)

**Propósito:** Card individual do kanban com estado visual e CTAs contextuais.

**Responsabilidades:**
- Renderizar estado visual baseado em `ProjectStatus`
- Exibir `PipelineProgress` compacto (checklist de etapas)
- Exibir `CostMeter` compacto
- Disparar ações: abrir side panel, abrir ApprovalModal, abrir PublishModal, re-tentar

**Props:** `project: ContentProject`, `onOpenPanel: (id) => void`, `onApprove: (id) => void`, `onPublish: (id) => void`

---

### C-04: `ProjectDetailPanel` (React Component)

**Propósito:** Side panel com detalhes completos do projeto, custo real vs estimado, e ações contextuais.

**Responsabilidades:**
- Subscribir ao listener Firestore do projeto selecionado
- Exibir `PipelineProgress` expandido com `retryCount` e `errorType`
- Exibir seção de Resultados de Publicação (pós-publicação)
- Orquestrar ações de recuperação: retry-stage, skip-stage, manual-upload

**Props:** `projectId: string | null`, `onClose: () => void`

---

### C-05: `ApprovalModal` + `PublishModal` (React Components)

**Propósito:** Gates de aprovação com custo estimado/real e seleção de canais.

**Responsabilidades:**
- `ApprovalModal`: busca custo estimado via `/cost-estimate`, valida contra teto, submete aprovação
- `PublishModal`: busca preview via `/publish-preview`, oferece agendamento, submete publicação

**Props:** Ver interfaces TypeScript em `refined-mockups/mockups.md`

---

### C-06: Next.js Route Handlers (API Layer)

**Propósito:** Camada de API do frontend — ponte entre UI e serviços GCP.

**Responsabilidades:**
- Autenticar via Firebase Admin SDK (session token)
- Ler/escrever Firestore via Firebase Admin SDK
- Publicar mensagens Pub/Sub via Google Cloud Pub/Sub client
- Ler secrets do Secret Manager
- Proxy de requests para CMO Agent Python (para operações já existentes)

**Rotas principais:**
```
/api/csm/projects                → C-07 (ProjectService)
/api/csm/pipeline/config         → C-08 (ConfigService)
/api/csm/pipeline/config/keys    → C-08 (ConfigService)
/api/csm/pipeline/config/ping    → C-08 (ConfigService)
```

---

## Componentes Backend (GCP Cloud Run)

### C-07: `ProjectService` (Embedded em Route Handlers Next.js)

**Propósito:** CRUD de projetos e orquestração de aprovação.

**Responsabilidades:**
- Criar documento `content_projects` no Firestore
- Validar custo estimado antes da aprovação
- Escrever `approval_data` no Firestore e publicar `package_approved` no Pub/Sub
- Endpoints de fallback manual (retry, skip, upload)
- Fornecer `publish-preview` (GCS signed URLs)

**Nota:** Não é um microserviço separado — vive nos Route Handlers do Next.js. Acessa Firestore e Pub/Sub diretamente via Firebase Admin SDK e Google Cloud client libs.

---

### C-08: `ConfigService` (Embedded em Route Handlers Next.js)

**Propósito:** Gestão segura de configurações de pipeline.

**Responsabilidades:**
- CRUD de `pipeline_config` e `channel_config` no Firestore
- Ler/escrever API keys no GCP Secret Manager
- Executar pings de autenticação nas APIs externas (ElevenLabs, HeyGen)
- Iniciar fluxo OAuth YouTube (redirect handler)

**Segurança:** NUNCA retornar valores de API keys para o frontend. Retornar apenas `{ saved: true }` ou `{ masked: "sk-****" }`.

---

### C-09: `TTSJob` (Cloud Run Job — Python)

**Propósito:** Geração de áudio por segmento via ElevenLabs API.

**Responsabilidades:**
- Consumir mensagem Pub/Sub `package_approved` com `{ project_id }`
- Ler manifesto HTML do GCS (`manifest_url` do Firestore)
- Chamar ElevenLabs API para cada `segment.script` do manifesto
- Salvar MP3 por segmento em GCS: `projects/{id}/audio/{segment_id}.mp3`
- Atualizar `project.stages.tts` no Firestore (status, retry_count, cost_real)
- Publicar `tts_completed` no Pub/Sub com `gcs_audio_paths[]`

**Retry:** 3 tentativas com backoff (1s, 4s, 16s) para HTTP 429/503. HTTP 401/403 → erro imediato.

---

### C-10: `AvatarJob` (Cloud Run Job — Python)

**Propósito:** Geração de vídeo avatar via HeyGen Lipsync API v3.

**Responsabilidades:**
- Consumir `tts_completed` do Pub/Sub
- Concatenar áudios dos segmentos (horizontal: todos; vertical: segmentos do deck `vert`)
- Fazer upload do áudio concatenado para HeyGen Assets API (`POST /v3/assets`)
- Criar jobs Lipsync (`POST /v3/lipsyncs`) para horizontal e vertical (modo `precision`)
- Registrar callback URL e aguardar via Pub/Sub (não polling ativo)
- Quando callback recebido: baixar vídeos para GCS
- Publicar `avatar_completed` no Pub/Sub

**Callback handler:** Cloud Run Service mínimo (`/heygen-callback`) que recebe o webhook HeyGen e publica `avatar_completed` no Pub/Sub.

---

### C-11: `VideoEditorJob` (Cloud Run Job — Python)

**Propósito:** Composição determinística de vídeo horizontal e vertical.

**Responsabilidades:**
- Consumir `avatar_completed` do Pub/Sub
- Ler manifesto para obter mapeamento `segment → slide`
- Renderizar cada slide HTML via Playwright (Chromium headless)
- Compor vídeo via FFmpeg: avatar + slides nos timestamps calculados pela duração do MP3
- Aplicar jump cuts (remover silêncios > 0.8s)
- Publicar `video_ready` no Pub/Sub com URLs dos vídeos finais

**Sem Gemini alignment:** O manifesto tem `segment.slide` explícito. Duração calculada a partir do MP3 (ffprobe). Pipeline completamente determinístico.

---

### C-12: `PublisherService` (Cloud Run Job + Cloud Run Service — Python)

**Propósito:** Publicação omnicanal em todos os canais habilitados.

**Responsabilidades:**
- Consumir `video_ready` do Pub/Sub (modo Job para Scheduler)
- Receber chamada HTTP do Next.js (modo Service para "Publicar Agora")
- Verificar `approval_status: "approved"` antes de qualquer publicação
- Publicar em cada canal habilitado de forma independente (falha isolada)
- Respeitar throttler por canal
- Registrar resultado de cada publicação no Firestore `project.publications`

**Canais:** YouTube (Data API v3), YouTube Shorts, Instagram Reels, Threads, LinkedIn, Blog (`/api/csm/publish`)

---

### C-13: `CostTrackerService` (Utilitário Python — shared module)

**Propósito:** Rastreamento de custo por etapa e por pacote.

**Responsabilidades:**
- Calcular custo de cada chamada de API paga (ElevenLabs, HeyGen)
- Atualizar `project.cost_breakdown` no Firestore após cada job
- Verificar se custo acumulado + estimativa excede o teto antes de iniciar cada job
- Emitir evento de bloqueio (`project.cost_blocked`) se teto seria excedido

**Não é um serviço separado:** é um módulo Python importado pelos Jobs (TTSJob, AvatarJob, VideoEditorJob).

---

### C-14: `HeyGenCallbackHandler` (Cloud Run Service — Python)

**Propósito:** Receptor do webhook HeyGen quando lipsync job completa.

**Responsabilidades:**
- Receber `POST /heygen-callback` com `{ lipsync_id, status, video_url }`
- Validar HMAC (ou token secreto) para autenticar a origem HeyGen
- Publicar `avatar_completed` no Pub/Sub com o `project_id` correspondente

**Nota:** É um endpoint HTTP público mínimo. Deve ter URL configurada no `callback_url` da chamada `POST /v3/lipsyncs`.
