# Interaction Specification
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Referências: [wireframes.md](../../ideation/rough-mockups/wireframes.md) | [user-flow.md](../../ideation/rough-mockups/user-flow.md) | [stories.md](../user-stories/stories.md) | [requirements.md](../requirements-analysis/requirements.md) | [team-practices.md](../practices-discovery/team-practices.md)

---

## 1. Padrões de Interação Globais

### 1.1 Atualização em Tempo Real (Firestore Listeners)

Todos os componentes que exibem estado de projeto usam listeners Firestore. Padrão de implementação:

```typescript
// Hook padrão para escutar um projeto
useEffect(() => {
  const unsubscribe = db
    .collection('content_projects')
    .doc(projectId)
    .onSnapshot((doc) => {
      if (doc.exists) setProject({ id: doc.id, ...doc.data() });
    });
  return () => unsubscribe(); // cleanup obrigatório
}, [projectId]);
```

**SLA visual:** mudança de estado deve ser visível em ≤ 3s após o Firestore ser atualizado (US-06).

### 1.2 Toast Notifications

Disparadas por eventos críticos de pipeline:

| Evento | Tipo | Texto | Duração |
|---|---|---|---|
| Job concluído | success | "✓ [Etapa] concluída — R$X.XX" | 5s |
| Job com erro | error | "✕ [Etapa] falhou: [mensagem curta]" | 8s (dismiss manual) |
| Custo em 80% | warning | "⚠ Custo em 80% do teto — R$80/R$100" | 8s |
| Publicação concluída | success | "✓ Publicado em N canais" | 5s |

```typescript
// Padrão de uso (integrar com sistema de toast existente ou criar)
toast.success('TTS concluído — R$4.13', { duration: 5000 });
toast.error('Video Editor falhou: Playwright timeout', { duration: 8000 });
```

### 1.3 Skeleton Loaders

Cards na aba "Projetos" exibem skeleton enquanto o Firestore listener não retornou o primeiro resultado:

```
+------------------+
| [░░░░░░░░░░░░░]  |  ← shimmer animation
| [░░░░░░░░]       |
| [░] [░░░░]       |
| [░] [░░░]        |
| [░░░░░░░░░░░░░]  |
| [░░░░░░]         |
+------------------+
```

```css
.skeleton {
  background: linear-gradient(90deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.1) 50%, rgba(255,255,255,0.05) 100%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
@keyframes shimmer { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }
```

---

## 2. Fluxos de Interação por User Story

### US-04: Fluxo de Aprovação para Produção

```
1. Victor clica "Aprovar" no card
   → ProjectCard emite onClick → CsmDashboard abre ApprovalModal
   → ApprovalModal faz GET /api/csm/projects/{id}/cost-estimate
   → Exibe custo estimado por etapa

2. Se custo ≤ limite: botão "Aprovar e Iniciar Pipeline" habilitado
   Se custo > limite: botão desabilitado, alerta visível

3. Victor clica "Aprovar e Iniciar Pipeline"
   → POST /api/csm/projects/{id}/approve
   → Body: { channels_approved: string[], ai_disclosure: true }
   → Backend escreve approval_data no Firestore, dispara Pub/Sub
   → Modal fecha, card atualiza para "Gerando Mídia" (via listener)

4. Se Victor cancela: modal fecha, sem efeito no Firestore
```

**Tratamento de erro:**
```
GET /cost-estimate falha:
  → Exibe "Erro ao calcular custo estimado. [Tentar novamente]"
  → Botão de aprovação permanece desabilitado

POST /approve falha:
  → Toast error "Falha ao iniciar pipeline. Tente novamente."
  → Modal permanece aberto para retry
```

---

### US-05: Fluxo de Aprovação de Publicação

```
1. Victor clica "Publicar" (card ou side panel)
   → Abre PublishModal
   → Modal faz GET /api/csm/projects/{id}/publish-preview
   → Exibe custos reais, links de preview, canais

2. Victor escolhe "Publicar agora" ou seleciona data/hora

3. Victor confirma canais (pode desmarcar individualmente)

4. Clica "Publicar / Agendar"
   → POST /api/csm/projects/{id}/publish
   → Body: { mode: 'now' | 'scheduled', scheduled_at?: string, channels: string[] }
   → Se 'now': Publisher Service disparado imediatamente
   → Se 'scheduled': salva scheduled_publish_at no Firestore
   → Cloud Scheduler seleciona na data/hora configurada
```

---

### US-07: Fluxos de Recuperação Manual

**Re-tentar etapa:**
```
1. Victor clica "Re-tentar etapa" no side panel
   → POST /api/csm/projects/{id}/retry-stage
   → Body: { stage: 'tts' | 'avatar' | 'editor' }
   → Backend publica mensagem Pub/Sub para o job específico
   → Stage volta para status 'running'
   → Side panel atualiza via Firestore listener
```

