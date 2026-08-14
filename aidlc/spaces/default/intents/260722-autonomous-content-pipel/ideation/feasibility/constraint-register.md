# Constraint Register
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Referências: [intent-statement.md](../intent-capture/intent-statement.md) | [build-vs-buy.md](../market-research/build-vs-buy.md)

---

## Constraints Técnicos

| ID | Constraint | Fonte | Impacto no Design |
|---|---|---|---|
| CT-01 | **LLMs obrigatoriamente do Google (Gemini)** | Decisão do Victor (intent-capture Q3 / AGENTS.md) | Vertex AI como único endpoint de inferência. Proibido usar OpenAI, Anthropic ou outros LLMs. |
| CT-02 | **HeyGen v2 descontinuado em out/2026** | Documentação HeyGen | Todo código de avatar deve usar HeyGen v3 API. O `heygen/route.ts` existente precisa de refatoração. |
| CT-03 | **Playwright/Chromium em Cloud Run Jobs** | Compatibilidade de container | Imagem Docker deve incluir Chromium; usar `mcr.microsoft.com/playwright` ou `browserless/chrome` como base. Memória mínima: 2GB por job. |
| CT-04 | **Pub/Sub requer at-least-once delivery** | Garantia do GCP Pub/Sub | Todos os consumers de Pub/Sub devem ser idempotentes — processar a mesma mensagem duas vezes não deve ter efeito colateral. |
| CT-05 | **Secret Manager para todas as chaves externas** | Decisão arquitetural imutável (platform_technical_context.md) | NUNCA armazenar API keys em env vars hardcoded. ElevenLabs key, HeyGen key, tokens OAuth das redes sociais — todos no Secret Manager. |
| CT-06 | **Firebase Admin SDK como única fonte de credenciais** | Decisão arquitetural imutável | REST direto para Vertex AI usando token do Firebase Admin ADC. Não adicionar SDK Vertex AI para Node. |
| CT-07 | **CSS Modules para estilização no frontend** | Decisão arquitetural imutável | Painel de configuração e kanban usam CSS Modules, não TailwindCSS. |
| CT-08 | **Agentes Python como microserviços separados do Next.js** | Decisão arquitetural imutável | TTS Job, Avatar Job, Video Editor Job e Publisher Service são Cloud Run Services/Jobs em Python. Não integrar lógica pesada no Next.js. |

---

## Constraints de Compliance e Regulatório

| ID | Constraint | Fonte | Impacto no Design |
|---|---|---|---|
| CC-01 | **YouTube: AI Disclosure obrigatório** | YouTube Policy (maio/2026) — detecção automática ativa | Publisher Service deve preencher o campo `aiGeneratedContent: true` no payload de upload da YouTube Data API v3 em 100% dos vídeos da pipeline. |
| CC-02 | **Meta Graph API: usar apenas APIs oficiais** | Meta Developer Platform ToS | Proibido usar Selenium/Playwright/puppeteer para simular postagem no Instagram/Facebook. Somente Graph API com tokens OAuth legítimos. |
| CC-03 | **LGPD: voz clonada é dado biométrico** | Lei 13.709/2018, Art. 5º II | A voz clonada do Victor é dado biométrico sensível. Deve ser armazenada exclusivamente em GCS com acesso restrito ao service account do projeto. Não vazar para terceiros além do ElevenLabs (que tem sua própria política). |
| CC-04 | **Rate limiting conservador nas plataformas** | ToS de cada plataforma | Instagram: máximo 1 post de feed/dia + 1 Reel/dia. LinkedIn: máximo 1 post/dia. YouTube: máximo 1 upload/dia. Threads: máximo 1-2 posts/dia. Configurável no painel mas com limites máximos hardcoded. |
| CC-05 | **Tokens OAuth: nunca logar ou expor** | Boas práticas de segurança | Os tokens de acesso das redes sociais nunca devem aparecer em logs do Cloud Logging. Usar variáveis mascaradas. Rotação automática quando possível. |
| CC-06 | **Conteúdo de IA deve ser curatorizado por humano antes da publicação** | Política de uso responsável + contexto do Victor | O gate de aprovação manual (Q4: D) é um constraint arquitetural, não apenas uma preferência. O sistema nunca publica sem `approval_status: "approved"` no Firestore. |

---

## Constraints Orçamentários

| ID | Constraint | Limite | Mecanismo de Controle |
|---|---|---|---|
| CO-01 | **Custo máximo por pacote de conteúdo completo** | R$100 (~$20 ao câmbio) | `CostTrackerService` acumula custo de cada etapa (ElevenLabs + HeyGen + Gemini + GCP) e bloqueia o processamento se estimativa ultrapassar o limite antes de acionar APIs pagas. |
| CO-02 | **Alerta de custo por etapa** | 80% do limite ($16) | Cloud Monitoring budget alert + notificação no painel CSM Studio quando custo acumulado atinge 80% do teto. |
| CO-03 | **Custo de infra GCP não deve exceder R$50/mês** | R$50/mês (~$10) | Cloud Billing budget alert; revisar se custo de Cloud Run Jobs ou Storage escalar inesperadamente. |

---

## Constraints de Operabilidade

| ID | Constraint | Razão | Implementação |
|---|---|---|---|
| COP-01 | **Fallback manual para cada etapa automática** | Victor opera sozinho; automações quebram | Cada microserviço deve expor um endpoint de invocação manual no painel CSM Studio. TTS pode ser acionado com upload de áudio próprio. HeyGen pode ser acionado separadamente. Publisher pode postar item individual. |
| COP-02 | **Logs de erro acessíveis no painel** | Debugging solo sem equipe de ops | Erros de cada job aparecem na UI do kanban (não apenas no Cloud Logging). |
| COP-03 | **Cada canal pode ser desligado individualmente** | Victor quer controle granular | A tabela `channel_config` no Firestore controla `enabled: bool` por canal. Se LinkedIn está desligado, o Publisher Service pula silenciosamente. |
