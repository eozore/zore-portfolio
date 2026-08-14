# Component Dependency
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Referências: [requirements.md](../requirements-analysis/requirements.md) | [stories.md](../user-stories/stories.md) | [team-practices.md](../practices-discovery/team-practices.md)

---

## Mapa de Dependências

```
Frontend Components:
  C-01 (ProjectsTab)
    depends on: C-03 (ProjectCard), C-04 (ProjectDetailPanel), 
                C-05 (ApprovalModal, PublishModal), C-06 (Route Handlers)
  C-02 (PipelineTab)
    depends on: C-08 (ConfigService via Route Handlers)
  C-03 (ProjectCard)
    depends on: (props only — nenhuma dependência direta de serviço)
  C-04 (ProjectDetailPanel)
    depends on: C-06 (retry/skip/upload endpoints)
  C-05 (ApprovalModal)
    depends on: C-06 (cost-estimate, approve endpoints)
  C-05 (PublishModal)
    depends on: C-06 (publish-preview, publish endpoints)
  C-06 (Route Handlers)
    depends on: Firestore, Pub/Sub, Secret Manager, GCS (via Firebase Admin + GCP clients)

Backend Services:
  C-09 (TTSJob)
    depends on: C-13 (CostTrackerService), ElevenLabs API, GCS, Firestore, Pub/Sub
  C-10 (AvatarJob)
    depends on: C-13 (CostTrackerService), HeyGen Assets API, HeyGen Lipsync API, 
                GCS, Firestore, Pub/Sub
  C-11 (VideoEditorJob)
    depends on: Playwright/Chromium, FFmpeg, GCS, Firestore, Pub/Sub
  C-12 (PublisherService)
    depends on: YouTube Data API v3, Meta Graph API, LinkedIn API, 
                C-07 (/api/csm/publish route), GCS, Firestore, Secret Manager
  C-13 (CostTrackerService)
    depends on: Firestore (apenas — sem dependências externas)
  C-14 (HeyGenCallbackHandler)
    depends on: Pub/Sub, Firestore
```

---

## Matriz de Dependências

| Componente | Firestore | GCS | Pub/Sub | Secret Manager | ElevenLabs | HeyGen | YouTube | Meta | LinkedIn | CMO Agent |
|---|---|---|---|---|---|---|---|---|---|---|
| C-06 (Route Handlers) | ✓ (R/W) | ✓ (R) | ✓ (W) | ✓ (R/W) | — | — | — | — | — | ✓ (proxy) |
| C-09 (TTSJob) | ✓ (R/W) | ✓ (R/W) | ✓ (R/W) | ✓ (R) | ✓ | — | — | — | — | — |
| C-10 (AvatarJob) | ✓ (R/W) | ✓ (R/W) | ✓ (R/W) | ✓ (R) | — | ✓ | — | — | — | — |
| C-11 (VideoEditorJob) | ✓ (R/W) | ✓ (R/W) | ✓ (R/W) | — | — | — | — | — | — | — |
| C-12 (PublisherService) | ✓ (R/W) | ✓ (R) | ✓ (R) | ✓ (R) | — | — | ✓ | ✓ | ✓ | ✓ (blog — intencional) |
| C-13 (CostTracker) | ✓ (R/W) | — | — | — | — | — | — | — | — | — |
| C-14 (HeyGenCallback) | ✓ (R) | — | ✓ (W) | — | — | — | — | — | — | — |

---

## Fluxo de Dados End-to-End

