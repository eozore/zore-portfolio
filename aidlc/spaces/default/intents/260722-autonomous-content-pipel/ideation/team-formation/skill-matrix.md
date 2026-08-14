# Skill Matrix
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Referências: [scope-document.md](../scope-definition/scope-document.md) | [feasibility-assessment.md](../feasibility/feasibility-assessment.md)

---

## Legenda

| Código | Significado |
|---|---|
| ✅ | Disponível e pronto — sem lacuna |
| ⚠️ | Disponível mas novo no contexto — spike necessário |
| 🔧 | Parcialmente disponível — código existente precisa de adaptação |
| ❌ | Lacuna real — mitigação necessária |

---

## Matrix por Bolt

### Bolt 1 — Walking Skeleton

| Capacidade | Skill Necessária | Disponível | Status |
|---|---|---|---|
| GCP Pub/Sub setup | Python `google-cloud-pubsub` SDK | Victor | ⚠️ Novo mas simples |
| Firestore schema `content_projects` | Firebase Admin SDK (Python + TS) | Victor | ✅ |
| ElevenLabs TTS API | REST API Python, voz clonada pt-BR | Victor | ⚠️ Novo — spike obrigatório |
| HeyGen Assets API upload | REST API Python, multipart upload | Victor | ⚠️ Novo — spike obrigatório |
| HeyGen Lipsync API v3 | REST API Python, polling/callback | Victor | ⚠️ Novo — spike obrigatório |
| Cloud Run Jobs (Python) | Dockerfile, Cloud Run Jobs config | Victor | 🔧 Tem Cloud Run Services, Jobs é novo |
| Kanban básico (Next.js) | React, Firestore realtime, CSS Modules | Victor | ✅ |
| Gate de aprovação Firestore | Firestore write + TypeScript types | Victor | ✅ |

### Bolt 2 — Video Editor

| Capacidade | Skill Necessária | Disponível | Status |
|---|---|---|---|
| Playwright renderização slides | Playwright Python, Chromium headless | Victor | 🔧 Tem em `tool-videoyoutube`, precisa containerizar |
| FFmpeg composição H+V | FFmpeg CLI, filter_complex | Victor | 🔧 Tem em `editor_pipeline.py`, adaptar pipeline |
| Composição determinística manifesto | Python, leitura JSON manifesto | Victor | ✅ |
| Jump cuts automáticos | FFmpeg silence detection, Python | Victor | 🔧 Já existe em `editor_pipeline.py` |
| Cloud Run Job containerização | Docker multi-stage, Playwright Alpine | Victor | ⚠️ Playwright + Alpine precisa de teste |

### Bolt 3 — Publisher Service

| Capacidade | Skill Necessária | Disponível | Status |
|---|---|---|---|
| YouTube Data API v3 upload | OAuth 2.0 Google, `google-api-python-client` | Victor | ⚠️ OAuth user flow novo (service account não serve) |
| YouTube AI disclosure field | YouTube API `videoStatus` payload | Victor | ⚠️ Campo novo (maio/2026) — verificar spec |
| Meta Graph API (Instagram/Threads/FB) | Graph API REST, tokens OAuth | Victor | ✅ Já operacional |
| LinkedIn API v2 posts | LinkedIn API REST, OAuth tokens | Victor | ✅ Já operacional |
| Cloud Scheduler setup | GCP Cloud Scheduler, cron config | Victor | ⚠️ Novo mas simples |
| Rate limiter por canal | Python async, throttling patterns | Victor | ✅ |

### Bolt 4 — Painel de Configuração

| Capacidade | Skill Necessária | Disponível | Status |
|---|---|---|---|
| Config UI no CSM Studio | Next.js, React forms, CSS Modules | Victor | ✅ |
| Secret Manager read/write | GCP Secret Manager API, Python + TS | Victor | ✅ Já usa em `heygen/route.ts` |
| CostTrackerService | Python, Firestore writes, cálculo de custo API | Victor | ✅ |
| Kanban completo com histórico | React, Firestore queries, TypeScript | Victor | ✅ |
| Error log inline no kanban | Firestore error documents, React | Victor | ✅ |

### Bolt 5 — Distribuição Completa

| Capacidade | Skill Necessária | Disponível | Status |
|---|---|---|---|
| Carrossel publisher (imagens sequenciais) | Meta Graph API carousel endpoint | Victor | ⚠️ Endpoint específico para carrossel — verificar spec |
| YouTube Shorts tag | YouTube API `tags` e `categoryId` | Victor | ✅ Mesmo upload do Bolt 3 com parâmetros diferentes |
| YouTube Community Posts | YouTube API `communityPosts` endpoint | Victor | ⚠️ Endpoint menos documentado — verificar disponibilidade |
| Stories agendamento | Meta Graph API scheduled posts | Victor | ⚠️ TTL de 24h torna timing crítico |

---

## Resumo de Gaps por Severidade

**Gaps ⚠️ (spike necessário antes de implementar):**
1. ElevenLabs API — clone de voz pt-BR (Bolt 1, pré-condição crítica)
2. HeyGen Lipsync API v3 — fluxo completo com áudio externo (Bolt 1, risco alto)
3. YouTube OAuth user flow — upload em nome do canal pessoal (Bolt 3)
4. YouTube AI disclosure field — verificar spec atual do campo (Bolt 3)
5. Playwright em Alpine Linux — Dockerfile para Cloud Run Jobs (Bolt 2)

**Gaps 🔧 (adaptação de código existente):**
1. `editor_pipeline.py` → Cloud Run Job containerizado (Bolt 2)
2. `tool-videoyoutube` pipeline → Cloud Run Job com Pub/Sub input (Bolt 2)
3. `heygen/route.ts` v2 → v3 migration (Bolt 1)

**Sem gaps críticos.** Nenhuma lacuna requer contratação externa ou aprendizado de meses. Todos os spikes são resolúveis em 1-3 dias de trabalho técnico.

---

## Plano de Remediação de Gaps (pré-Bolt 1)

Antes de iniciar o Bolt 1, Victor deve completar estes setups externos que são pré-condições:

| Tarefa | Estimativa | Bloqueante para |
|---|---|---|
| Criar conta ElevenLabs, gravar amostras de voz (>2 min áudio limpo), configurar Instant Clone | 2-4h | B1-08, TTS Job |
| Confirmar avatar HeyGen (Avatar IV) ativo e API key válida | 30 min | B1-04, Avatar Job |
| Testar HeyGen Lipsync API v3 com vídeo de 1 min + áudio ElevenLabs (confirmar custo real — Issue I01) | 2h | Todos os custos do Bolt 1 |
| Configurar YouTube Data API v3 no GCP Console, fazer OAuth com canal do Victor | 1-2h | B3-02 |
| Ativar GCP Pub/Sub API no projeto `eozore-platform` | 15 min | B1-01 |
