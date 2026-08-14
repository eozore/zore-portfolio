# éozoré Content Studio — Roadmap de Melhoria

**Documento de planejamento para próximas sessões.**
Baseado em análise crítica do estado atual após os Sprints 1–4 e sessões de teste em produção.

---

## Estado atual em produção (julho 2026)

**O que funciona de ponta a ponta:**
- Chat CMO → pauta com 8 campos (hardskills, objetivo_aprendizado, etc.)
- Geração de artigo: Critic → Research → Writing → Validator (com regeneração automática)
- Roteiro segmentado com âncoras (scriptwriter_agent via vertex_generate.py)
- Thumbnails HTML 1200×628 (thumbnail_agent)
- Copies LinkedIn + Threads (copy_agent)
- Derivações omnicanal: Reels, Shorts, Carrosséis, Stories (distribution_agent, migrado para vertex_generate)
- Calendário editorial semanal com popup de edição
- Artigo renderizado com LaTeX, Mermaid, syntax highlighting
- Pipeline de vídeo: TTS (ElevenLabs) → HeyGen → VideoEditor → Publisher
- Publicação agendada via social_queue + publisher-scheduled (Cloud Scheduler horário)

**O que não funciona ainda:**
- Slides visuais no manifesto (placeholders sem conteúdo)
- Processo de avatar_job: concatena todos os áudios em um único vídeo — segmentos não são individuais
- Calendário sem cores por projeto (todos os eventos parecem iguais)
- Sem tela de biblioteca de projetos ("pasta de conteúdos")

---

## Problemas críticos identificados

### P1 — Avatar Job arquitetura incorreta

**O que está errado:**
O `avatar_job` concatena todos os segmentos de áudio em um único MP3 e faz uma única chamada ao HeyGen. O resultado é um vídeo contínuo sem marcações. O `video_editor_job` tenta fatiar esse vídeo de volta por `min_duration_s` estimado — o que é uma aproximação frágil que desincroniza avatar e slides.

**Como deveria ser:**
Cada segmento com `script != ""` → um WAV separado → uma chamada HeyGen separada → um vídeo curto por segmento. O `video_editor_job` então concatena os vídeos na ordem do manifesto, intercalando com os slides (Playwright). Isso está documentado na arquitetura mas não implementado.

**Impacto:** vídeos gerados têm timing incorreto entre fala e slides.

---

### P2 — slide_designer_agent não existe

**O que está errado:**
Os slides no manifesto são placeholders vazios:
```html
<section class="slide" id="yt-02"><div class="slide-id">// yt-02</div></section>
```
Quando o VideoEditorJob renderiza via Playwright, grava telas pretas com só o ID.

**Como deveria ser:**
Um `slide_designer_agent` que recebe o segmento (beat, script, âncoras) e gera um HTML/SVG animado para cada slide, seguindo o design system do `pacote-finetuning-v2.html`.

**Cada slide precisa ter:**
- Título/conceito central em Space Grotesk Bold
- Elemento visual: SVG inline de matriz, grafo, equação, ou gráfico de barras
- Elementos com IDs `fd1, fd2, fd3, fd4, b1, b2, b3, b4` — reveláveis pelas âncoras
- Animações CSS de entrada (fade + translate) para cada elemento
- Logo éozoré no canto

---

### P3 — agent.py com 1900 linhas — refatoração necessária

**O que está errado:**
`agent.py` tem 1900 linhas e orquestra tudo: interview, generate, youtube, repurpose, package, build-manifest, render-motion, merge-video, etc. Isso cria:
- Dificuldade de debug (uma falha afeta tudo)
- Cold starts mais lentos (importa todos os agentes na inicialização)
- Impossibilidade de escalar endpoints independentemente

**Como deveria ser:**
Serviços FastAPI separados por domínio, cada um deployado independentemente:
- `cmo-editorial` → /interview, /generate, /youtube
- `cmo-specialist` → /package, /validate
- `cmo-distribution` → /repurpose, /build-manifest

---

### P4 — Validator agente bloqueia o artigo com critérios rígidos demais

**O que está errado:**
O `validator_agent` reprova artigos sem `python-plot` e regenera, mas o modelo às vezes não gera `python-plot` por falta de dados numéricos para graficar. Em artigos conceituais (ex: ética em IA), um gráfico forçado piora o conteúdo.

**Como deveria ser:**
Os critérios do validator devem ser contextuais com base no tipo de artigo. Artigos matemáticos/técnicos: código + Mermaid obrigatórios. Artigos conceituais/estratégicos: apenas rigor de texto.

---

### P5 — Gráficos python-plot não renderizam na maioria dos casos