**Upload manual:**
```
1. Victor clica "Upload manual .mp4"
   → input[type="file"] accept=".mp4" abre file picker nativo
   → Ao selecionar: exibe nome do arquivo e tamanho
   → Victor clica "Confirmar upload"
   → POST /api/csm/projects/{id}/stages/{stage}/manual-upload
     (multipart/form-data com o arquivo)
   → Backend salva em GCS: gs://{bucket}/projects/{id}/{stage}_manual.mp4
   → Backend atualiza Firestore: stage.status = 'completed', stage.source = 'manual'
   → Pipeline retoma da próxima etapa via Pub/Sub
```

**Pular etapa:**
```
1. Victor clica "Pular esta etapa"
   → Diálogo de confirmação inline (não modal): 
     "Pular [Video Editor]? O vídeo não terá slides sincronizados."
     [Cancelar] [Pular mesmo assim]
   → POST /api/csm/projects/{id}/skip-stage
   → Backend: stage.status = 'skipped', publica Pub/Sub para próxima etapa
```

---

### US-11: Fluxo de Configuração de API Key

```
1. Victor clica "Editar" no ApiKeyField
   → Campo muda de tipo="text" (masked) para tipo="password"
   → Input vazio (NUNCA pré-preenchido com valor real)
   → Victor digita a nova key

2. Clica "Salvar"
   → POST /api/csm/pipeline/config/keys
   → Body: { provider: 'elevenlabs' | 'heygen', key: string }
   → Backend chama GCP Secret Manager API para criar/atualizar secret
   → Retorna { saved: true } — NUNCA retorna o valor da key
   → Frontend exibe "✓ Salvo com segurança"

3. Clica "Testar ping"
   → GET /api/csm/pipeline/config/ping?provider=elevenlabs
   → Backend faz chamada autenticada real ao provider
   → Retorna { ok: boolean, latencyMs: number, error?: string }
   → ApiKeyField exibe status atualizado
```

---

## 3. Estados de Todos os Componentes

### ProjectCard — Todos os Estados

| Estado | Loading | Empty | Error | Success | Partial |
|---|---|---|---|---|---|
| Carregando do Firestore | Skeleton loader | — | "Erro ao carregar" | Card normal | — |
| Gerando mídia | Badge "Gerando..." + spinner | — | Badge erro + mensagem | — | Checklist parcial |
| Publicando | Badge "Publicando" + spinner | — | Badge erro por canal | Badge "Publicado" | Alguns canais publicados |

### ApprovalModal — Estados de Loading

| Ação | Loading State | Sucesso | Erro |
|---|---|---|---|
| Carregar custo estimado | Spinner no bloco de custo, botão desabilitado | Valores exibidos | "Erro ao calcular. [Tentar novamente]" |
| Submeter aprovação | Botão em loading, spinner inline | Modal fecha + toast success | Toast error, modal fica aberto |

### ApiKeyField — Estados

| Estado | Visual |
|---|---|
| View mode | Key mascarada, botões "Editar" e "Testar ping" |
| Edit mode | Input vazio tipo password, botões "Cancelar" e "Salvar" |
| Saving | Spinner no botão "Salvar", campo desabilitado |
| Ping loading | Spinner no botão "Testar ping" |
| Ping success | "● ATIVO (189ms)" em verde |
| Ping error | "✕ INATIVO — Erro 401" em vermelho + link de ajuda |

---

## 5. Shape do Documento Firestore — `content_projects`

Documenta os campos que o frontend escuta via Firestore listener (F5 da revisão).

### Schema: `project.stages[]`

```typescript
// Firestore: content_projects/{projectId}
interface ContentProject {
  id: string;
  title: string;
  status: ProjectStatus;
  manifest_url: string;
  created_at: Timestamp;
  approved_by?: string;
  approved_at?: Timestamp;
  estimated_cost?: CostBreakdown;
  scheduled_publish_at?: Timestamp;
  channels_approved?: string[];

  // Atualizado pelo CostTrackerService após cada job
  cost_breakdown: {
    tts?: number;         // custo real ElevenLabs (R$)
    heygen?: number;      // custo real HeyGen (R$)
    gemini?: number;      // custo real Gemini (R$)
    gcp?: number;         // custo real infra (R$)
    total_real: number;   // soma dos reais
    total_estimated: number; // estimativa dos pendentes
  };

  // Array de etapas — atualizado por cada Cloud Run Job via Firestore
  stages: Array<{
    id: 'tts' | 'avatar' | 'editor' | 'publisher';
    label: string;
    status: 'pending' | 'running' | 'retrying' | 'completed' | 'error' | 'skipped';
    retry_count: number;         // 0-3; atualizado a cada tentativa automática
    max_retries: number;         // sempre 3
    error_message?: string;
    error_type?: 'transient' | 'permanent';
    cost_real?: number;          // definido quando status = 'completed'
    cost_estimated?: number;     // estimativa inicial
    source?: 'pipeline' | 'manual'; // 'manual' quando upload manual foi usado
    started_at?: Timestamp;
    completed_at?: Timestamp;
  }>;

  // Resultados de publicação — preenchidos pelo Publisher Service
  publications?: {
    youtube?: { status: 'published' | 'failed' | 'skipped'; url?: string; error?: string };
    youtube_short?: { status: 'published' | 'failed' | 'skipped'; url?: string; error?: string };
    instagram_reel?: { status: 'published' | 'failed' | 'skipped'; url?: string; error?: string };
    linkedin?: { status: 'published' | 'failed' | 'throttled' | 'skipped'; url?: string };
    threads?: { status: 'published' | 'failed' | 'skipped'; url?: string; error?: string };
    blog?: { status: 'published' | 'failed' | 'skipped_duplicate' | 'skipped'; url?: string; error?: string };
  };

  // Bloqueio por custo (FR-10.2)
  cost_blocked?: {
    blocked: true;
    blocked_stage: string;      // qual job foi bloqueado
    current_cost: number;       // custo acumulado no momento do bloqueio
    estimated_next: number;     // estimativa da próxima etapa
    limit: number;              // teto configurado
    blocked_at: Timestamp;
  };
}
```

