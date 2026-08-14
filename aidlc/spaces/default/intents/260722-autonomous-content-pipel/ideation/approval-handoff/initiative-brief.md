# Initiative Brief
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Compilação de todos os artefatos da fase de Ideação para aprovação e handoff para Inception.
> Referências: [intent-statement.md](../intent-capture/intent-statement.md) | [scope-document.md](../scope-definition/scope-document.md) | [intent-backlog.md](../scope-definition/intent-backlog.md) | [competitive-analysis.md](../market-research/competitive-analysis.md) | [feasibility-assessment.md](../feasibility/feasibility-assessment.md) | [constraint-register.md](../feasibility/constraint-register.md) | [team-assessment.md](../team-formation/team-assessment.md) | [wireframes.md](../rough-mockups/wireframes.md)

---

## 1. Problema e Oportunidade

**Quem:** Victor Zore — criador de conteúdo técnico solo sobre IA/ML. Opera sem equipe de produção.

**Dor central:** O processo atual de produção de conteúdo é uma cadeia de passos manuais que consome 4-8h por vídeo. O resultado: **as redes sociais ficam em silêncio** mesmo quando o conteúdo do YouTube existe — a adaptação manual é inviável para um criador solo.

**Oportunidade:** A infraestrutura base já existe — CSM Studio funciona, `cmo_agent` produz conteúdo de qualidade, `tool-videoyoutube` tem pipeline de edição completa, integrações sociais estão parcialmente ativas. O que falta é a **cola entre essas peças**: microserviços de orquestração que conectam a aprovação de um pacote à publicação final omnicanal, sem intervenção manual.

---

## 2. Visão do Sistema

> *Um Content Production Studio autônomo integrado ao CSM Studio, onde Victor faz uma sessão semanal de cocriação com o CMO Agent, aprova um pacote no kanban, e o sistema executa toda a cadeia automaticamente — TTS, avatar, edição de vídeo e publicação em 6+ canais — dentro de R$100 por pacote.*

**Fluxo resumido:**

```
Victor (30-60 min/semana)
    Sessao CMO --> Aprova pacote no kanban
                        |
                        v
    [Pub/Sub pipeline automatico]
    TTS Job (ElevenLabs) --> Avatar Job (HeyGen Lipsync v3)
    --> Video Editor Job (Playwright+FFmpeg) --> Publisher Service
    --> YouTube + Instagram + LinkedIn + Threads + Blog
                        |
                        v
    Custo exibido no painel (meta: <= R$100)
    Zero intervencoes manuais de Victor
```

---

## 3. Validação de Mercado

**Lacuna confirmada:** nenhuma ferramenta do mercado (Opus Clip, Jasper, Synthesia, Descript) resolve o problema completo — geração de conteúdo técnico com rigor matemático + pipeline de vídeo com avatar + distribuição omnicanal automatizada. A solução é proprietária e não tem substituto direto.

**Custo validado:** estimativa R$67/pacote completo (ElevenLabs + HeyGen + Gemini + GCP infra), dentro do teto de R$100 com 33% de margem. Custo real do HeyGen Lipsync API v3 PAYG a confirmar com spike antes do Bolt 1.

**Conformidade:** YouTube exige AI disclosure desde maio/2026 (label automático). Publisher Service preenche o campo obrigatoriamente. Publicação via Graph API oficial do Meta = zero ban risk.

---

## 4. Viabilidade Técnica

**Veredicto:** ✅ VIÁVEL

| Componente | Status | Risco |
|---|---|---|
| ElevenLabs TTS + clone de voz Victor | API estável, clone a configurar | Médio — qualidade pt-BR a testar |
| HeyGen Lipsync API v3 (áudio externo) | Confirmado via docs: `POST /v3/lipsyncs` | Médio — custo PAYG a confirmar |
| Pipeline de edição (Playwright + FFmpeg) | Código existente a containerizar | Médio — Alpine/Chromium em Cloud Run |
| Pub/Sub + Cloud Run Jobs | GCP nativo, a ativar | Baixo |
| Publisher Service (YouTube + Meta + LinkedIn) | APIs operacionais | Baixo — YouTube OAuth a configurar |

**Migração obrigatória:** HeyGen v2 → v3 (v2 descontinua outubro/2026).

---

## 5. Escopo e Backlog

**5 Bolts sequenciados por dependência + risco:**

| Bolt | Foco | Capacidades Must-Have | Go/No-Go |
|---|---|---|---|
| **B1** Walking Skeleton | ElevenLabs + HeyGen v3 + Pub/Sub + kanban básico | 8 | Custo HeyGen ≤ R$80, qualidade voz ok |
| **B2** Video Editor | Playwright + FFmpeg H+V + jump cuts | 6 | Vídeos gerados em < 30 min |
| **B3** Publisher Service | YouTube + Meta + LinkedIn + agendamento | 10 | Publicação sem ban, com AI disclosure |
| **B4** Painel + Kanban | Config, CostTracker, fallback manual | 7 | Victor opera sem acesso ao código |
| **B5** Distribuição | Carrosseis, Shorts, Community Posts | 4 | Sistema completo validado e2e |

