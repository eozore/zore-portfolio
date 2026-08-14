# Unit of Work Dependency
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Referências: [components.md](../application-design/components.md) | [component-methods.md](../application-design/component-methods.md) | [services.md](../application-design/services.md) | [component-dependency.md](../application-design/component-dependency.md) | [decisions.md](../application-design/decisions.md) | [requirements.md](../requirements-analysis/requirements.md) | [stories.md](../user-stories/stories.md)

---

## DAG de Dependências (texto)

```
U-01 (firestore-schema)
  └── nenhuma dependência

U-02 (pubsub-infra)
  └── nenhuma dependência

U-07 (pipeline-shared-lib)
  └── U-01

U-03 (projects-api)
  ├── U-01
  └── U-02

U-04 (config-api)
  └── U-01

U-13 (cloudbuild-pipeline)
  └── U-07

U-08 (tts-job)
  ├── U-07
  └── U-02

U-10 (heygen-callback)
  ├── U-07
  ├── U-01 (índice collection_group)
  └── U-02

U-09 (avatar-job)
  ├── U-07
  ├── U-02
  └── U-10 (URL do callback deve existir em prod antes do primeiro uso)

U-11 (video-editor-job)
  ├── U-07
  └── U-02

U-12 (publisher-service)
  ├── U-07
  └── U-02
  ← U-03 removido: canal Blog agora via Firestore direto (elimina acoplamento HTTP Python→Next.js)

U-05 (projects-tab-ui)
  ├── U-01
  └── U-03

U-06 (pipeline-tab-ui)
  ├── U-01
  └── U-04
```

---

## Edge Block YAML (Machine-Readable DAG)

```yaml
units:
  - name: firestore-schema
    depends_on: []

  - name: pubsub-infra
    depends_on: []

  - name: pipeline-shared-lib
    depends_on: [firestore-schema]

  - name: projects-api
    depends_on: [firestore-schema, pubsub-infra]

  - name: config-api
    depends_on: [firestore-schema]

  - name: cloudbuild-pipeline
    depends_on: [pipeline-shared-lib]

  - name: tts-job
    depends_on: [pipeline-shared-lib, pubsub-infra]

  - name: heygen-callback
    depends_on: [pipeline-shared-lib, firestore-schema, pubsub-infra]

  - name: avatar-job
    depends_on: [pipeline-shared-lib, pubsub-infra, heygen-callback]

  - name: video-editor-job
    depends_on: [pipeline-shared-lib, pubsub-infra]

  - name: publisher-service
    depends_on: [pipeline-shared-lib, pubsub-infra]

  - name: projects-tab-ui
    depends_on: [firestore-schema, projects-api]

  - name: pipeline-tab-ui
    depends_on: [firestore-schema, config-api]
```

---

## Oportunidades de Paralelismo

**Conjunto 1 — Fundação (sem dependências entre si):**
- `firestore-schema` ⟂ `pubsub-infra`

**Conjunto 2 — Após U-01 estar disponível (paralelo entre si):**
- `pipeline-shared-lib` ⟂ `config-api`

**Conjunto 3 — Após U-07 (shared lib) estar disponível:**
- `tts-job` ⟂ `heygen-callback` ⟂ `video-editor-job`
- Esses três Jobs não dependem um do outro no código — são independentes de desenvolvimento

**Conjunto 4 — Frontend (após U-01 e APIs respectivas):**
- `projects-tab-ui` ⟂ `pipeline-tab-ui` (desenvolvidas em paralelo)

**Conjunto 5 — Sequencial por dependência:**
- `avatar-job` depende de `heygen-callback` (callback_url precisa existir)
- `publisher-service` depende de `projects-api` (endpoint `/api/csm/publish`)
- `cloudbuild-pipeline` pode ser desenvolvido em qualquer momento após `pipeline-shared-lib`

---

## Integração entre Unidades — Contratos

| Integração | Contrato | Formato |
|---|---|---|
| U-03 → Pub/Sub | Mensagem `package_approved` → U-08 (TTSJob) | JSON em `services.md` |
| U-08 → Pub/Sub | Mensagem `tts_completed` → U-09 (AvatarJob) | JSON em `services.md` |
| U-09 → HeyGen | `POST /v3/lipsyncs` com `callback_url` do U-10 | HeyGen API v3 |
| HeyGen → U-10 | Webhook `{ lipsync_id, status, video_url }` | HTTP POST |
| U-10 → Pub/Sub | Mensagem `avatar_completed` → U-11 (VideoEditorJob) | JSON em `services.md` |
| U-11 → Pub/Sub | Mensagem `video_ready` → U-12 (PublisherService) | JSON em `services.md` |
| U-12 → U-03 | ~~`POST /api/csm/publish` para canal Blog~~ — **REMOVIDO.** U-12 escreve diretamente no Firestore `articles` via Firebase Admin SDK Python (decisão pós-review: Opção B para eliminar acoplamento HTTP Python→Next.js) | Firestore Admin SDK |
| U-05/U-06 → Firestore | `onSnapshot` listeners para `content_projects` | Schema em interaction-spec.md seção 5 |
| U-07 → Firestore | `update_actual_cost`, `check_cost_gate` | Schema `cost_breakdown`, `cost_blocked` |

