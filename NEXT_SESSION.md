# éozoré Content Studio — Handoff para Próxima Sessão

**Objetivo:** Finalizar a ferramenta de ponta a ponta.
**Agente:** Leia este documento completo antes de qualquer código. Depois leia os arquivos listados em cada seção. Só então implemente.

---

## Contexto do projeto

Plataforma de criação de conteúdo técnico automatizada em `eozore.com/admin/csm`.
Stack: Next.js 14 (apps/web) + Python FastAPI (agents/cmo_agent) + GCP vazfy-417019.

**Senha de acesso:** `Zore@victor94`

**URLs em produção:**
- Frontend: `https://frontend-4zffe4l4lq-uc.a.run.app` / `https://eozore.com/admin/csm`
- CMO Agent: `https://cmo-agent-4zffe4l4lq-uc.a.run.app`
- HeyGen Callback: `https://heygen-callback-4zffe4l4lq-uc.a.run.app`

**Deploy:** `gcloud builds submit --config=cloudbuild.yaml --project=vazfy-417019 --substitutions=COMMIT_SHA=<tag>`
**CMO Agent rebuild:** mesmo comando — o `cloudbuild.yaml` rebuilda cmo-agent + frontend em sequência.

---

## O que está funcionando hoje

1. Chat CMO → pauta com 8 campos validados (titulo, subtitulo, tese, publico, objetivo_aprendizado, hardskills[], duracao_alvo, serie)
2. Geração de artigo: Critic → Research → Writing → Validator (com regeneração automática em 2 tentativas)
3. Artigo renderizado: LaTeX via KaTeX, Mermaid, syntax highlighting, tabelas GFM
4. Roteiro segmentado (scriptwriter_agent) + thumbnails (thumbnail_agent) + copies LinkedIn/Threads (copy_agent)
5. Derivações omnicanal: Reels, Shorts, Carrosséis, Stories (distribution_agent)
6. Calendário editorial com popup de edição (copy, hashtags, data/hora)
7. Publicação agendada via `social_queue` (status=planned) + publisher-scheduled horário
8. Pipeline de vídeo: TTS (ElevenLabs) → HeyGen → VideoEditor → Publisher (funciona mas com bugs abaixo)

---

## O que NÃO funciona — lista completa com causa-raiz

### BUG 1 — CRÍTICO: Vídeos sem slides (telas pretas)
**Causa:** `slide_designer_agent` não existe. O `wrap_scriptwriter_manifest()` gera placeholders HTML:
```html
<section class="slide" id="yt-02" data-seg="yt-02">
  <div class="slide-id">yt-02</div>
</section>
```
O VideoEditorJob renderiza via Playwright → tela preta com só o texto "// yt-02".

**Arquivo:** `agents/cmo_agent/manifest_builder.py`, função `wrap_scriptwriter_manifest()` — linhas finais onde os `<section class="slide">` são gerados.

**Solução:** Criar `agents/cmo_agent/slide_designer_agent.py` que recebe cada segmento e gera HTML visual real. Ver seção IMPLEMENTAÇÃO NECESSÁRIA abaixo.

---

### BUG 2 — CRÍTICO: Avatar Job concatena tudo num único vídeo
**Causa:** `agents/pipeline/avatar_job/job.py` — `_concatenate_audio()` junta todos os WAVs de um target em 1 MP3, faz 1 chamada HeyGen, gera 1 vídeo. O VideoEditor tenta fatiar esse vídeo por `min_duration_s` estimado → dessincronizado.

**Arquitetura correta:**
```
Por segmento com script != "":
  WAV individual → 1 upload HeyGen Assets → 1 POST /v3/videos → 1 vídeo curto
VideoEditorJob recebe lista de [video_horizontal_seg_001.mp4, ...] e concatena
```

**Impacto:** Todos os vídeos gerados hoje têm timing incorreto entre fala e slides.

