# Decision Log — Fase de Ideação
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Registro cronológico de todas as decisões tomadas durante a fase de Ideação.
> Referências: [intent-statement.md](../intent-capture/intent-statement.md) | [scope-document.md](../scope-definition/scope-document.md) | [intent-backlog.md](../scope-definition/intent-backlog.md) | [competitive-analysis.md](../market-research/competitive-analysis.md) | [feasibility-assessment.md](../feasibility/feasibility-assessment.md) | [constraint-register.md](../feasibility/constraint-register.md) | [team-assessment.md](../team-formation/team-assessment.md) | [wireframes.md](../rough-mockups/wireframes.md)

---

## Decisões de Produto e Estratégia

| ID | Decisão | Razão | Estágio | Alternativa Rejeitada |
|---|---|---|---|---|
| D-001 | **Gargalo principal = ausência de derivação automática para redes sociais** | Victor confirmou explicitamente: redes ficam sem conteúdo por falta de tempo para adaptação manual | intent-capture | Gravação manual de voz como gargalo principal |
| D-002 | **Ponto de entrada = CSM Studio no browser** | Interface já existe; não faz sentido criar nova UI | intent-capture | CLI, Telegram bot |
| D-003 | **Qualidade/naturalidade > economia de custo** | Princípio orientador estabelecido pelo Victor; teto de R$100 é limite, não alvo | intent-capture | Priorizar custo mínimo |
| D-004 | **Aprovação obrigatória antes de qualquer publicação** | Conformidade com políticas de plataformas, manutenção de padrão técnico | intent-capture | Autonomia total com rollback |
| D-005 | **Batch semanal** (sessão CMO → 5-7 pacotes → 1/dia) | Melhor uso do tempo de Victor; evita custo de infra idle | intent-capture | Event-driven por pacote |
| D-006 | **Todos os canais com painel liga/desliga** | Victor quer controle granular por canal sem acesso ao código | intent-capture | Canais fixos hardcoded |
| D-007 | **Nenhuma ferramenta de mercado resolve o problema completo** | Análise de 4 categorias de ferramentas: nenhuma combina rigor técnico + pipeline vídeo + distribuição omnicanal | market-research | Usar Make.com ou Buffer |
| D-008 | **Build publisher próprio vs. Buffer/Hootsuite** | Controle do fluxo de aprovação; sem dependência de terceiro; custo mensal extra injustificado para uso solo | market-research | Metricool como fallback temporário |
| D-009 | **n8n/Make.com descartados para orquestração** | Inadequados para jobs de vídeo de 5-20 min (timeout); Pub/Sub + Cloud Run Jobs é superior | market-research | n8n self-hosted |
| D-010 | **Sequência de Bolts: dependency-first + risk-first no B1** | Bolt 1 valida os dois maiores riscos (ElevenLabs + HeyGen) antes de construir o restante | scope-definition | Value-first (publisher primeiro) |

---

## Decisões Técnicas e Arquiteturais

| ID | Decisão | Razão | Estágio | Alternativa Rejeitada |
|---|---|---|---|---|
| D-011 | **ElevenLabs TTS com voz clonada do Victor** | Naturalidade máxima; custo ~$0.75/vídeo é aceitável | intent-capture | HeyGen voz nativa do avatar |
| D-012 | **HeyGen Lipsync API v3 (não v2 video/generate)** | v2 descontinua outubro/2026; Lipsync v3 aceita áudio externo (asset_id) | feasibility | Manter v2 até descontinuação |
| D-013 | **Manifesto HTML como contrato de dados (manter formato existente)** | Schema v2 já tem mapeamento segmento→slide explícito; elimina necessidade de Gemini alignment | intent-capture | Manifesto JSON puro sem HTML |
| D-014 | **Eliminação do Gemini para alignment de vídeo** | Mapeamento segmento→slide já está no manifesto; Gemini era workaround para ausência do contrato explícito | feasibility | Manter Gemini alignment |
| D-015 | **Microserviços Pub/Sub como barramento** | Cada etapa tem latência variável (HeyGen 5-45 min); Pub/Sub permite processamento assíncrono real | intent-capture | Chamadas síncronas encadeadas |
| D-016 | **Cloud Run Jobs (não Services) para TTS/Avatar/Editor** | Jobs suportam timeout de até 24h; HeyGen pode levar 45 min; Services têm timeout máximo de 60 min | feasibility | Cloud Run Services para todos |
| D-017 | **GCP Secret Manager para todas as API keys** | Constraint arquitetural imutável do projeto; nunca em env vars hardcoded | feasibility | Firestore para keys |
| D-018 | **Callback do HeyGen (não polling periódico)** | HeyGen v3 suporta `callback_url`; mais eficiente que polling a cada 30s por até 45 min | feasibility | Polling periódico |
| D-019 | **Playwright + FFmpeg para composição de vídeo** | Código existente em `tool-videoyoutube`; reusar e containerizar em vez de reescrever | feasibility | Remotion, FFmpegKit |
| D-020 | **Cada pacote de conteúdo = projeto com kanban** | Victor quer visibilidade de estado de cada conteúdo; modelo de "pasta" por conteúdo | intent-capture | Lista plana de tarefas |

