# Bolt Plan
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Referências: [requirements.md](../requirements-analysis/requirements.md) | [stories.md](../user-stories/stories.md) | [mockups.md](../refined-mockups/mockups.md) | [components.md](../application-design/components.md) | [unit-of-work.md](../units-generation/unit-of-work.md) | [unit-of-work-dependency.md](../units-generation/unit-of-work-dependency.md) | [unit-of-work-story-map.md](../units-generation/unit-of-work-story-map.md) | [team-practices.md](../practices-discovery/team-practices.md)
>
> Walking Skeleton: Bolt 1. Sequência: Bolts 1→2→3→4→5 sem gates inter-Bolt (team.md § Walking Skeleton). Falhas param e apresentam retry/skip/abort.

---

## Visão Geral dos Bolts

| Bolt | Nome | Unidades | Complexidade | Hipótese de Confiança |
|---|---|---|---|---|
| **0** | `foundations` | U-01, U-02 | S+S | Schema e infra GCP existem e são válidos |
| **1** | `walking-skeleton` | U-07, U-08, U-09, U-10, U-13 | S+M+L+S+M | Pipeline TTS→Avatar→HeyGen funciona end-to-end; custo real dentro do teto |
| **2** | `video-editor` | U-11 | XL | Vídeo horizontal e vertical gerados deterministicamente a partir do manifesto |
| **3** | `publisher-core` | U-12, U-03 | L+M | Publicação automática no YouTube com AI disclosure e nos canais Meta/LinkedIn |
| **4** | `studio-ui` | U-04, U-05, U-06 | M+L+M | Victor opera a pipeline completa via CSM Studio sem acessar código |
| **5** | `distribution` | — (conteúdo derivado) | M | Carrosseis, Shorts e Community Posts publicados automaticamente |

---

## Bolt 0: `foundations`

**Tipo:** Fundação (não é Walking Skeleton — é pré-requisito de deploy)

**Unidades:**
- **U-01** (`firestore-schema`) — tipos TypeScript + dataclasses Python + Firestore rules/indexes
- **U-02** (`pubsub-infra`) — tópicos Pub/Sub + subscriptions + Cloud Scheduler + IAM

**Por que separado:** U-01 e U-02 não têm lógica de negócio mas são pré-requisitos duros de todas as outras unidades. Completar antes de qualquer Job ser implementado elimina erros de tipo e falhas de infra nos Bolts seguintes.

**Definition of Done:**
- [ ] `firestore.rules`, `firestore.indexes.json` deployados no projeto GCP
- [ ] Tipos TypeScript em `apps/web/src/types/pipeline.ts` com `ProjectStatus`, `ContentProject`, `StageStatus`
- [ ] Dataclasses Python em `agents/pipeline/shared/models.py`
- [ ] 4 tópicos Pub/Sub criados e verificados via smoke test
- [ ] Cloud Scheduler job criado (dispara diariamente)
- [ ] 1 teste Nyquist: query `collection_group('lipsync_jobs').limit(1)` retorna sem erro 400

**Hipótese de Confiança:** Schema e infra são válidos — nenhum Job falha por tipo errado ou tópico inexistente.

---

## Bolt 1: `walking-skeleton` ⭐

**Tipo:** Walking Skeleton — prova as duas integrações de maior risco antes de qualquer construção adicional

**Unidades:**
- **U-07** (`pipeline-shared-lib`) — CostTrackerService, retry module, shared models
- **U-08** (`tts-job`) — Cloud Run Job Python: ElevenLabs TTS por segmento
- **U-09** (`avatar-job`) — Cloud Run Job Python: HeyGen Lipsync v3
- **U-10** (`heygen-callback`) — Cloud Run Service: receptor de webhook HeyGen
- **U-13** (`cloudbuild-pipeline`) — Dockerfile unificado + `cloudbuild-pipeline.yaml`

**Camadas arquiteturais provadas:**
- Camada de infra: Pub/Sub tópicos → Jobs Cloud Run
- Camada de integração: ElevenLabs API, HeyGen Assets API, HeyGen Lipsync v3
- Camada de persistência: Firestore (schema `lipsync_jobs`, `cost_breakdown`)
- Camada de callback: endpoint HTTP público + autenticação via token
- Camada de CI/CD: imagem Docker unificada + deploy pipeline

