# Design Decisions

| ID | Decisão | Impacto |
|---|---|---|
| AD-1 | `slide_designer_agent` usa `vertex_generate.py` (não antigravity SDK) | Consistência com os demais agentes recentes |
| AD-2 | `post_process_article_plots()` recebe `gcs_bucket` como parâmetro (não env var hard-coded) | Testabilidade e flexibilidade |
| AD-3 | Tavily via `requests` puro (não biblioteca `tavily-python`) | Evita dep extra; a API é um POST simples |
| AD-4 | `tipo_artigo` é `Optional` com default `"tecnico"` em todos os lugares | Compatibilidade retroativa com sessões existentes |
| AD-5 | BUG2: `segment_ids` na lista de vídeos usa o basename do audio path (ex: `yt-01`) | Consistência com o manifesto; evita re-mapeamento |