**O que está errado:**
O `writing_agent` gera blocos ` ```python-plot ` mas o `RichArticleRenderer` tenta parsear o código Python com regex simples. Qualquer variação na sintaxe quebra o parser e o gráfico não aparece.

**Como deveria ser:**
Executar o código Python no backend (code_executor já existe), salvar a imagem no GCS, e retornar a URL para o frontend renderizar como `<img>`. O frontend não deve tentar executar Python.

---

### P6 — Sem biblioteca de projetos — conteúdo "perdido"

**O que está errado:**
Não existe tela para navegar por projetos anteriores. Se o usuário fecha o browser, a sessão muda, ou inicia nova reunião, o conteúdo anterior fica inacessível via UI (existe no Firestore mas sem forma de acessar).

**Como deveria ser:**
Tela `/admin/projetos` que lista `content_projects` e `csm_sessions` do Firestore. Para cada projeto: título, data, status do pipeline, preview do artigo, conteúdo de redes sociais. Com opção de reabrir e continuar de onde parou.

---

### P7 — Publicação não respeita scheduled_at para texto imediato

**O que está errado:**
Quando o usuário clica "Aprovar Pacote", os items de texto (LinkedIn, Threads) vão para `social_queue` com `status=planned` e `scheduled_at`. O `publisher-scheduled` roda a cada hora mas não está sendo monitorado. Se a hora já passou, publica na próxima rodada. Se deu erro, o usuário não sabe.

**O que falta:**
- Tela de status de publicação em tempo real no Calendário
- Notificação quando um item é publicado ou falha
- Retry automático com backoff para erros de rate limit

---

## Roadmap por prioridade

### Fase 1 — Estabilidade (próxima sessão)

**1.1 — Refatorar avatar_job para vídeos por segmento**
- `_process_segment()` faz 1 WAV → 1 upload HeyGen → 1 vídeo
- HeyGen v3 suporta geração por clip — `POST /v3/videos` com áudio do segmento
- `video_editor_job` recebe lista de vídeos e concatena na ordem do manifesto
- Estimativa: 1 dia de trabalho

**1.2 — Criar slide_designer_agent**
- Input: `{beat, script, anchors[], pauta_titulo, serie}`
- Output: HTML completo de 1 slide com elementos animáveis
- Design baseado no pacote-finetuning-v2.html (fd1-fd4, b1-b4)
- Cada slide é gerado em paralelo para todos os segmentos do manifesto
- Estimativa: 1 dia

**1.3 — Corrigir python-plot via backend**
- code_executor já executa matplotlib
- Salvar PNG no GCS após execução
- Retornar URL ao invés de tentar renderizar no browser
- Estimativa: 2–3 horas

**1.4 — Validator contextual**
- Adicionar campo `tipo_artigo` na pauta: `tecnico` | `conceitual` | `estrategico`
- CMO determina o tipo na pauta JSON
- Validator aplica critérios diferentes por tipo
- Estimativa: 3–4 horas

---

### Fase 2 — UX e Produto (sessão seguinte)

**2.1 — Biblioteca de projetos**
- Nova rota `/api/csm/projects` — lista `csm_sessions` com draft.suggestedTitle e status
- Nova aba "Projetos" no dashboard
- Cards com: título, data, status do pipeline, preview de 2 linhas do artigo
- Botão "Continuar" carrega a sessão no dashboard
- Estimativa: 1 dia

**2.2 — Status de publicação em tempo real no Calendário**
- Webhook ou polling no Calendário para atualizar status dos items
- Notificação visual quando item passa de `planned` → `published`
- Badge de erro visível no card sem precisar abrir o popup
- Estimativa: 4–5 horas

**2.3 — Cores por projeto no Calendário**
- Usar `article_slug` como chave de cor
- Hash determinístico do slug → cor da paleta (6–8 cores distintas)
- Legenda de projetos no topo do calendário
- Filtro por projeto (dropdown)
- Estimativa: 3–4 horas

**2.4 — Tela de revisão antes de aprovar**
- Antes de "Aprovar Pacote", mostrar checklist editável:
  - Artigo: título, slug, leitura estimada → editáveis
  - LinkedIn post 1 e 2: hook editável inline
  - Cronograma sugerido: arraste para redistribuir
- Só então o botão "Confirmar e Publicar" aparece
- Estimativa: 1 dia

---

### Fase 3 — Escala e Qualidade (médio prazo)

**3.1 — Refatorar agent.py em microserviços**
- `cmo-editorial`: interview + generate + youtube (usa antigravity SDK)
- `cmo-specialist`: package + validate (usa vertex_generate.py direto)
- `cmo-distribution`: repurpose + build-manifest
- Cada serviço tem timeout e auto-scaling independentes
- Estimativa: 2 dias

**3.2 — Google Login + multi-usuário**
- Firebase Auth com Google OAuth
- Firestore com path tenanted: `users/{uid}/sessions/...`
- AuthGate substituído por signIn with Google
- Estimativa: 1–2 dias (sem assinatura), +2 dias (com Stripe)

**3.3 — Sistema de assinatura (Stripe)**
- Planos: Free (3 pacotes/mês), Pro (ilimitado + pipeline de vídeo), Team
- Webhook Stripe → atualiza `subscription_status` no Firestore
- Middleware Next.js verifica plano antes de renderizar o CSM
- Estimativa: 3–4 dias (requer conta jurídica Stripe Brasil)

**3.4 — Memória longa e continuidade editorial**
- Após publicar artigo, salvar embedding no Firestore (Vector Search)
- CMO usa busca semântica para evitar repetição de teses
- Research agent busca artigos anteriores como contexto
- Estimativa: 2 dias

**3.5 — Diversificação de hooks nos roteiros**
- Scriptwriter_agent: banco de 8 estratégias de hook (pergunta retórica, dado chocante, contrafactual, provocação, analogia, erro comum, resultado surpreendente, comparação)
- Cada vídeo usa uma estratégia diferente, documentada na pauta
- Estimativa: 4–6 horas

---

### Fase 4 — Automação completa (longo prazo)

**4.1 — Lifecycle de 60 dias (já implementado, validar)**
- Testar `lifecycle_job` com dados reais
- Verificar que `archived` assets aparecem corretamente no Calendário
- Adicionar opção de "desarquivar" se necessário

**4.2 — Agendamento automático inteligente**
- CMO sugere dia/hora baseado em dados de engajamento histórico
- LinkedIn: terças e quartas 10h–12h (pico B2B)
- Instagram: sextas 18h–20h e domingos 11h
- YouTube: quintas 18h
- Usuário pode aceitar ou ajustar

**4.3 — Métricas de performance dos posts**
- Após publicação, buscar dados de engajamento via API de cada plataforma
- Dashboard de analytics: impressões, cliques, conversões para blog
- Feedback loop: o CMO usa engajamento para propor próximas teses

---

## Dívidas técnicas a resolver

| Dívida | Impacto | Esforço |
|---|---|---|
| `avatar_job` gera vídeo único | Alto — sincronização errada | 1 dia |
| `slide_designer_agent` não existe | Alto — vídeos sem slides | 1 dia |
| `agent.py` com 1900 linhas | Médio — debug e escala | 2 dias |
| `python-plot` renderiza no browser | Médio — gráficos falham | 3h |
| Sem biblioteca de projetos | Alto — conteúdo "perdido" | 1 dia |
| `VERTEX_MODEL` hardcoded na imagem | Baixo — requer rebuild para mudar modelo | 2h |
| Warnings de `Field name "copy" shadows` | Baixo — logs sujos | 1h |
| `min-instances=1` no cmo-agent | Baixo — custo ~$15/mês desnecessário | 1h |
| `search_web` na ferramenta do CMO tenta DuckDuckGo e falha silenciosamente | Médio — CMO sem dados de mercado | 3h |

---

## Notas para a próxima sessão

**Começar por:** Fase 1.1 (avatar_job por segmento) + Fase 1.2 (slide_designer_agent). São os dois gaps que impedem que os vídeos gerados tenham qualidade real.

**Contexto que o agente deve ler antes de começar:**
- `/agents/pipeline/avatar_job/job.py` — entender o fluxo atual de concatenação
- `/agents/pipeline/shared/models.py` — contratos TtsCompletedMsg e AvatarCompletedMsg
- `/agents/cmo_agent/manifest_builder.py` — estrutura dos segmentos v2
- `/tool-videoyoutube/pacote-finetuning-v2.html` — referência visual dos slides

**Constraint de deploy:**
- O `VERTEX_MODEL=gemini-3.5-flash-lite` está hardcoded no `vertex_generate.py` como default
- Para testar novo modelo, basta alterar a env var `VERTEX_MODEL` no Cloud Run (sem rebuild)
- `gcloud run services update cmo-agent --update-env-vars=VERTEX_MODEL=gemini-3.6-flash`

**Estado das credenciais:**
- Vertex AI: ADC via service account — funciona
- HeyGen: secret `heygen-api-key` no Secret Manager
- ElevenLabs: secret `elevenlabs-api-key` no Secret Manager
- LinkedIn/Instagram/YouTube: secrets OAuth no Secret Manager
- `gemini-3.5-flash-lite` habilitado no projeto vazfy-417019 via endpoint global

---

*Última atualização: julho 2026 | Ambiente: GCP vazfy-417019 | Stack: Next.js 14 + Python FastAPI + Google Antigravity SDK + Vertex AI*