**Total:** 35 capacidades (27 Must Have, 7 Should Have, 1 Could Have).

**Critério de "pronto" do sistema completo:**
```
Victor: sessão CMO (30-60 min) → aprova no kanban
Sistema: executa pipeline completo automaticamente
Resultado: vídeo YouTube + posts em 6 redes no dia seguinte
Custo: <= R$100 exibido no painel
Intervenções manuais de Victor: zero
```

---

## 6. Constraints Não Negociáveis

| ID | Constraint |
|---|---|
| CT-01 | LLMs obrigatoriamente do Google (Gemini via Vertex AI) |
| CT-02 | HeyGen v3 API (v2 descontinua out/2026) |
| CT-05 | Todas as API keys via GCP Secret Manager — nunca em env vars hardcoded |
| CC-01 | AI disclosure obrigatório em 100% dos uploads YouTube |
| CC-02 | Somente Meta Graph API oficial (nunca bots/scrapers) |
| CC-06 | O sistema NUNCA publica sem `approval_status: "approved"` no Firestore |
| CO-01 | Custo máximo R$100/pacote — gate arquitetural via CostTrackerService |
| COP-01 | Fallback manual obrigatório para cada etapa automatizada |

---

## 7. Time e Capacidade

**Modelo:** Victor Zore (Solo Tech Lead + PO) + AIDLC Agent Ensemble.

**Capacidade:** ~5h/semana de review/gates durante a construção.

**Pré-condições humanas antes do Bolt 1** (Victor executa externamente):

| Tarefa | Tempo | Bloqueante |
|---|---|---|
| ElevenLabs: conta + voz clonada | 2-4h | TTS Job |
| HeyGen: spike de custo Lipsync API v3 | 2h | Custo estimado do sistema |
| YouTube OAuth no GCP Console | 1-2h | Publisher Service |
| GCP Pub/Sub API ativada | 15 min | Toda a arquitetura |

**Total pré-construção:** ~6-9h de setup externo.

---

## 8. Conceito Visual

**Duas novas abas no CSM Studio existente:**

- **"Projetos"** — kanban com cards de conteúdo em 7 estados (`creating → awaiting_approval → generating_media → awaiting_publication → publishing → published → error`), custo R$XX/R$100, botões de ação contextuais, recuperação inline de erros.

- **"Pipeline"** — painel de configuração com toggles por canal, API keys via Secret Manager, limites de custo, agenda semanal com fila de próximos agendamentos.

**Dois modais de aprovação distintos:**
- Tela 4: aprovação para **produção** (custo estimado, canais a processar, AI disclosure)
- Tela 4B: aprovação para **publicação** (custo real confirmado, horário, fila)

---

## 9. Recomendação Go/No-Go

**Recomendação: ✅ GO — Iniciar Inception**

**Justificativas:**
1. **Viabilidade técnica confirmada** — todas as integrações têm APIs estáveis e documentadas; o fluxo ElevenLabs → HeyGen Lipsync API v3 foi confirmado via documentação oficial.
2. **Custo dentro do orçamento** — estimativa R$67/pacote com 33% de margem para o teto de R$100.
3. **Riscos com mitigação** — os dois riscos mais críticos (ban YouTube + ban Meta) têm tratamento arquitetural obrigatório.
4. **Código base existente** — ~60% da infraestrutura necessária já existe (`cmo_agent`, `tool-videoyoutube`, CSM Studio, integrações Meta/LinkedIn). A Inception vai refinar e complementar, não construir do zero.
5. **Critério de sucesso claro** — o critério de "pronto" é objetivo, testável e diretamente alinhado com a dor do Victor.

**Condição para Inception:** Victor confirma que executará as pré-condições externas (ElevenLabs + HeyGen spike + YouTube OAuth) antes do Bolt 1 da Construção.

---

## 10. Próximos Passos (Inception)

A fase de Inception aprofunda o design com:

1. **Reverse Engineering (2.1)** — mapeamento completo do código existente para identificar o que reusa, o que adapta e o que cria do zero.
2. **Requirements Analysis (2.3)** — requisitos funcionais e não-funcionais formais por componente.
3. **User Stories (2.4)** — histórias de usuário com critérios de aceitação testáveis.
4. **Refined Mockups (2.5)** — wireframes evoluídos para mockups de média fidelidade com especificações de interação.
5. **Application Design (2.6)** — arquitetura detalhada: schemas Firestore, contratos de mensagens Pub/Sub, APIs, diagrama de componentes.
6. **Units Generation (2.7)** — decomposição em unidades de trabalho independentemente implementáveis.
7. **Delivery Planning (2.8)** — sequência de Bolts com estimativas e critérios de go/no-go por Bolt.