---

## Decisões de Design e UX

| ID | Decisão | Razão | Estágio | Alternativa Rejeitada |
|---|---|---|---|---|
| D-021 | **Duas novas abas no CsmDashboard ("Projetos" + "Pipeline")** | Integração no CSM Studio existente sem nova interface | rough-mockups | Página dedicada separada |
| D-022 | **Side panel para detalhes do projeto (não modal central)** | Preserva contexto do kanban durante revisão de projeto específico | rough-mockups | Modal central bloqueante |
| D-023 | **Dois modais de aprovação distintos (produção vs. publicação)** | Distinção arquitetural crítica: aprovar para gerar ≠ aprovar para publicar; descoberto pelo reviewer | rough-mockups | Um único modal de aprovação |
| D-024 | **Convenção cromática para custo estimado vs. real** | `~R$XX` âmbar para estimativas; `R$XX` branco para reais; tracejado cinza para não executado | rough-mockups | Label de texto `[estim.]` |
| D-025 | **Filtro `[!Erro]` no kanban** | Victor precisa triagem rápida de projetos com falha; descoberto pelo reviewer | rough-mockups | Sem filtro de erro |
| D-026 | **Fallback manual com upload de arquivo** | Constraint COP-01: cada etapa automatizada precisa de fallback manual; inclui upload de vídeo MP4 para HeyGen que falhou | rough-mockups | Apenas "Re-tentar" como recuperação |

---

## Decisões de Compliance e Custo

| ID | Decisão | Razão | Estágio | Alternativa Rejeitada |
|---|---|---|---|---|
| D-027 | **AI disclosure obrigatório + automático no YouTube** | YouTube aplica label automático desde maio/2026; risco de suspensão do canal se não declarar | market-research + feasibility | Disclosure opcional/manual |
| D-028 | **Somente Meta Graph API oficial para Instagram/Facebook/Threads** | ~0% ban risk via API oficial vs. 11-17% via bots; decisão de conformidade, não só técnica | market-research | Automação via browser/scraper |
| D-029 | **Teto de R$100/pacote como gate arquitetural** | CostTrackerService bloqueia execução se estimativa exceder o limite antes de acionar APIs pagas | intent-capture | Alertas apenas, sem bloqueio |
| D-030 | **ElevenLabs Turbo v2.5 como modelo padrão** | Melhor relação custo/qualidade para pt-BR ($0.05/1k chars); Multilingual v2 como upgrade opcional | market-research | Google Chirp 3 HD (sem clone) |

---

## Decisões Abertas (para Inception)

| ID | Questão | Impacto | Owner |
|---|---|---|---|
| Q-001 | Custo real HeyGen Lipsync API v3 PAYG por segundo | Define se teto R$100 é atingível; pode requerer plano Creator ($29/mês) | Victor (spike) |
| Q-002 | ElevenLabs Instant Clone vs. Professional Clone — qualidade para pt-BR | Define plano ($22/mês vs $99/mês) | Victor (teste) |
| Q-003 | Painel de configuração como aba do CsmDashboard ou página separada | Impacto em routing do Next.js | Application Design |
| Q-004 | Carrosseis/image posts: design template HTML ou geração de imagem por IA | Impacto em Bolt 5 e complexidade do pipeline | Requirements Analysis |
| Q-005 | Endpoint `POST /projects/:id/stages/:stage/manual-upload` — escopo e contrato | Capacidade de fallback manual descoberta nos wireframes | Requirements Analysis |
| Q-006 | YouTube Community Posts API — disponibilidade e escopos OAuth | Bolt 5 pode ser simplificado se API não estiver disponível | Feasibility spike |