**Arquivos a ler antes de implementar:**
- `agents/pipeline/avatar_job/job.py` — classe `AvatarJob` completa
- `agents/pipeline/shared/models.py` — `TtsCompletedMsg`, `AvatarCompletedMsg`
- `agents/pipeline/tts_job/job.py` — como audio_paths é estruturado por segmento

**Nota:** `TtsCompletedMsg.audio_paths` já é `{"horizontal": ["gs://.../seg_001.mp3", "gs://.../seg_002.mp3", ...], "vertical": [...]}` — os caminhos já são individuais por segmento. O avatar_job só precisa parar de concatenar e processar individualmente.

**O que muda no `AvatarCompletedMsg`:** atualmente tem `horizontal_video_path: str` (1 vídeo). Precisará virar `horizontal_video_paths: list[str]` (N vídeos). Isso afeta `heygen_callback/app.py` e `video_editor_job/job.py`.

---

### BUG 3 — IMPORTANTE: Gráficos python-plot falham silenciosamente
**Causa:** O `RichArticleRenderer.tsx` tenta parsear código Python com regex JavaScript para renderizar gráficos interativos. Qualquer variação de sintaxe no código gerado quebra o parser.

**Causa real:** O `code_executor.py` já executa matplotlib e salva imagens, mas o resultado não chega ao frontend de forma confiável.

**Arquivo:** `agents/cmo_agent/code_executor.py` — verificar o que retorna e como o artigo inclui as imagens geradas.

**Solução simples:** o `code_executor` deve salvar o PNG no GCS e retornar a URL no Markdown como `![grafico](https://storage.googleapis.com/...)`. O `RichArticleRenderer` renderiza como `<img>` via seu handler de imagens já existente. Remove o `InteractiveChart` component do renderer (era uma gambiarra).

---

### BUG 4 — IMPORTANTE: search_web do CMO falha silenciosamente
**Causa:** `agents/cmo_agent/tools.py` — `search_web()` usa scraping de HTML do DuckDuckGo. Falha com frequência por rate limit ou mudança de layout.