**Definition of Done:**
- [ ] TTS Job processa todos os segmentos de um manifesto real e gera MP3s no GCS
- [ ] Avatar Job cria dois jobs HeyGen (horizontal + vertical) com `lipsync_ids` salvos no Firestore
- [ ] HeyGen Callback Handler recebe dois callbacks e publica `avatar_completed` apenas quando ambos completam
- [ ] Custo real do par de vídeos (horizontal + vertical) medido e registrado no Firestore — dentro de R$80 (margem para demais etapas)
- [ ] `cloudbuild-pipeline.yaml` faz build/deploy com sucesso
- [ ] 2 testes Nyquist de U-09 passam (lipsync_id mappings) + 2 de U-10 (dois callbacks)

**Hipótese de Confiança:** O fluxo TTS→Avatar→HeyGen funciona de ponta a ponta. O custo real HeyGen para um vídeo de 15 min está dentro do teto de R$100. Se o custo exceder R$80, o plano de custo precisa ser revisado antes do Bolt 2.

**Go/No-Go:** Se o custo real HeyGen for > R$80 ou se a qualidade de lipsync for inaceitável (avaliação de Victor), o projeto para para replanejamento arquitetural antes de prosseguir.

**Pré-condições humanas obrigatórias (Victor executa antes do Bolt 1):**
- [ ] Conta ElevenLabs com voz clonada configurada, `voice_id` no Secret Manager
- [ ] Conta HeyGen com Avatar IV, API key no Secret Manager
- [ ] GCP Pub/Sub API ativada no projeto
- [ ] URL pública do HeyGen Callback Handler obtida via `gcloud run services describe`

---

## Bolt 2: `video-editor`

**Unidades:**
- **U-11** (`video-editor-job`) — Cloud Run Job Python: Playwright + FFmpeg, composição determinística H+V

**Por que em Bolt separado:** U-11 é a unidade mais complexa (XL) e o maior risco técnico operacional restante (OOM, Playwright em Alpine). Isolá-la permite validação específica sem afetar o pipeline de TTS/Avatar já validado.

**Definition of Done:**
- [ ] Vídeo horizontal (1920×1080) gerado com avatar + slides sincronizados a partir do manifesto
- [ ] Vídeo vertical (1080×1920) gerado corretamente
- [ ] Jump cuts aplicados (silêncios > 0.8s removidos)
- [ ] Memory do Cloud Run Job confirmado ≤ 4GB em execução real
- [ ] Playwright serializado: `browser.close()` chamado entre cada slide render
- [ ] Vídeos finais disponíveis no GCS, mensagem `video_ready` publicada no Pub/Sub
- [ ] 2 testes Nyquist de U-11 passam

**Hipótese de Confiança:** A composição determinística (sem Gemini alignment) funciona. Playwright + FFmpeg rodam no Cloud Run com 4GB sem OOM para vídeos de até 15 min.

**Go/No-Go:** Se VideoEditorJob der OOM para vídeo de 15 min mesmo com 4GB, investigar se composição sequencial de slides (não batch) resolve antes de prosseguir.

---

## Bolt 3: `publisher-core`

**Unidades:**
- **U-12** (`publisher-service`) — Cloud Run Job + Service: publicação omnicanal
- **U-03** (`projects-api`) — Route Handlers Next.js: CRUD de projetos + endpoints de aprovação/fallback

**Por que agrupados:** U-12 depende do schema Firestore de `publications` (U-01) e o Publisher Service imediato é chamado via U-03. Implementar ambos no mesmo Bolt garante que o gate de publicação (US-05) e a publicação real (US-08/09) funcionam end-to-end.

