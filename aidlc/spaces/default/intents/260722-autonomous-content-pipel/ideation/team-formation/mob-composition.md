# Mob Composition Plan
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Referências: [scope-document.md](../scope-definition/scope-document.md) | [intent-backlog.md](../scope-definition/intent-backlog.md)

---

## Modelo: Solo Tech Lead + AI Agent Ensemble

Em vez de mobs de pessoas, o projeto opera com **mobs de agentes AIDLC** onde cada Bolt tem um conjunto definido de agentes responsáveis pela execução e Victor como único revisor humano.

---

## Mob por Bolt

### BOLT 1 — Walking Skeleton

**Objetivo:** Provar o fluxo end-to-end. Resolver os dois maiores riscos (ElevenLabs clone + HeyGen v3 Lipsync) antes de construir o restante.

```
+------------------------------------------+
| Victor Zore (Tech Lead + PO)             |
|   - Aprova gates                         |
|   - Faz spikes externos (ElevenLabs,     |
|     HeyGen, YouTube OAuth, Pub/Sub)      |
|   - Revisa código gerado                 |
+------------------------------------------+
|   Lead: Developer Agent                  |
|     - Infra Pub/Sub (B1-01)              |
|     - Schema Firestore (B1-02)           |
|     - TTS Job Python (B1-03)             |
|     - Avatar Job Python (B1-04)          |
|     - Migração HeyGen v2→v3 (B1-07)     |
+------------------------------------------+
|   Support: Architect Agent               |
|     - Valida design de mensagens Pub/Sub |
|     - Revisa contratos de interface      |
|     - Define estrutura do Cloud Run Job  |
+------------------------------------------+
|   Support: Quality Agent                 |
|     - Testes unitários TTS Job           |
|     - Testes de integração Avatar Job    |
|     - Validação do fluxo e2e em staging  |
+------------------------------------------+
|   Support: DevSecOps Agent               |
|     - Configura Secret Manager paths     |
|     - Valida IAM roles dos Cloud Run Jobs|
+------------------------------------------+
```

**Pré-condições humanas (Victor):**
- [ ] ElevenLabs: conta criada, voz clonada configurada, `voice_id` obtido
- [ ] HeyGen: conta ativa, Avatar IV confirmado, API key válida
- [ ] HeyGen: spike de custo (vídeo 1 min via Lipsync API v3) executado
- [ ] GCP Pub/Sub API ativada no projeto

**Definition of Done — Bolt 1:**
- [ ] TTS Job processa todos os segmentos de um manifesto de teste e gera áudios no GCS
- [ ] Avatar Job recebe os áudios, chama HeyGen Lipsync v3, recebe vídeo de volta e salva no GCS
- [ ] Kanban básico exibe o projeto com estado `generating_media`
- [ ] Gate de aprovação persiste `approval_data` no Firestore
- [ ] Custo real por vídeo confirmado e dentro do teto R$100

---

### BOLT 2 — Video Editor

**Objetivo:** Transformar avatar + slides HTML em vídeos horizontal e vertical prontos.

```
+------------------------------------------+
| Victor Zore                              |
|   - Revisa vídeos gerados (qualidade)    |
|   - Aprova gate                          |
+------------------------------------------+
|   Lead: Developer Agent                  |
|     - Video Editor Job (Cloud Run Job)   |
|     - Containerização Playwright Alpine  |
|     - Composição FFmpeg H+V (B2-03/04)   |
|     - Jump cuts (B2-05)                  |
|     - Pub/Sub integration (B2-06)        |
+------------------------------------------+
|   Support: Architect Agent               |
|     - Valida Dockerfile e image size     |
|     - Revisa performance FFmpeg          |
+------------------------------------------+
|   Support: Quality Agent                 |
|     - Testa renderização de slides       |
|     - Valida sincronização avatar+slides |
|     - Verifica jump cuts não quebram fala|
+------------------------------------------+
```

**Definition of Done — Bolt 2:**
- [ ] Vídeo horizontal (1920×1080) gerado com avatar + slides sincronizados
- [ ] Vídeo vertical (1080×1920) gerado com avatar + slides sincronizados
- [ ] Jump cuts aplicados (silêncios removidos)
- [ ] Ambos os vídeos disponíveis no GCS e referenciados no Firestore do projeto
- [ ] Cloud Run Job executa em < 30 min para vídeo de 15 min

---

### BOLT 3 — Publisher Service

**Objetivo:** Publicar automaticamente nos 6 canais habilitados com conformidade.

```
+------------------------------------------+
| Victor Zore                              |
|   - Configura OAuth YouTube (uma vez)    |
|   - Revisa primeira publicação de cada   |
|     canal antes de ativar automação      |
|   - Aprova gate                          |
+------------------------------------------+
|   Lead: Developer Agent                  |
|     - Publisher Service base (B3-01)     |
|     - YouTube Publisher + AI disclosure  |
|     - Meta/LinkedIn Publishers           |
|     - Blog Publisher (B3-07)             |
|     - Gate de aprovação publicação       |
|     - Cloud Scheduler setup (B3-09)      |
|     - Throttler por canal (B3-10)        |
+------------------------------------------+
|   Support: Compliance Agent              |
|     - Valida AI disclosure no payload YT |
|     - Verifica conformidade com ToS Meta |
|     - Confirma rate limits implementados |
+------------------------------------------+
|   Support: Quality Agent                 |
|     - Testa publicação end-to-end        |
|     - Verifica comportamento de retry    |
|     - Testa throttler (não publica 2x)   |
+------------------------------------------+
```