---

## Análise de Blast Radius

| Unidade falha | Impacto | Isolamento |
|---|---|---|
| U-01 (`firestore-schema`) | Bloqueio total — todas as outras dependem dos tipos | Deploy antes de tudo |
| U-07 (`pipeline-shared-lib`) | Bloqueio de todos os Jobs Python | Base do container image |
| U-02 (`pubsub-infra`) | Bloqueio de toda comunicação assíncrona entre jobs | Setup de infra |
| U-10 (`heygen-callback`) | Avatar Job cria jobs HeyGen mas nunca recebe callback → timeout | Altamente crítico |
| U-08 (`tts-job`) | Pipeline para após aprovação | Re-tentar via U-03 |
| U-09 (`avatar-job`) | Pipeline para após TTS | Re-tentar via U-03 |
| U-11 (`video-editor-job`) | Pipeline para após avatar | Re-tentar via U-03 |
| U-12 (`publisher-service`) | Vídeos prontos mas não publicados | Re-tentar via "Publicar Agora" em U-05 |
| U-05/U-06 (UI) | Sem acesso ao kanban — Victor não vê o estado | Operação cega mas pipeline continua |
| U-13 (`cloudbuild-pipeline`) | Sem deploy automatizado | Deploy manual via `gcloud` |

---

## Review

**Revisor:** aidlc-architecture-reviewer-agent
**Data:** 2025-07-27
**Artefatos revisados:** `unit-of-work.md`, `unit-of-work-dependency.md`, `unit-of-work-story-map.md`

### Verdict: ✅ READY — com 2 observações para Delivery Planning

O DAG é consistente, a cobertura de testes é adequada para a maioria das unidades, e os contratos entre unidades estão documentados. Dois pontos exigem decisão explícita antes da implementação de U-12.

---

### Finding 1 — DAG: Acíclico ✅

Verificação topológica completa:

- Raízes (sem dependências): `U-01`, `U-02` — correto.
- Caminho mais longo: `U-01 → U-07 → U-10 → U-09` (4 níveis) e `U-01 → U-03 → U-12` (3 níveis). Ambos terminam em folhas sem retorno.
- **U-09 → U-10** e **U-10 → {U-01, U-07, U-02}**: confirmado acíclico. U-10 não depende de U-09 em nenhum sentido — correto.
- **U-12 → U-03** e **U-03 → {U-01, U-02}**: confirmado acíclico. U-03 não depende de U-12.

Nenhum ciclo detectado em nenhum nível (código, dados, infra). ✅

**Nota sobre U-09 → U-10:** A dependência é de deployment-time (a URL pública do U-10 precisa existir antes do primeiro job HeyGen ser criado em produção), não de código-fonte. Isso está corretamente modelado como dependência no DAG e documentado em `unit-of-work.md`. Recomendo que o `cloudbuild-pipeline.yaml` (U-13) codifique a ordem de deploy: U-10 antes de U-09, explicitamente via steps sequenciais ou tags de deploy.

---

### Finding 2 — Cobertura de Testes Nyquist ✅ (com observação em U-13)

| Unidade | Testes | Avaliação |
|---|---|---|
| U-01 | 1 | OK — schema sem lógica |
| U-02 | 1 | OK — smoke test de infra |
| U-03 | 3 | OK — bem coberto |
| U-04 | 2 | OK |
| U-05 | 2 | OK |
| U-06 | 2 | OK |
| U-07 | 2 | OK — retry + cost gate |
| U-08 | 1 | OK — happy path suficiente para S+M |
| U-09 | 2 | OK |
| U-10 | 2 | OK — primeiro/segundo callback |
| U-11 | 2 | OK |
| U-12 | 3 | Bem coberto |
| U-13 | 1 | Aceitável, ver nota |

**U-13 — 1 teste é aceitável** dado que CI/CD é infra declarativa, não lógica de negócio. No entanto, o único teste atual (`gcloud builds submit` sem erro) cobre apenas o build — não verifica que os serviços estão *saudáveis após o deploy*. 

> **Recomendação para Delivery Planning:** Adicionar um segundo teste Nyquist em U-13 — health check pós-deploy: após `gcloud run deploy`, chamar `GET /health` (ou endpoint equivalente) em `heygen-callback` e `publisher-immediate` e verificar HTTP 200. Isso eleva a confiança do pipeline de CI/CD de "imagem construída" para "serviço respondendo".

---

### Finding 3 — ⚠️ Risco Arquitetural: U-12 (Python Job) chamando U-03 (Next.js Route Handler) para canal Blog

**Descrição do problema:** A tabela de contratos documenta `U-12 → U-03` como `POST /api/csm/publish` para o canal Blog. Isso significa que um Cloud Run Job Python fará uma chamada HTTP síncrona para um Route Handler Next.js.

**Implicações concretas:**