**Solução:** Substituir pela [SerpAPI](https://serpapi.com/) ou [Tavily API](https://tavily.com/) — ambas têm planos gratuitos generosos. Tavily é a mais usada em agentes de IA.

**Implementação:** Adicionar `TAVILY_API_KEY` no Secret Manager + atualizar `search_web()` para `requests.post("https://api.tavily.com/search", ...)`.

---

### BUG 5 — MENOR: Warnings no startup do CMO Agent
**Causa:** `Field name "copy" in "LinkedInPost" shadows an attribute in parent "BaseModel"` — Pydantic v2 não gosta do campo chamado `copy`.

**Solução:** Renomear o campo Pydantic para `post_copy` e usar `alias="copy"` já existente no modelo. Afeta `distribution_agent.py` (4 classes).

---

### BUG 6 — MENOR: Validator pode reprovar artigos conceituais injustamente
**Causa:** `validator_agent.py` — blockers incluem "ausência de código Python", mas artigos sobre estratégia/liderança não precisam de código.

**Solução:** O campo `tese` da pauta já indica o ângulo. Adicionar campo `tipo_artigo: "tecnico" | "conceitual" | "estrategico"` na `PautaConcebida`. O validator lê esse campo e aplica critérios diferentes.

**Arquivos:** `agents/cmo_agent/validator_agent.py`, `apps/web/src/components/csm/CsmDashboard.tsx` (interface PautaConcebida), `agents/cmo_agent/prompts.py` (CMO deve incluir o campo no JSON).

---

## Implementação necessária: slide_designer_agent

Este é o item de maior impacto. Leia `tool-videoyoutube/pacote-finetuning-v2.html` antes de implementar.

### O que o agente recebe (input por segmento):
```python
{
  "segment_id": "yt-02",
  "beat": "teoria",           # define o tipo visual
  "script": "O LoRA resolve isso decompondo...",  # texto falado
  "anchors": [
    {"on_phrase": "decompondo", "action": "show_slide"},
    {"on_phrase": "duas menores", "action": "reveal", "element": "fd2"},
    {"on_phrase": "baixo rank", "action": "reveal", "element": "fd3"}
  ],
  "pauta_titulo": "LoRA: Fine-Tuning Eficiente",
  "serie": "ia-para-lideres"
}
```

### O que o agente deve gerar (output: HTML completo de 1 slide):
- Dimensões: 1920×1080 (YouTube) ou 1080×1920 (Reels)
- Background: `#0d0f14` com grid sutil laranja
- Elementos com IDs `fd1, fd2, fd3, fd4` (fadeIn) e `b1, b2, b3, b4` (barras)
- `fd1` visível por padrão, `fd2, fd3, fd4` com `display:none` (revelados pelas âncoras)
- Animação CSS: `@keyframes fadeIn { from { opacity: 0; transform: translateY(8px) } to { opacity: 1; transform: translateY(0) } }`
- Fonte: Space Grotesk (display) + JetBrains Mono (mono) via Google Fonts
- Logo éozoré no canto inferior direito

### Tipos visuais por beat:
- `hook`: título grande + número de contraste (ex: "1% dos parâmetros")
- `intro`: problema (lado esquerdo) + solução (lado direito), seta conectando
- `teoria`: equação central estilizada + decomposição visual (matrizes)
- `codigo`: frame estilo terminal/editor com código fragmentado
- `demo`: barras de gráfico comparativo (usa `b1, b2, b3, b4`)
- `comparativo`: tabela de 2 colunas antes/depois
- `consideracoes`: checklist de bullets com ícones
- `resumo`: 3 pontos numerados grandes + CTA

### Onde integrar:
1. Criar `agents/cmo_agent/slide_designer_agent.py`
2. Chamar no `agent.py` no endpoint `/package` — após `run_scriptwriter()`, para cada segmento com `slide != null`, chamar `run_slide_designer(segment, pauta)`
3. Os HTMLs dos slides devem ser inseridos no `manifestHtml` gerado por `wrap_scriptwriter_manifest()` — substituindo os `<section class="slide">` placeholder pelos HTMLs reais

---

## Implementação necessária: avatar_job por segmento

### Arquitetura nova:

```python
# TtsCompletedMsg já tem:
# audio_paths = {"horizontal": ["gs://.../yt-01.mp3", "gs://.../yt-03.mp3", ...]}
# (só segmentos com script != "", na ordem do manifesto)

# Nova lógica do AvatarJob:
for target in ("horizontal", "vertical"):
    segment_paths = msg.audio_paths[target]  # lista de paths individuais
    segment_videos = []
    
    for seg_path in segment_paths:
        seg_id = os.path.basename(seg_path).replace(".mp3", "")
        
        # 1 upload por segmento
        audio_asset_id = await _upload_to_heygen_assets(seg_path)
        
        # 1 vídeo por segmento
        video_id = await _generate_avatar_video(audio_asset_id, avatar_id, target, project_id)
        
        segment_videos.append({
            "seg_id": seg_id,
            "video_id": video_id,
            "status": "pending",
            "video_url": None
        })
    
    # Salva lista de video_ids no Firestore
    await firestore.update_stage(project_id, "avatar", {
        f"segment_videos.{target}": segment_videos
    })
```

### Mudanças no `AvatarCompletedMsg`:
```python
@dataclass
class AvatarCompletedMsg:
    project_id: str
    # ANTES: horizontal_video_path: str
    # DEPOIS:
    horizontal_video_paths: list[str]  # ["gs://.../yt-01.mp4", "gs://.../yt-03.mp4", ...]
    vertical_video_paths: list[str]
    segment_ids: list[str]             # ["yt-01", "yt-03", ...] (mesma ordem)
    duration_seconds: float
    total_cost_usd: float
```

### Mudanças no `heygen_callback/app.py`:
O callback hoje recebe o video_id de um único vídeo e dispara `avatar-completed`. Com a nova arquitetura, precisa:
1. Receber cada callback individualmente
2. Salvar URL do vídeo para o `seg_id` correspondente no Firestore
3. Quando TODOS os segmentos de um projeto tiverem `status: "completed"`, montar a lista `horizontal_video_paths` e publicar `avatar-completed`

### Mudanças no `video_editor_job/job.py`:
O `_compose_timeline()` hoje recebe um único `avatar_path`. Precisará receber a lista `segment_videos` e usar cada vídeo no slot correto do manifesto.

---

## Estrutura de arquivos relevantes

```
agents/
  cmo_agent/
    agent.py                    # 1900 linhas — orquestrador FastAPI
    writing_agent.py            # Writing + YouTube script (usa vertex_generate)
    scriptwriter_agent.py       # Manifesto v2 com anchors[] (usa vertex_generate)
    copy_agent.py               # LinkedIn + Threads (usa vertex_generate)
    thumbnail_agent.py          # 2 thumbnails HTML (usa vertex_generate)
    distribution_agent.py       # Reels/Shorts/Carrosséis/Stories (usa vertex_generate)
    validator_agent.py          # Valida artigo e pacote (usa vertex_generate)
    vertex_generate.py          # Wrapper REST Vertex AI — TODOS os agentes usam este
    manifest_builder.py         # Gera HTML do manifesto v2 (slides são placeholders aqui)
    prompts.py                  # System instruction do CMO chat
    model_config.py             # Config antigravity SDK (só para chat/critic/research)
    tools.py                    # search_web, fetch_trending_papers, get_ecosystem_memory
    critic_agent.py             # Steering editorial (usa antigravity SDK)
    research_agent.py           # Pesquisa arXiv + web (usa antigravity SDK)
    code_executor.py            # Executa python-plot e gera imagens
    
  pipeline/
    avatar_job/job.py           # BUG: concatena tudo — precisa refatorar
    tts_job/job.py              # Correto: já gera WAV por segmento
    video_editor_job/job.py     # Playwright + FFmpeg compose
    heygen_callback/app.py      # Webhook do HeyGen
    publisher_job/job.py        # Publica nas plataformas
    shared/models.py            # Contratos de mensagem Pub/Sub
    infra/setup_jobs.sh         # Provisiona Cloud Run Jobs

apps/web/src/
  components/csm/
    CsmDashboard.tsx            # Estado global, navegação, tipos TypeScript
    RichArticleRenderer.tsx     # Renderiza Markdown com LaTeX/Mermaid/código
    tabs/
      IdeaTab.tsx               # Chat CMO
      PackageTab.tsx            # Pacote com scroll único
      GenerateTab.tsx           # Editor split view
      CalendarTab.tsx           # Calendário semanal
      PublishTab.tsx            # Publicação no blog
      RepurposeTab.tsx          # Derivações (aba legada)
  app/api/csm/
    interview/route.ts          # Proxy CMO chat → cmo-agent /interview
    generate/route.ts           # SSE artigo → cmo-agent /generate
    package/route.ts            # Orchestrates generate + repurpose + specialists
    approve-package/route.ts    # Blog + enqueue texto + dispara pipeline vídeo
    pipeline-submit/route.ts    # Firestore + Pub/Sub para pipeline
    calendar/route.ts           # GET/PUT calendário
    calendar/retry/route.ts     # Retry de items com falha
    schedule/route.ts           # Salva items na social_queue

tool-videoyoutube/
  pacote-finetuning-v2.html     # REFERÊNCIA VISUAL dos slides — ler antes de slide_designer
```

---

## Variáveis de ambiente críticas

```bash
# Cloud Run: cmo-agent
FIREBASE_PROJECT_ID=vazfy-417019       # via Secret Manager
VERTEX_MODEL=gemini-3.5-flash-lite     # trocar para gemini-3.6-flash quando disponível
                                        # gcloud run services update cmo-agent \
                                        #   --update-env-vars=VERTEX_MODEL=gemini-3.6-flash

# Cloud Run: frontend  
CMO_AGENT_URL=https://cmo-agent-4zffe4l4lq-uc.a.run.app  # auto-detectado no deploy
CSM_PASSWORD_HASH=<hash SHA256 de "Zore@victor94">         # via Secret Manager

# Cloud Run Jobs: pipeline
GCS_BUCKET=vazfy-417019-pipeline-media
HEYGEN_CALLBACK_URL=https://heygen-callback-4zffe4l4lq-uc.a.run.app
HEYGEN_AVATAR_ID_HORIZONTAL=32e2ad6b3e5a45bf8c61cbf7220912f4
HEYGEN_AVATAR_ID_VERTICAL=d7fdce2942a244649820a0b5c989766f
```

---

## Ordem de execução recomendada

1. **Leia os arquivos** listados nas seções de BUG antes de qualquer código
2. **BUG 3** (python-plot) — mais simples, 2–3 horas, impacto visual imediato
3. **BUG 4** (search_web) — 2–3 horas, melhora qualidade do CMO
4. **BUG 5** (Pydantic warnings) — 1 hora, limpa os logs
5. **BUG 6** (validator contextual) — 3–4 horas
6. **BUG 1** (slide_designer_agent) — 1 dia, maior impacto visual
7. **BUG 2** (avatar_job por segmento) — 1 dia, maior impacto técnico, fazer por último pois muda contratos Pub/Sub

**Não começar pelo BUG 2 (avatar_job)** sem ter feito os outros — ele muda `AvatarCompletedMsg` que afeta 3 serviços simultaneamente.

---

## Comandos úteis para debug

```bash
# Ver logs recentes do cmo-agent
gcloud logging read 'resource.labels.service_name="cmo-agent" AND textPayload!=""' \
  --project=vazfy-417019 --limit=50 --freshness=2h \
  --format='value(timestamp,textPayload)' 2>/dev/null | \
  grep -v "UserWarning\|class \|Uvicorn\|startup\|Application\|Default STARTUP\|Starting new\|Field name"

# Testar cmo-agent diretamente
CMO="https://cmo-agent-4zffe4l4lq-uc.a.run.app"
curl -s "$CMO/health"
curl -s -X POST "$CMO/package" -H "Content-Type: application/json" \
  -d '{"pauta":{"titulo":"Teste","subtitulo":"","tese":"A","publico":"líderes","objetivo_aprendizado":"ok","hardskills":["x"],"duracao_alvo":"5 min","serie":"ia"},"articleContent":"Conteúdo aqui.","category":"ml","language":"pt-BR"}' \
  --max-time 60 | python3 -c "import sys,json; d=json.load(sys.stdin); print('Keys:', list(d.keys()))"

# Rebuild e deploy completo
cd /Users/victorzore/Desktop/zore-portfolio
gcloud builds submit --config=cloudbuild.yaml --project=vazfy-417019 --substitutions=COMMIT_SHA=<tag>

# Trocar modelo sem rebuild (instante)
gcloud run services update cmo-agent --region=us-central1 --project=vazfy-417019 \
  --update-env-vars=VERTEX_MODEL=gemini-3.6-flash
```

---

## Estrutura de dados Firestore (referência)

```
csm_sessions/{sessionId}
  draft: { ...DraftState }   # salvo a cada 30s pelo frontend

social_queue/{itemId}
  platform, format, title, copy, hashtags
  scheduled_at, status (planned|published|failed)
  article_slug, session_id
  retry_count, error_message, published_at

content_projects/{projectId}
  project_id, title, manifest_url
  article_slug, session_id
  status (generating_media|awaiting_publication|published|archived)
  stages: { tts: {status}, avatar: {status, lipsync_jobs}, editor: {status}, publisher: {status} }
```

---

*Documento gerado em: julho 2026*
*Projeto: éozoré / vazfy-417019*
*Repositório: /Users/victorzore/Desktop/zore-portfolio*
