# Code Generation Plan

## Arquivos implementados

| Bug | Arquivo | Tipo de mudança |
|---|---|---|
| BUG3 | `agents/cmo_agent/code_executor.py` | Reescrita: salva PNG no GCS, retorna URL pública |
| BUG3 | `apps/web/src/components/csm/RichArticleRenderer.tsx` | Remove InteractiveChart, adiciona handler img |
| BUG3 | `agents/cmo_agent/agent.py` | Passa gcs_bucket para post_process_article_plots |
| BUG4 | `agents/cmo_agent/tools.py` | search_web() substituída por Tavily API |
| BUG5 | `agents/cmo_agent/distribution_agent.py` | 4 campos copy → post_copy com Field(alias) |
| BUG6 | `agents/cmo_agent/validator_agent.py` | Critérios condicionais por tipo_artigo |
| BUG6 | `agents/cmo_agent/prompts.py` | JSON pauta com tipo_artigo (9 campos) |
| BUG6 | `apps/web/src/components/csm/CsmDashboard.tsx` | Interface PautaConcebida + tipo_artigo |
| BUG6 | `apps/web/src/components/csm/tabs/IdeaTab.tsx` | Parse tipo_artigo + badge colorido |
| BUG6 | `agents/cmo_agent/agent.py` | Extrai tipo_artigo do contexto para validator |
| BUG1 | `agents/cmo_agent/slide_designer_agent.py` | NOVO: 8 beat types, asyncio.Semaphore(3) |
| BUG1 | `agents/cmo_agent/manifest_builder.py` | wrap_scriptwriter_manifest aceita slide_htmls |
| BUG1 | `agents/cmo_agent/agent.py` | Chama design_all_slides antes do wrap |
| BUG2 | `agents/pipeline/shared/models.py` | AvatarCompletedMsg: str→list, segment_ids |
| BUG2 | `agents/pipeline/avatar_job/job.py` | Remove _concatenate_audio, loop por segmento |
| BUG2 | `agents/pipeline/heygen_callback/app.py` | _process_segment_result, tracking granular |
| BUG2 | `agents/pipeline/video_editor_job/job.py` | segment_video_paths dict em vez de avatar_path |

## Verificação
- Python: 12/12 arquivos sem erros de sintaxe (ast.parse)
- TypeScript: tsc --noEmit sem erros