**Definition of Done — Bolt 3:**
- [ ] Artigo publicado no blog via publisher (usa rota existente)
- [ ] Vídeo horizontal publicado no YouTube com AI disclosure
- [ ] Vídeo vertical publicado como Instagram Reel
- [ ] Post publicado no Threads e LinkedIn
- [ ] Cloud Scheduler distribui publicações conforme agenda configurada
- [ ] Nenhuma publicação duplicada em 24h por canal

---

### BOLT 4 — Painel de Configuração + Kanban Completo

**Objetivo:** Dar controle total a Victor sem acesso ao código ou ao Cloud Console.

```
+------------------------------------------+
| Victor Zore                              |
|   - Testa o painel end-to-end            |
|   - Configura canais reais no painel     |
|   - Aprova gate                          |
+------------------------------------------+
|   Lead: Developer Agent                  |
|     - Config Service UI (B4-01)          |
|     - Secret Manager integration (B4-02) |
|     - Kanban completo (B4-03)            |
|     - CostTrackerService (B4-04)         |
|     - Fallback manual por etapa (B4-05)  |
|     - Error log inline (B4-06)           |
|     - Alert token OAuth (B4-07)          |
+------------------------------------------+
|   Support: Design Agent                  |
|     - UI/UX do painel de configuração    |
|     - Kanban visual com estados claros   |
|     - Mobile-friendly para revisar rápido|
+------------------------------------------+
|   Support: Quality Agent                 |
|     - Testa todas as ações manuais       |
|     - Valida Secret Manager round-trip   |
|     - Testa alerta de token expirando    |
+------------------------------------------+
```

**Definition of Done — Bolt 4:**
- [ ] Victor consegue ligar/desligar cada canal individualmente no painel
- [ ] Keys/tokens configurados via UI persistem no Secret Manager (não em Firestore)
- [ ] Kanban mostra estado de cada projeto com custo acumulado
- [ ] Botões de fallback manual funcionam para cada etapa
- [ ] Erros de jobs aparecem inline no card do projeto

---

### BOLT 5 — Distribuição Social Completa

**Objetivo:** Pipeline 100% completa com todos os formatos derivados.

```
+------------------------------------------+
| Victor Zore                              |
|   - Revisa qualidade dos carrosseis      |
|   - Aprova gate final                    |
+------------------------------------------+
|   Lead: Developer Agent                  |
|     - Carrossel Publisher (B5-01)        |
|     - Image Post Publisher (B5-02)       |
|     - YouTube Community Posts (B5-03)    |
|     - YouTube Shorts tag (B5-05)         |
+------------------------------------------+
|   Support: Quality Agent                 |
|     - Testa todos os formatos visuais    |
|     - Valida sequência de stories        |
|     - Smoke test completo do sistema     |
+------------------------------------------+
```

**Definition of Done — Bolt 5 (Sistema Completo):**
- [ ] Carrosseis publicados no Instagram e LinkedIn
- [ ] YouTube Shorts publicados com tag correta
- [ ] Community Posts publicados no YouTube
- [ ] **Sistema completo validado end-to-end** com pacote de conteúdo real:
  - Sessão CMO → aprovação → pipeline automático executa → vídeo YouTube + todos os posts nas redes publicados → custo ≤ R$100 → zero intervenções manuais de Victor

---

## RACI Simplificado (Solo)

| Atividade | Victor | AIDLC Agents |
|---|---|---|
| Decisões de produto e prioridade | **R + A** | C |
| Geração de código | C | **R** |
| Revisão de código e artefatos | **R + A** | C |
| Aprovação de gates | **R + A** | — |
| Configuração de contas externas (ElevenLabs, HeyGen, OAuth) | **R + A** | C |
| Testes automatizados | C | **R** |
| Documentação técnica | C | **R** |
| Operação do sistema após construção | **R + A** | C |

**R** = Responsible, **A** = Accountable, **C** = Consulted

---

## Sequência de Bolts e Critérios de Go/No-Go

```
PRE-CONDITIONS (antes do Bolt 1)
    Victor: ElevenLabs clone OK + HeyGen spike custo OK
         |
         v
    BOLT 1 — Walking Skeleton
    Go: fluxo e2e funciona, custo dentro do teto
    No-Go: custo HeyGen > R$80 ou qualidade ElevenLabs inadequada
         |  → se No-Go: revisar arquitetura de custo / trocar fornecedor TTS
         v
    BOLT 2 — Video Editor
    Go: vídeos H+V gerados com qualidade aceitável em < 30 min
    No-Go: Playwright em Alpine não funciona em Cloud Run
         |  → se No-Go: usar `html2youtube` standalone ao invés de containerizar
         v
    BOLT 3 — Publisher Service
    Go: publicação funcional em todos os canais sem ban, com AI disclosure
    No-Go: YouTube rejeita upload ou Meta bloqueia conta
         |  → se No-Go: publicação manual via painel como fallback
         v
    BOLT 4 — Painel + Kanban
    Go: Victor consegue operar o sistema completo sem acesso ao código
    No-Go: (improvável — sem dependências externas de alto risco)
         v
    BOLT 5 — Distribuição Completa
    Go: todos os formatos derivados publicados com sucesso
    → Sistema operacional
```
