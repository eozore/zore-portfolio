# Constraint Register

| ID | Tipo | Descrição | Impacto | Mitigação |
|---|---|---|---|---|
| C1 | Técnico | Stack imutável: Next.js 14 + Python FastAPI + GCP | Nenhum — todos os bugfixes respeitam a stack | — |
| C2 | Técnico | Todos os LLMs via Vertex AI (Gemini) | slide_designer_agent usa `vertex_generate.py` existente | Reutilizar wrapper REST existente |
| C3 | Infraestrutura | TAVILY_API_KEY deve estar no Secret Manager antes do deploy do BUG4 | BUG4 não pode ser deployado sem a chave | Victor criar conta Tavily antes do deploy |
| C4 | Deploy | BUG2 é breaking change em AvatarCompletedMsg — deploy coordenado obrigatório | Se deployado isoladamente, quebra a pipeline em produção | Deploy simultâneo via cloudbuild.yaml com todos os 3 serviços |
| C5 | Custo | HeyGen cobra por segundo de vídeo (não por chamada) | BUG2 não aumenta custo monetário | — |
| C6 | Tempo | slide_designer_agent gera HTML via LLM — latência +10-15s no /package | UX degradada levemente | Aceitável; /package já é slow (~30-60s) |
