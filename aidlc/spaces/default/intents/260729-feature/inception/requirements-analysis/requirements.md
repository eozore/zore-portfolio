# Requirements — éozoré Content Studio Bugfixes

## Functional Requirements

### FR-BUG3: Python Plot Rendering
- **FR3.1** `code_executor.execute_python_plot()` deve salvar o PNG no GCS bucket (`vazfy-417019-pipeline-media` ou bucket do cmo-agent) e retornar a URL pública `https://storage.googleapis.com/<bucket>/plots/<uuid>.png`
- **FR3.2** `post_process_article_plots()` deve substituir o bloco `python-plot` por `![alt](url_gcs)` no Markdown final
- **FR3.3** `RichArticleRenderer.tsx` deve remover o componente `InteractiveChart` e renderizar imagens GCS como `<img>` padrão via o handler de imagens existente
- **FR3.4** O artigo renderizado não deve ter mais erros silenciosos de parse Python

### FR-BUG4: Tavily Web Search
- **FR4.1** `search_web(query, max_results)` deve chamar `POST https://api.tavily.com/search` com `{"api_key": TAVILY_API_KEY, "query": query, "search_depth": "basic", "max_results": max_results}`
- **FR4.2** Retornar os resultados no mesmo formato de string que o atual (compatibilidade com o CMO Agent que consome a ferramenta)
- **FR4.3** Se `TAVILY_API_KEY` não estiver definida, logar warning e retornar string de erro (não crash)
- **FR4.4** Adicionar `tavily-python>=0.3.0` (ou `requests` puro) no requirements.txt do cmo_agent

### FR-BUG5: Pydantic Field Naming
- **FR5.1** Nas 4 classes de `distribution_agent.py` que têm `copy: str = Field(alias="copy")`: renomear o campo Python para `post_copy`
- **FR5.2** Manter `Field(alias="copy")` para que o JSON de entrada/saída continue usando a chave `"copy"`
- **FR5.3** Zero warnings `Field name "copy" shadows an attribute` no startup

### FR-BUG6: Contextual Validator
- **FR6.1** Adicionar campo `tipo_artigo: Literal["tecnico", "conceitual", "estrategico"]` na `PautaConcebida` (TypeScript) e na validação do CMO Agent
- **FR6.2** O prompt do CMO (prompts.py) deve incluir `tipo_artigo` no bloco JSON da pauta
- **FR6.3** `_check_article_deterministic()` em `validator_agent.py` deve:
  - Para `tipo_artigo == "tecnico"`: manter todos os blockers atuais (código, mermaid, LaTeX)
  - Para `tipo_artigo == "conceitual"`: remover blocker B1 (código Python), manter B2 e B3
  - Para `tipo_artigo == "estrategico"`: remover blockers B1 e B2 (código e mermaid), manter apenas B3 (LaTeX) e extensão

### FR-BUG1: Slide Designer Agent
- **FR1.1** Criar `agents/cmo_agent/slide_designer_agent.py` com função `run_slide_designer(segment: dict, pauta: dict, target: str) -> str` que retorna HTML completo (string)
- **FR1.2** O agente deve suportar os 8 beat types: `hook`, `intro`, `teoria`, `codigo`, `demo`, `comparativo`, `consideracoes`, `resumo`
- **FR1.3** Para `target="horizontal"`: dimensões 1920×1080. Para `target="vertical"`: 1080×1920
- **FR1.4** Design system: background `#0d0f14`, Space Grotesk + JetBrains Mono via Google Fonts CDN, logo éozoré no canto inferior direito, grid sutil laranja
- **FR1.5** Elementos `fd1` (visível por padrão), `fd2, fd3, fd4` com `display:none` (revelados por âncoras)
- **FR1.6** Animação CSS: `@keyframes fadeIn { from { opacity: 0; transform: translateY(8px) } to { opacity: 1; transform: translateY(0) } }`
- **FR1.7** `agent.py` endpoint `/package`: após `run_scriptwriter()`, para cada segmento com `slide != null`, chamar `run_slide_designer(segment, pauta)`
- **FR1.8** `manifest_builder.py` `wrap_scriptwriter_manifest()`: substituir `<section class="slide" id="...">` placeholder pelo HTML real do slide_designer

### FR-BUG2: Avatar Job Per Segment
- **FR2.1** `avatar_job/job.py`: remover `_concatenate_audio()`. Para cada `seg_path` em `msg.audio_paths[target]`, fazer upload individual para HeyGen Assets e gerar vídeo individual
- **FR2.2** Salvar no Firestore a lista `segment_videos.{target}[i] = {seg_id, video_id, status, video_url}` para cada segmento
- **FR2.3** `shared/models.py` `AvatarCompletedMsg`: mudar `horizontal_video_path: str` → `horizontal_video_paths: list[str]` e `vertical_video_path: str` → `vertical_video_paths: list[str]`. Adicionar `segment_ids: list[str]`
- **FR2.4** `heygen_callback/app.py`: ao receber callback de um `video_id`, resolver o `seg_id` via Firestore. Quando todos os segmentos de um target tiverem `status: "completed"`, montar listas e publicar `AvatarCompletedMsg`
- **FR2.5** `video_editor_job/job.py` `_compose_timeline()`: receber `segment_video_paths: dict[str, str]` (mapa de seg_id → local path) em vez de `avatar_path: str` único. Para cada segmento com `script != ""`, usar o path correspondente

## Non-Functional Requirements
- **NFR1** Nenhum bugfix deve aumentar o tempo médio de resposta do `/generate` em mais de 5s
- **NFR2** BUG2 exige deploy coordenado — os 3 serviços devem estar na mesma versão simultaneamente
- **NFR3** Nenhuma nova dependência externa além de `tavily-python` (BUG4) é introduzida
- **NFR4** Compatibilidade retroativa: campos `tipo_artigo` e `post_copy` são opcionais com fallback