**Definition of Done:**
- [ ] YouTube Publisher: upload com `selfDeclaredAiGeneratedContent: True` bem-sucedido com vídeo real
- [ ] Instagram Reel e YouTube Short publicados com isolamento de falha validado
- [ ] LinkedIn e Threads publicados via APIs oficiais
- [ ] Blog escrito diretamente no Firestore `articles` via Firebase Admin SDK Python
- [ ] `POST /api/csm/projects/[id]/approve` dispara pipeline end-to-end
- [ ] `POST /api/csm/projects/[id]/publish` (modo imediato) chama `publisher-immediate` corretamente
- [ ] Throttler funciona: dado LinkedIn no limite, pula e registra `throttled`
- [ ] 3 testes Nyquist de U-12 passam + 3 de U-03

**Hipótese de Confiança:** A pipeline completa TTS→Avatar→Video→Publish executa sem intervenção manual de Victor. Todos os canais publicam com isolamento de falha.

**Pré-condições humanas obrigatórias (Victor executa antes do Bolt 3):**
- [ ] YouTube OAuth configurado: token OAuth no Secret Manager, GCP project vinculado ao canal do Victor
- [ ] Confirmar que tokens OAuth Meta (Instagram, Threads, Facebook) e LinkedIn ainda são válidos

---

## Bolt 4: `studio-ui`

**Unidades:**
- **U-04** (`config-api`) — Route Handlers: ConfigService + OAuth YouTube
- **U-05** (`projects-tab-ui`) — React: kanban, cards, side panel, recovery actions
- **U-06** (`pipeline-tab-ui`) — React: PipelineTab, ApiKeyField, ApprovalModal, PublishModal, CostMeter, PipelineProgress

**Por que em Bolt separado:** A UI pode ser construída depois da pipeline estar funcionando, pois Victor pode operar os endpoints diretamente enquanto a UI está sendo construída. Colocar a UI depois da pipeline garante que os componentes são testados contra comportamento real.

**Definition of Done:**
- [ ] Kanban de projetos exibe estado em tempo real (via Firestore listener, SLA ≤ 3s)
- [ ] ApprovalModal bloqueia quando custo > teto (FR-02.2)
- [ ] PublishModal agenda corretamente (fuso America/Sao_Paulo)
- [ ] ProjectDetailPanel mostra `retrying` diferente de `error` (FR-11)
- [ ] PipelineTab salva API keys no Secret Manager via `config-api`
- [ ] Ping de status das APIs externas funciona (ElevenLabs, HeyGen)
- [ ] OAuth YouTube flow funciona (popup → callback → token salvo)
- [ ] Empty states implementados (US-02)
- [ ] 2 testes Nyquist de U-05 + 2 de U-06 + 2 de U-04 passam

**Hipótese de Confiança:** Victor consegue operar a pipeline completa apenas pelo CSM Studio, sem precisar de terminal ou acesso direto ao GCP Console.

---

## Bolt 5: `distribution`

**Escopo:** Conteúdo derivado — carrosseis (PNG via Playwright), YouTube Community Posts, Stories agendados (se viável).

**Unidades:** Extensões de U-11 (Playwright para PNG de carrossel) e U-12 (novos canais: carousel, community post).

**Definition of Done:**
- [ ] Carrosseis (deck `DECKS.carousel` do manifesto) renderizados como PNGs e publicados via Meta Carousel API
- [ ] YouTube Short publicado com tag correta (já incluído no Bolt 3, mas validado aqui como smoke test)
- [ ] YouTube Community Post publicado (se API estiver disponível — verificar OQ-05)
- [ ] Sistema completo validado end-to-end com pacote de conteúdo real: sessão CMO → aprovação → pipeline automático → publicação em 6+ canais → custo ≤ R$100 exibido no painel

**Hipótese de Confiança:** O sistema funciona completamente para uso em produção semanal por Victor, sem nenhuma intervenção técnica além da cocriação CMO.

---

## Sequência de Branches (Way of Working)

Por `team.md § Way of Working`:
- Bolt 0: `bolt/foundations` → squash-merge → `main`
- Bolt 1: `bolt/walking-skeleton` → squash-merge → `main`
- Bolt 2: `bolt/video-editor` → squash-merge → `main`
- Bolt 3: `bolt/publisher-core` → squash-merge → `main`
- Bolt 4: `bolt/studio-ui` → squash-merge → `main`
- Bolt 5: `bolt/distribution` → squash-merge → `main`
