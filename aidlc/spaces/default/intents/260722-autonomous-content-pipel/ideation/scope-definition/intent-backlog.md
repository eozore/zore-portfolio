# Intent Backlog
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Priorização: MoSCoW + sequência por dependência e risco técnico.
> Referências: [scope-document.md](./scope-document.md) | [feasibility-assessment.md](../feasibility/feasibility-assessment.md)

---

## Legenda de Prioridade (MoSCoW)

| Código | Significado |
|---|---|
| M | Must Have — sem isso o sistema não funciona |
| S | Should Have — valor alto, não bloqueia MVP |
| C | Could Have — desejável mas postergável |
| W | Won't Have (agora) — fora do escopo desta entrega |

---

## BOLT 1 — Walking Skeleton: Validação de Risco + Fundação

*Objetivo: provar que o fluxo end-to-end funciona antes de construir o restante.*

| ID | Capacidade | MoSCoW | Dependências | Risco |
|---|---|---|---|---|
| **B1-01** | Infraestrutura Pub/Sub: ativar API, criar tópicos e subscriptions para cada etapa do pipeline | M | — | Baixo |
| **B1-02** | Schema Firestore `content_projects`: documento de projeto com estados do kanban, manifesto, metadados de produção e histórico de aprovação | M | B1-01 | Baixo |
| **B1-03** | TTS Job (Cloud Run Job): consome manifesto do Firestore, chama ElevenLabs API por segmento, faz upload dos áudios para GCS, publica mensagem Pub/Sub `tts_completed` | M | B1-01, B1-02 | **Alto** — qualidade de clone pt-BR a validar |
| **B1-04** | Avatar Job (Cloud Run Job): consome `tts_completed`, faz upload de áudios para HeyGen Assets API, chama HeyGen Lipsync API v3 com modo `precision`, recebe callback quando pronto, baixa vídeo para GCS, publica `avatar_completed` | M | B1-03 | **Alto** — HeyGen v3 Lipsync API, custo real a confirmar |
| **B1-05** | Kanban básico no CSM Studio: nova aba "Projetos" com lista de `content_projects` e estado atual de cada um | M | B1-02 | Baixo |
| **B1-06** | Gate de aprovação no kanban: botão "Aprovar para Produção" que muda estado para `generating_media` e armazena `approval_data` (userId, timestamp, versão do manifesto) no Firestore | M | B1-05 | Baixo |
| **B1-07** | Migração HeyGen v2 → v3: refatorar `apps/web/src/app/api/csm/heygen/route.ts` para usar endpoints v3 | M | — | Médio |
| **B1-08** | ElevenLabs Voice Clone setup: configurar voz clonada do Victor no ElevenLabs e armazenar `voice_id` no Secret Manager | M | — | **Alto** — depende de Victor gravar amostras |

---

## BOLT 2 — Video Editor: Composição Determinística

*Objetivo: transformar avatar + slides em vídeos horizontal e vertical prontos.*

| ID | Capacidade | MoSCoW | Dependências | Risco |
|---|---|---|---|---|
| **B2-01** | Video Editor Job (Cloud Run Job): refatorar `tool-videoyoutube` como job containerizado que consome `avatar_completed` | M | B1-04 | Médio |
| **B2-02** | Renderização de slides HTML via Playwright: cada slide do manifesto renderizado como clipe de vídeo pela duração exata do segmento de áudio | M | B2-01 | Médio — Playwright em container Alpine |
| **B2-03** | Composição FFmpeg horizontal (1920×1080): avatar + slides sobrepostos nos timestamps do manifesto | M | B2-02 | Baixo |
| **B2-04** | Composição FFmpeg vertical (1080×1920): mesmo pipeline para formato Reels/Shorts | M | B2-02 | Baixo |
| **B2-05** | Jump cuts automáticos: remoção de silêncios do vídeo final (código existente em `editor_pipeline.py`, adaptar para o novo pipeline) | S | B2-03, B2-04 | Baixo |
| **B2-06** | Upload dos vídeos finais para GCS e publicação de `video_ready` no Pub/Sub | M | B2-03, B2-04 | Baixo |

---

## BOLT 3 — Publisher Service: Publicação Omnicanal

*Objetivo: publicar automaticamente em todos os canais habilitados.*

| ID | Capacidade | MoSCoW | Dependências | Risco |
|---|---|---|---|---|
| **B3-01** | Publisher Service base: consome `video_ready` do Pub/Sub, lê configuração de canais do Firestore, roteia para cada publisher habilitado | M | B2-06 | Baixo |
| **B3-02** | YouTube Publisher: upload via YouTube Data API v3 com AI disclosure obrigatório (campo `selfDeclaredAiGeneratedContent`) | M | B3-01 | Médio — OAuth setup necessário |
| **B3-03** | Instagram Reels Publisher: publica vídeo vertical via Meta Graph API | M | B3-01 | Baixo — já operacional |
| **B3-04** | Threads Publisher: publica texto derivado via Meta Graph API | M | B3-01 | Baixo — já operacional |
| **B3-05** | LinkedIn Publisher: publica post de texto/vídeo via LinkedIn API v2 | M | B3-01 | Baixo — já operacional |
| **B3-06** | Facebook Publisher: publica via Meta Graph API | S | B3-01 | Baixo — já operacional |
| **B3-07** | Blog Publisher: publica artigo no Firestore `articles` (já existe via `/api/csm/publish`) | M | B3-01 | Baixo — já existe |
| **B3-08** | Gate de aprovação de publicação: estado `awaiting_publication` no kanban, botão "Publicar Agora" ou publicação agendada | M | B3-01, B1-06 | Baixo |
| **B3-09** | Cloud Scheduler: job diário que verifica pacotes aprovados na fila e publica o próximo conforme horário configurado | M | B3-01 | Baixo |
| **B3-10** | Throttler de publicação: respeita rate limits por canal, não publica mais de N vezes/dia por rede (configurável com limites máximos hardcoded) | M | B3-01 | Baixo |