```
Victor (browser)
    |
    | 1. Clica "Aprovar para Produção"
    v
C-06 Route Handler (/projects/{id}/approve)
    |
    | 2. Escreve approval_data no Firestore
    | 3. Publica package_approved no Pub/Sub
    v
C-09 TTSJob [Pub/Sub trigger]
    |
    | 4. Lê manifesto do GCS
    | 5. Chama ElevenLabs (por segmento, com retry)
    | 6. Salva MP3s no GCS
    | 7. Atualiza project.stages.tts no Firestore
    | 8. Publica tts_completed no Pub/Sub
    v
C-10 AvatarJob [Pub/Sub trigger]
    |
    | 9. Concatena áudios (horizontal + vertical)
    | 10. Upload áudio para HeyGen Assets API
    | 11. Cria jobs HeyGen Lipsync v3 (H + V)
    | 12. Registra lipsync_ids no Firestore, aguarda callback
    v
    HeyGen (externa) — processa 5-45 min
    |
    | 13. HeyGen chama POST /heygen-callback
    v
C-14 HeyGenCallbackHandler
    |
    | 14. Valida origem HeyGen
    | 15. Publica avatar_completed no Pub/Sub
    v
C-11 VideoEditorJob [Pub/Sub trigger]
    |
    | 16. Lê manifesto e avatar do GCS
    | 17. Renderiza slides via Playwright (por segmento)
    | 18. Compõe vídeo via FFmpeg (H + V)
    | 19. Aplica jump cuts
    | 20. Salva vídeos finais no GCS
    | 21. Publica video_ready no Pub/Sub
    v
    Firestore atualiza → Frontend ProjectCard atualiza via listener
    Victor vê "Pronto!" no kanban
    |
    | 22. Victor clica "Publicar" → PublishModal
    | 23. Clica "Publicar / Agendar"
    v
C-06 Route Handler (/projects/{id}/publish) — modo imediato
    |
    | 24. Chama publisher-immediate service via HTTP
    v
C-12 PublisherService (imediato)
    |
    | 25. Verifica approval_status
    | 26. Publica em cada canal habilitado (independente)
    | 27. Registra resultado no Firestore
    v
    Firestore atualiza → Frontend ProjectCard atualiza para "Publicado"
```

---

## Dados Compartilhados e Ownership

| Recurso | Owner (escreve) | Consumers (lê) | Notas |
|---|---|---|---|
| `content_projects/{id}` | C-06 (criação/aprovação), C-09/10/11/12 (stages), C-13 (cost) | C-01/03/04 (UI via listener), C-12 (publisher) | Documento compartilhado — campos por dono |
| `pipeline_config/{tenant}` | C-08 (ConfigService) | C-09/10/11/12 (cost rates, limits) | Config lida pelos jobs no início |
| `channel_config/{tenant}/{channel}` | C-08 | C-12 (enabled, throttler) | Jobs respeitam config |
| `gs://.../audio/` | C-09 (TTSJob) | C-10 (AvatarJob) | Passado via Pub/Sub path |
| `gs://.../avatar_*.mp4` | C-10 (AvatarJob via HeyGen download) | C-11 (VideoEditorJob) | Passado via Pub/Sub path |
| `gs://.../final_*.mp4` | C-11 (VideoEditorJob) | C-12 (PublisherService), C-06 (publish-preview) | Signed URLs geradas pelo C-06 |
| Secret Manager | C-08 (ConfigService) | C-09/10/11/12 (lê keys na inicialização) | Cada job lê secrets pertinentes |

---

## Comunicação Síncrona vs. Assíncrona

| Par de Componentes | Padrão | Protocolo | Razão |
|---|---|---|---|
| Frontend → C-06 | Síncrono | HTTP/REST | Resposta imediata necessária para UX |
| C-06 → Pub/Sub | Assíncrono | Pub/Sub publish | Fire-and-forget; jobs executam em background |
| C-09/10/11/12 → Firestore | Síncrono (async Python) | Firestore SDK | Atualização de estado para o listener do frontend |
| HeyGen → C-14 | Assíncrono | HTTP webhook | HeyGen entrega callback quando pronto |
| C-14 → Pub/Sub | Assíncrono | Pub/Sub publish | Desacopla o handler do job downstream |
| C-06 (Route Handlers) → C-12 (imediato) | Síncrono | HTTP | "Publicar Agora" requer confirmação rápida. URL via env var `PUBLISHER_IMMEDIATE_URL` |
| Cloud Scheduler → C-12 | Assíncrono | HTTP (Cloud Scheduler) | Publicação agendada batch |
| C-12 (PublisherService) → C-06 (blog) | Síncrono | HTTP interno | Dependência intencional — reusa rota existente; falha isolada não afeta outros canais |
