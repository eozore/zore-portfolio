# Scope Document — éozoré Content Studio Bugfixes

## In Scope

| ID | Item | Serviço |
|---|---|---|
| BUG3 | `code_executor.py`: retornar URL GCS como `![img](url)` no Markdown | `cmo-agent` |
| BUG3 | `RichArticleRenderer.tsx`: remover `InteractiveChart` component; renderizar imagens por `<img>` | `frontend` |
| BUG4 | `tools.py`: substituir `search_web()` por Tavily API | `cmo-agent` |
| BUG5 | `distribution_agent.py`: renomear campo `copy` → `post_copy` com `Field(alias="copy")` em 4 classes Pydantic | `cmo-agent` |
| BUG6 | `validator_agent.py`: critérios por tipo de artigo (tecnico/conceitual/estrategico) | `cmo-agent` |
| BUG6 | `prompts.py`: CMO inclui `tipo_artigo` no JSON da pauta | `cmo-agent` |
| BUG6 | `CsmDashboard.tsx`: campo `tipo_artigo` na interface `PautaConcebida` | `frontend` |
| BUG1 | Criar `slide_designer_agent.py`: gera HTML visual por segmento (8 beat types) | `cmo-agent` |
| BUG1 | `agent.py`: chamar `run_slide_designer()` no endpoint `/package` após `run_scriptwriter()` | `cmo-agent` |
| BUG1 | `manifest_builder.py`: `wrap_scriptwriter_manifest()` insere HTMLs reais dos slides | `cmo-agent` |
| BUG2 | `avatar_job/job.py`: processar segmentos individualmente (remover `_concatenate_audio()`) | `pipeline/avatar-job` |
| BUG2 | `shared/models.py`: `AvatarCompletedMsg.horizontal_video_path: str` → `horizontal_video_paths: list[str]` | `pipeline/shared` |
| BUG2 | `heygen_callback/app.py`: tracking por segmento; publicar `avatar-completed` quando todos N segmentos completarem | `pipeline/heygen-callback` |
| BUG2 | `video_editor_job/job.py`: receber lista de paths por segmento em `_compose_timeline()` | `pipeline/video-editor-job` |

## Out of Scope
- Novas features no chat CMO (novo modelo, novos campos na pauta além de `tipo_artigo`)
- Novos canais de distribuição (TikTok, Twitter/X)
- Refatoração de publisher_job ou tts_job (funcionam corretamente)
- UI/UX redesign do dashboard
- Testes automatizados end-to-end (fora do escopo desta iteração)

## Done / Definition of Done
- Cada bug tem PR com mudança mínima no(s) arquivo(s) afetado(s)
- Código não quebra a pipeline existente para projetos em curso
- BUG2: deploy coordenado dos 3 serviços no mesmo `gcloud builds submit`