**Como o frontend detecta bloqueio por custo (FR-10.2):**
```typescript
// No ProjectCard e ProjectDetailPanel: verificar cost_blocked
if (project.cost_blocked?.blocked) {
  // Renderizar estado de erro especial:
  // "Custo estimado ultrapassaria R$[limit]. Ajuste o teto ou desabilite canais."
  // CTA: [Ajustar teto de custo →] → navega para PipelineTab seção custo
}
```

Todos os novos endpoints ficam em `apps/web/src/app/api/csm/`:

| Método | Endpoint | Body | Resposta | User Story |
|---|---|---|---|---|
| GET | `/projects` | — | `Project[]` | US-02 |
| POST | `/projects` | `{ manifest_url }` | `{ id }` | US-01 |
| GET | `/projects/[id]` | — | `Project` | US-03 |
| GET | `/projects/[id]/cost-estimate` | — | `{ breakdown, total }` | US-04 |
| POST | `/projects/[id]/approve` | `{ channels_approved[], ai_disclosure }` | `{ ok }` | US-04 |
| POST | `/projects/[id]/publish` | `{ mode, scheduled_at?, channels[] }` | `{ ok }` | US-05 |
| POST | `/projects/[id]/retry-stage` | `{ stage }` | `{ ok }` | US-07 |
| POST | `/projects/[id]/skip-stage` | `{ stage }` | `{ ok }` | US-07 |
| POST | `/projects/[id]/stages/[stage]/manual-upload` | `multipart/form-data` | `{ ok, gcs_url }` | US-07 |
| GET | `/pipeline/config` | — | `PipelineConfig` | US-11 |
| POST | `/pipeline/config/keys` | `{ provider, key }` | `{ saved }` | US-11 |
| GET | `/pipeline/config/ping` | `?provider=` | `{ ok, latencyMs, error? }` | US-11 |
| POST | `/pipeline/config` | `PipelineConfig` | `{ ok }` | US-11/12/13 |
| GET | `/projects/[id]/publish-preview` | — | `PublishPreview` | US-05 |

---

## 6. Estados de Loading/Error/Success — `PipelineTab`

**Mapeia:** US-11, US-12, US-13, F7 da revisão

| Ação | Loading State | Sucesso | Erro |
|---|---|---|---|
| Salvar agenda semanal | Botão "Salvar configurações" em loading (spinner inline), campos desabilitados | `✓ Configuração salva` (texto inline por 3s) | Toast error "Erro ao salvar configuração. [Tentar novamente]" |
| Salvar teto de custo | Indicador inline no campo, sem desabilitar os outros campos | Texto "✓ Salvo" por 2s no campo | Mensagem inline "Erro ao salvar" em vermelho |
| Toggle de canal | Spinner no toggle por 500ms | Toggle atualizado (estado persistido) | Toggle reverte ao estado anterior + toast "Erro ao salvar configuração do canal" |
| Salvar config de canal (expandida) | Botão "Salvar" do sub-painel em loading | Texto "✓ Salvo" por 2s | Mensagem inline de erro |

---

## 7. Toasts — Tabela Completa

**Atualização da seção 1.2 com entradas adicionais (F8 da revisão):**

| Evento | Tipo | Texto | Duração |
|---|---|---|---|
| Job concluído | success | "✓ [Etapa] concluída — R$X.XX" | 5s |
| Job com erro | error | "✕ [Etapa] falhou: [mensagem curta]" | 8s (dismiss manual) |
| Custo em 80% | warning | "⚠ Custo em 80% do teto — R$80/R$100" | 8s |
| Publicação concluída | success | "✓ Publicado em N canais" | 5s |
| **Publicação agendada iniciada** | info | "⏰ Publicando '[título]' — agendado para [horário]" | 5s |
| Configuração salva | success | "✓ Configuração salva" | 3s |
| Token OAuth expirando em ≤ 3 dias | warning | "⚠ Token YouTube expira em N dias. [Renovar →]" | 10s (dismiss) |
| Token OAuth já expirado | error | "✕ Token YouTube expirado. Publicações do YouTube estão pausadas. [Reautorizar →]" | Persistente |
