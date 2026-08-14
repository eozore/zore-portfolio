# Análise Build vs. Buy vs. Partner
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Referência: [intent-statement.md](../intent-capture/intent-statement.md)

---

## Framework de Decisão

Para cada componente da pipeline, a decisão segue três critérios:
1. **Diferencial estratégico?** — Se sim, construir internamente preserva a vantagem.
2. **Commodidade técnica resolvida?** — Se sim, comprar/integrar API evita retrabalho.
3. **Custo/controle aceitável?** — Se o fornecedor tem pricing previsível e API estável, partner é adequado.

---

## Componente 1: Geração de Conteúdo (CMO Agent + Writer + Distribution)

| Opção | Avaliação |
|---|---|
| **BUILD** (atual) | Correto. É o núcleo do diferencial — o rigor técnico e o tom de Victor só existem nos prompts customizados. Nenhuma ferramenta de mercado replica isso. |
| Buy (Jasper, Copy.ai) | Descartado. Inadequado para conteúdo técnico com LaTeX e precisão matemática. |
| Partner (Claude/ChatGPT API direto) | Descartado. A decisão arquitetural imutável do projeto é usar modelos do Google (Gemini via Vertex AI). |

**Decisão: BUILD. Já implementado em `agents/cmo_agent/`. Evoluir, não substituir.**

---

## Componente 2: Text-to-Speech (ElevenLabs)

| Opção | Avaliação |
|---|---|
| BUILD | Inviável. Treinar modelo de síntese de voz de qualidade é um problema de ML de meses/anos. |
| **PARTNER — ElevenLabs** (escolhido) | Correto. API madura, voz clonada do Victor em pt-BR, qualidade natural. Custo ~$0.75/vídeo é aceitável. |
| Partner — Google Chirp 3 HD | Alternativa viável como fallback. Sem clone de voz mas custo menor ($0.03/1k chars). |
| Partner — Azure Neural TTS | Alternativa para clone de voz com custo menor. Qualidade pt-BR inferior ao ElevenLabs. |

**Decisão: PARTNER ElevenLabs (primário) + Google Chirp 3 HD (fallback de custo).** A camada de abstração no código deve permitir trocar o provedor sem reescrever a pipeline.

---

## Componente 3: Geração de Avatar / Vídeo (HeyGen)

| Opção | Avaliação |
|---|---|
| BUILD | Inviável. Geração de avatar fotorrealista com lip-sync é estado da arte em deep learning — não replicável internamente. |
| **PARTNER — HeyGen** (atual, já integrado) | Correto. API v2 já está implementada em `apps/web/src/app/api/csm/heygen/route.ts`. Pay-as-you-go. |
| Partner — Synthesia | Alternativa se HeyGen mudar pricing drasticamente. API menos madura para áudio externo. |
| Partner — D-ID | Alternativa para vídeos curtos. Menos adequado para vídeos longos de 15 min. |

**Decisão: PARTNER HeyGen. Encapsular chamadas em abstração `AvatarService` para facilitar troca de fornecedor se necessário.**

---

## Componente 4: Edição de Vídeo (composição slides + avatar)

| Opção | Avaliação |
|---|---|
| **BUILD** (atual, `tool-videoyoutube`) | Correto. O editor precisa entender o contrato do manifesto JSON, as posições dos slides e o formato específico dos vídeos do éozoré. Ferramentas genéricas não têm essa especificidade. FFmpeg é a base certa — livre, poderoso, amplamente suportado no GCP. |
| Buy (Adobe Premiere via API) | Não existe API de edição programática real para Premiere. |
| Buy (Runway ML Edit API) | Focado em efeitos de IA, não em composição determinística de slides. |

**Decisão: BUILD. Evoluir o `tool-videoyoutube` existente para ser um microserviço Cloud Run que consome mensagens Pub/Sub.**

A mudança arquitetural chave: **eliminar o Gemini alignment** (que era usado para inferir quando cada slide aparece) e **substituir por leitura direta do manifesto** (que já tem `slide_index` por segmento). O editor vira determinístico: recebe o vídeo do avatar + o manifesto → sobrepõe as ilustrações nos timestamps calculados a partir da duração do áudio de cada segmento.