---

## BOLT 4 — Painel de Configuração + Kanban Completo

*Objetivo: dar a Victor controle total do sistema sem precisar de acesso ao código.*

| ID | Capacidade | MoSCoW | Dependências | Risco |
|---|---|---|---|---|
| **B4-01** | Config Service (nova aba no CSM Studio): painel de configuração de canais com toggle liga/desliga, campos de API keys (criptografados no Secret Manager) e horário de publicação por canal | M | — | Baixo |
| **B4-02** | Secret Manager integration: salvar/recuperar API keys (ElevenLabs, HeyGen, tokens OAuth) via GCP Secret Manager na UI do painel | M | B4-01 | Baixo |
| **B4-03** | Kanban completo: visualização de todos os projetos com estado, data de criação, custo acumulado, preview do conteúdo e histórico de ações | M | B1-05 | Baixo |
| **B4-04** | CostTrackerService: rastreamento de custo por etapa (ElevenLabs créditos, HeyGen API calls, Gemini tokens, GCP) com exibição no kanban e alerta em 80% do teto | M | B1-02 | Baixo |
| **B4-05** | Fallback manual por etapa: botões no kanban para re-disparar individualmente TTS Job, Avatar Job, Video Editor Job e Publisher por canal | S | B4-03, B1-03, B1-04, B2-01, B3-01 | Baixo |
| **B4-06** | Log de erros no painel: erros de cada job aparecem inline no card do projeto (não apenas no Cloud Logging) | S | B4-03 | Baixo |
| **B4-07** | Alertas de token OAuth expirando: notificação no painel quando refresh token tem < 7 dias de vida | S | B4-01 | Baixo |

---

## BOLT 5 — Distribuição Social Completa

*Objetivo: publicar todos os formatos derivados (carrosseis, stories, image posts, community posts).*

| ID | Capacidade | MoSCoW | Dependências | Risco |
|---|---|---|---|---|
| **B5-01** | Carrossel Publisher: publicação de carrosseis (sequência de imagens) no Instagram e LinkedIn | S | B3-01, Distribution Agent | Baixo |
| **B5-02** | Image Post Publisher: publicação de post com imagem única no Instagram e LinkedIn | S | B3-01, Distribution Agent | Baixo |
| **B5-03** | YouTube Community Post Publisher: publica texto/imagem na comunidade do canal | S | B3-02 | Médio — requer escopo adicional no OAuth |
| **B5-04** | Stories scheduling: agendamento de stories do Instagram com sequência de 5-6 por semana | C | B3-03 | Médio — Stories têm TTL de 24h, timing é crítico |
| **B5-05** | YouTube Shorts: publicação do vídeo vertical como Short (mesmo arquivo do Reels, tag diferente) | M | B3-02, B2-04 | Baixo |

---

## Resumo de Capacidades por Prioridade

| MoSCoW | Quantidade | Bolts |
|---|---|---|
| **Must Have** | 27 capacidades | B1 a B5 |
| **Should Have** | 7 capacidades | B2-05, B3-06, B4-05, B4-06, B4-07, B5-01, B5-02 |
| **Could Have** | 1 capacidade | B5-04 |
| **Won't Have** | Multi-tenancy, TikTok, thumbnails IA, etc. | — |

---

## Mapa de Valor (Fluxo End-to-End por Bolt)

```
Victor (sessão CMO)
    |
    +-- Aprova pacote [B1-06] --------> Pub/Sub: "package_approved"
                                             |
                                        TTS Job [B1-03]
                                        ElevenLabs: segmento 1..N
                                             |
                                        Pub/Sub: "tts_completed"
                                             |
                                        Avatar Job [B1-04]
                                        HeyGen Lipsync v3
                                             |
                                        Pub/Sub: "avatar_completed"
                                             |
                                        Video Editor Job [B2-01..B2-06]
                                        Playwright + FFmpeg
                                        horizontal.mp4 + vertical.mp4
                                             |
                                        Pub/Sub: "video_ready"
                                             |
                              +----------+--+-----------+
                              |          |              |
                         YouTube    Instagram      LinkedIn
                         [B3-02]     [B3-03]       [B3-05]
                              |      Threads        Blog
                              |      [B3-04]       [B3-07]
                              |
                         Aprovação gate [B3-08]
                         Victor clica "Publicar" ou
                         Cloud Scheduler [B3-09] publica automaticamente
```

---

## Critério de Aceitação do Sistema Completo

```
DADO que Victor completou uma sessão CMO e aprovou o pacote,
QUANDO o sistema processar o pipeline completo,
ENTÃO:
  - Artigo publicado no blog em < 5 min após aprovação
  - Vídeo horizontal publicado no YouTube com AI disclosure em < 2h
  - Vídeo vertical publicado como Instagram Reel e YouTube Short em < 2h
  - Posts de texto publicados no LinkedIn e Threads em < 2h
  - Custo total exibido no painel ≤ R$100
  - Zero intervenções manuais de Victor além da cocriação e aprovação
```
