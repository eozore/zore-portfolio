# Components

## Novos Componentes

| ID | Nome | Tipo | Responsabilidade |
|---|---|---|---|
| C-NEW-1 | `slide_designer_agent` | Python module (cmo_agent) | Gera HTML visual completo para um segmento do manifesto, dado o beat type e o script |

## Componentes Modificados

| ID | Nome | Tipo | Modificação |
|---|---|---|---|
| C-MOD-1 | `code_executor` | Python module (cmo_agent) | `execute_python_plot()` salva PNG no GCS e retorna URL pública em vez de path local |
| C-MOD-2 | `tools` | Python module (cmo_agent) | `search_web()` substituída por Tavily API |
| C-MOD-3 | `distribution_agent` | Python module (cmo_agent) | 4 classes Pydantic: `copy` → `post_copy` com alias |
| C-MOD-4 | `validator_agent` | Python module (cmo_agent) | `_check_article_deterministic()` lê `tipo_artigo` e aplica critérios condicionais |
| C-MOD-5 | `prompts` | Python module (cmo_agent) | JSON da pauta inclui campo `tipo_artigo` |
| C-MOD-6 | `manifest_builder` | Python module (cmo_agent) | `wrap_scriptwriter_manifest()` insere HTML real dos slides em vez de placeholders |
| C-MOD-7 | `agent` | Python module (cmo_agent) | Endpoint `/package` chama `run_slide_designer()` após `run_scriptwriter()` |
| C-MOD-8 | `AvatarJob` | Python class (pipeline/avatar_job) | Remove `_concatenate_audio()`; processa segmentos individualmente |
| C-MOD-9 | `AvatarCompletedMsg` | Python dataclass (pipeline/shared) | `*_video_path: str` → `*_video_paths: list[str]` + `segment_ids: list[str]` |
| C-MOD-10 | `heygen_callback app` | Python FastAPI (pipeline) | Tracking por segmento; publica `AvatarCompletedMsg` quando todos N segmentos concluem |
| C-MOD-11 | `VideoEditorJob` | Python class (pipeline/video_editor_job) | `_compose_timeline()` recebe `segment_video_paths: dict` em vez de `avatar_path: str` |
| C-MOD-12 | `RichArticleRenderer` | TSX component (frontend) | Remove `InteractiveChart`; garante render de `<img>` para URLs GCS |
| C-MOD-13 | `CsmDashboard` | TSX component (frontend) | Interface `PautaConcebida` + `tipo_artigo` field; badge na UI |