---

## Componente 5: Publicação nas Redes Sociais

| Opção | Avaliação |
|---|---|
| **BUILD** (Publisher Service) | Preferível. Controle total do fluxo de aprovação, armazenamento dos dados de aprovação no Firestore, sem dependência de terceiro. Cada plataforma tem SDK/API oficial documentada. |
| Buy — Buffer/Hootsuite/Later | Adiciona ~$15-50/mês de custo, perde controle do pipeline, adiciona dependência de terceiro. Para uso solo sem necessidade de UI de agendamento social sofisticada, o custo não se justifica. |
| Partner — Metricool (gratuito) | Opção de fallback de curto prazo se o Publisher Service não estiver pronto. API gratuita cobre LinkedIn, Instagram, YouTube, Threads. |

**Decisão: BUILD (Publisher Service). Metricool como fallback temporário durante desenvolvimento.**

APIs a integrar diretamente:
- **YouTube Data API v3** — upload de vídeo + metadata + disclosure de IA (via GCP service account, já no ecossistema)
- **Meta Graph API** — publicação no Instagram Reels e Threads (tokens OAuth armazenados no Secret Manager)
- **LinkedIn API** — posts de texto e vídeo (tokens OAuth)
- **Facebook Graph API** — compartilhado com o Instagram via Meta

---

## Componente 6: Orquestração e Mensageria

| Opção | Avaliação |
|---|---|
| **BUILD + GCP Pub/Sub** (escolhido) | Correto. Nativo ao GCP, custo muito baixo para o volume de mensagens do éozoré (~4 mensagens por pacote de conteúdo/semana), sem timeout, observabilidade via Cloud Logging. |
| n8n self-hosted | Adequado para orquestração de SaaS rápida, inadequado para jobs de vídeo de 5-20 min. |
| Make.com | Idem n8n, com dependência de plataforma externa. |
| GCP Workflows | Alternativa viável se a lógica de orquestração ficar muito complexa. Pode complementar Pub/Sub. |

**Decisão: BUILD com GCP Pub/Sub como barramento. GCP Workflows como complemento opcional para lógica de retry/compensação.**

---

## Componente 7: Armazenamento de Mídia

| Opção | Avaliação |
|---|---|
| **BUILD + GCS** (já definido no `build_csm_tool.md`) | Correto. Google Cloud Storage é o padrão do projeto. Lifecycle policy para expirar mídias temporárias após 30 dias já está planejada. |
| AWS S3 | Fora do ecossistema GCP. Descartado. |
| Cloudinary | Adiciona custo e dependência. Desnecessário quando GCS cobre tudo. |

**Decisão: BUILD com GCS. Hierarquia `/tenants/{tenantId}/projects/{projectId}/` para organização por projeto.**

---

## Resumo das Decisões Build vs. Buy

| Componente | Decisão | Justificativa |
|---|---|---|
| Geração de conteúdo (CMO/Writer/Distribution) | BUILD | Diferencial estratégico — rigor técnico único |
| Text-to-Speech | PARTNER (ElevenLabs) | Commodity de alta qualidade, custo aceitável |
| Avatar / Vídeo IA | PARTNER (HeyGen) | Inviável replicar internamente |
| Edição de vídeo (composição) | BUILD (evoluir tool-videoyoutube) | Específico ao contrato do manifesto |
| Publicação social | BUILD (Publisher Service) | Controle do fluxo de aprovação |
| Orquestração / Mensageria | BUILD + GCP Pub/Sub | Nativo ao ecossistema, sem timeout |
| Armazenamento de mídia | BUILD + GCS | Já é o padrão do projeto |
| Painel de configuração | BUILD (nova aba CSM Studio) | Integrado ao workflow existente |

**Princípio geral:** Comprar onde é commodity, construir onde há diferencial ou onde a especificidade do éozoré torna ferramentas genéricas inadequadas.