1. **Acoplamento de disponibilidade:** Se o serviço `web` (Cloud Run que hospeda o Next.js) estiver com cold start, reiniciando, ou com deploy em andamento, a publicação do Blog falha — mesmo que todos os outros serviços Python estejam saudáveis. O blast radius do `web` aumenta.

2. **Autenticação serviço-a-serviço não definida:** U-03 usa autenticação de sessão de usuário (NextAuth ou similar). Uma chamada de U-12 (sem contexto de usuário) precisaria de um mecanismo diferente — Service Account token (OIDC), API key interna, ou rota separada sem auth de usuário. Isso não está especificado em nenhum artefato revisado.

3. **Responsabilidade misturada:** O Route Handler `/api/csm/publish` foi projetado como endpoint chamado pelo frontend, não como API interna entre microserviços. Chamá-lo de U-12 inverte o fluxo de dados esperado: backend Python chama Next.js que chama de volta Firestore/CMS.

**Alternativas para Delivery Planning decidir:**

- **Opção A (mínima mudança):** Manter a chamada, mas criar uma rota separada `/api/internal/blog-publish` sem autenticação de usuário, protegida apenas por um token de serviço via `Authorization: Bearer <INTERNAL_TOKEN>` no Secret Manager. Adicionar este token às envs de U-12.
- **Opção B (recomendada):** Mover a lógica de publicação no Blog diretamente para U-12. U-12 já tem acesso ao Firestore e ao GCS — pode escrever o post do blog diretamente (via API do CMS, ou gravando no Firestore na coleção de posts). Elimina o acoplamento HTTP entre serviços e alinha com o padrão dos demais canais.
- **Opção C:** Publicação no Blog via Pub/Sub — U-12 publica mensagem `blog_publish_requested` e um Cloud Run separado (ou o próprio Next.js via subscription) consome. Mais complexidade, mas desacopla completamente.

> **Recomendação:** Opção B elimina uma dependência de runtime entre serviços de tecnologias diferentes sem adicionar complexidade. Só faz sentido manter a chamada ao Next.js se o Blog for um sistema separado (ex: headless CMS) cujo único ponto de entrada seja esse Route Handler — nesse caso, Opção A com autenticação interna explícita.

---

### Finding 4 — ⚠️ `collection_group` em U-10: risco operacional baixo, gap de resiliência identificado

**Custo:** Com o volume projetado (projeto pessoal, dezenas de projetos), o custo de leitura por `collection_group` é negligenciável. Cada callback HeyGen dispara 1 query que retorna no máximo 2 documentos (horizontal + vertical). Sem impacto financeiro prático.

**Latência:** `collection_group` adiciona 50–200 ms vs. lookup direto por document path. Para um webhook handler, isso é aceitável — HeyGen não tem SLA de resposta estrito no callback.

**Risco real — índice ausente:** Se o índice `collection_group('lipsync_jobs')` no Firestore não estiver provisionado, a query falha com erro 400. A constraint em U-01 já documenta isso, mas o risco é silencioso: a query falha, o callback retorna erro, HeyGen pode retentar ou descartar. U-10 não tem lógica de fallback para índice ausente.

**Alternativa mais eficiente (para referência futura):** Ao criar `lipsync_job` em U-09, gravar `lipsync_id → project_id` em uma coleção raiz `/lipsync_index/{lipsync_id}`. U-10 faria `getDoc('/lipsync_index/' + lipsync_id)` — O(1) lookup sem índice composto. Reduz latência e elimina a dependência de índice. Custo de implementação: +2h em U-09 e U-10.

> **Recomendação para Delivery Planning:** A solução atual com `collection_group` funciona. Para mitigação do risco de índice ausente, adicionar verificação de health no smoke test de U-01: executar uma query `collection_group('lipsync_jobs').limit(1)` após aplicar os índices e verificar que não retorna erro 400. A alternativa do `/lipsync_index` é uma melhoria de resiliência válida para considerar como tech debt no Bolt 2.

---

### Resumo para Delivery Planning

| # | Item | Severidade | Ação Necessária |
|---|---|---|---|
| 1 | DAG acíclico, contratos documentados | ✅ Info | Nenhuma |
| 2 | U-09 → U-10: dependência de deployment, não de código | ✅ Info | Codificar ordem de deploy no U-13 (cloudbuild steps sequenciais) |
| 3 | U-13: 1 teste cobre apenas build, não health pós-deploy | ⚠️ Baixo | Adicionar health check como segundo teste Nyquist em U-13 |
| 4 | U-12 → U-03: acoplamento HTTP Python → Next.js sem auth serviço-a-serviço definida | 🔴 Médio | Decidir Opção A ou B antes de iniciar sprint de U-12 |
| 5 | U-10 `collection_group`: risco de índice ausente sem fallback | ⚠️ Baixo | Adicionar ao smoke test de U-01; avaliar `/lipsync_index` como tech debt |

**Bloqueante para início de U-12:** Finding 4 (autenticação de serviço interno). As demais unidades podem ser iniciadas sem bloqueio.
