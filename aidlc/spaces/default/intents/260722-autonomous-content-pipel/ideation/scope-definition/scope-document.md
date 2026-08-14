# Scope Document
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Referências: [intent-statement.md](../intent-capture/intent-statement.md) | [feasibility-assessment.md](../feasibility/feasibility-assessment.md) | [constraint-register.md](../feasibility/constraint-register.md)

---

## Visão do Sistema em Uma Frase

Um **Content Production Studio** integrado ao CSM Studio existente onde Victor, após uma sessão semanal de cocriação com o CMO Agent, aprova um pacote de conteúdo e o sistema executa automaticamente toda a cadeia — TTS, avatar, edição de vídeo e publicação omnicanal — sem intervenção manual.

---

## Fronteira IN / OUT

### ✅ IN — Está no escopo

**Infraestrutura e Orquestração**
- Ativação e configuração do GCP Pub/Sub como barramento de mensagens
- Cloud Run Jobs para TTS, Avatar e Video Editor (processamento assíncrono longo)
- Schema Firestore `content_projects` para kanban de projetos
- `CostTrackerService` com gate de custo por pacote (teto R$100)

**Cocriação e Aprovação**
- Kanban de projetos no CSM Studio (nova aba ou painel): estados `Em Cocriação → Aguardando Aprovação → Gerando Mídia → Aguardando Publicação → Publicado`
- Gate de aprovação obrigatório antes de qualquer publicação, com dados de aprovação armazenados no Firestore
- Painel de configuração de canais: liga/desliga por rede, API keys (via Secret Manager), horários de publicação por canal

**Pipeline de Áudio**
- TTS Job: ElevenLabs API gera áudio MP3 por segmento do manifesto
- Upload de áudio para HeyGen Assets API
- Clone de voz do Victor configurado no ElevenLabs

**Pipeline de Avatar**
- Avatar Job: HeyGen Lipsync API v3 (`POST /v3/lipsyncs`) com modo `precision`
- Polling do status via HeyGen callback URL
- Download do vídeo avatar para GCS após conclusão
- Migração do código existente (`heygen/route.ts`) de v2 para v3

**Pipeline de Vídeo**
- Video Editor Job: refatoração do `tool-videoyoutube` como Cloud Run Job
- Composição determinística: avatar + slides HTML renderizados via Playwright
- Mapeamento segmento→slide direto do manifesto (sem Gemini alignment)
- Geração de dois outputs: horizontal (1920×1080) e vertical (1080×1920)
- Jump cuts automáticos (remoção de silêncios) — já existe em `editor_pipeline.py`

**Publicação**
- Publisher Service: publicação automática via APIs oficiais em todos os canais habilitados
- YouTube: upload com AI disclosure obrigatório (campo preenchido automaticamente)
- Instagram Reels + Threads + Facebook + LinkedIn: publicação via Meta Graph API e LinkedIn API
- YouTube Community Posts: texto derivado do artigo
- Carrosseis: publicação de imagens sequenciais (Instagram/LinkedIn)
- Agendamento via Cloud Scheduler (1 pacote/dia, horário configurável por canal no painel)
- Throttler conservador por canal (rate limits respeitados)

**Distribuição de Conteúdo Derivado**
- Distribution Agent (já existe) gera: LinkedIn posts, Shorts scripts, Reels scripts, carrosseis, image posts, stories
- Esses conteúdos entram na fila de publicação e aparecem no kanban

---

### ❌ OUT — Fora do escopo desta entrega

| Capacidade | Razão | Quando |
|---|---|---|
| Multi-tenancy / SaaS para outros criadores | Roadmap de longo prazo — requer arquitetura de tenant isolation | Fase futura |
| Análise de métricas de performance de canal | Não foi solicitado; seria integração com YouTube Analytics API | Fase futura |
| Geração automática de thumbnails com IA | Requer modelo de geração de imagem (Imagen/DALL-E) — escopo separado | Fase futura |
| Integração com TikTok | TikTok API para criadores tem restrições severas; não mencionado pelo Victor | Fase futura |
| Automação de respostas a comentários | Problema diferente; risco de ban por comportamento de bot | Fora do escopo |
| Geração de newsletter / email | Canal não mencionado | Fase futura |
| Fine-tuning de modelos próprios | Escopo de ML engineering, não de content pipeline | Fora do escopo |
| Integração com plataformas de curso (Hotmart, Udemy) | Fase de produto educacional — depois da pipeline estabelecida | Fase futura |

---

## Princípios de Priorização

1. **Pipeline end-to-end primeiro** — uma versão funcional de ponta a ponta (mesmo que com limitações) é mais valiosa do que componentes individuais perfeitos.
2. **Risco técnico resolvido no Bolt 1** — ElevenLabs clone + HeyGen Lipsync v3 são as integrações mais incertas; devem ser validadas antes de construir o restante.
3. **Aprovação humana não negociável** — o gate de aprovação (constraint CC-06) não é uma feature opcional; é um requisito arquitetural.
4. **Operabilidade manual como fallback** — cada etapa automatizada precisa de um endpoint de invocação manual no painel (constraint COP-01).
5. **Conformidade desde o início** — AI disclosure, rate limiting e Secret Manager não são "para depois"; são parte do design de cada componente.

---

## Sequência de Construção (Bolts)

A sequência segue o fluxo natural do pipeline com ajuste risk-first no Bolt 1:

```
Bolt 1 — Walking Skeleton (Risco + Fundação)
  Validar fluxo completo: manifesto → ElevenLabs → HeyGen Lipsync v3 → video output
  Infraestrutura Pub/Sub + Cloud Run Jobs
  Schema Firestore content_projects + kanban básico

Bolt 2 — Video Editor + Composição Completa
  Refatorar tool-videoyoutube como Cloud Run Job
  Composição determinística horizontal + vertical
  Jump cuts automáticos

Bolt 3 — Publisher Service (YouTube + Meta)
  YouTube Data API v3 com AI disclosure
  Meta Graph API (Instagram Reels + Threads + Facebook)
  LinkedIn API
  Cloud Scheduler para publicação diária agendada

Bolt 4 — Painel de Configuração + Kanban Completo
  Painel de canais com liga/desliga e keys (Secret Manager)
  Kanban de projetos completo com estados e histórico
  CostTrackerService com gate de custo
  Alertas de erro no painel (fallback manual)

Bolt 5 — Distribuição Social Completa
  Publicação de conteúdo derivado (carrosseis, image posts, stories, community posts)
  Throttler configurável por canal
  Agendamento inteligente por horário de pico
```

---

## Definição de "Pronto" para o Sistema Completo

O sistema está completo quando Victor consegue:
1. Fazer uma sessão de cocriação CMO no CSM Studio (30-60 min)
2. Aprovar o pacote no kanban com um clique
3. Ver o sistema processar automaticamente todo o pipeline (TTS → Avatar → Editor → Publisher)
4. Encontrar o vídeo publicado no YouTube e os posts nas redes sociais no dia seguinte
5. Ter visto o custo total no painel (≤ R$100)
6. Ter zero ações manuais além da cocriação e da aprovação

Tudo isso dentro de uma semana de operação real sem intervenção técnica.
