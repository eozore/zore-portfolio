# Component Dependency

```
BUG3:
  code_executor → google-cloud-storage (já no requirements.txt)
  RichArticleRenderer → nenhuma nova dep

BUG4:
  tools.search_web → tavily-python ou requests (já disponível)

BUG5:
  distribution_agent → nenhuma nova dep (só rename de campo)

BUG6:
  validator_agent → nenhuma nova dep
  prompts → nenhuma nova dep
  CsmDashboard → nenhuma nova dep (TypeScript)

BUG1:
  slide_designer_agent → vertex_generate (já existente)
  manifest_builder → slide_designer_agent (nova dep interna)
  agent.py → slide_designer_agent (nova dep interna)

BUG2:
  avatar_job → shared/models (AvatarCompletedMsg modificado)
  heygen_callback → shared/models (AvatarCompletedMsg modificado)
  video_editor_job → shared/models (AvatarCompletedMsg modificado)
  ATENÇÃO: shared/models é a dep central — deve ser atualizado antes dos outros 3
```
