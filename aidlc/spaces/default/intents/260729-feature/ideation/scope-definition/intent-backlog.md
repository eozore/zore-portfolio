# Intent Backlog

## Itens priorizados (ordem de execução)

| Prioridade | ID | Descrição | Esforço | Risco |
|---|---|---|---|---|
| 1 | BUG3 | Corrigir python-plot: code_executor retorna URL GCS; RichArticleRenderer remove InteractiveChart | S (2-3h) | Baixo |
| 2 | BUG4 | Substituir search_web() por Tavily API | S (2-3h) | Baixo |
| 3 | BUG5 | Renomear campo Pydantic `copy` → `post_copy` com alias | XS (1h) | Mínimo |
| 4 | BUG6 | Validator contextual por tipo_artigo | M (3-4h) | Baixo |
| 5 | BUG1 | Criar slide_designer_agent.py + integração | L (1 dia) | Médio |
| 6 | BUG2 | Refatorar avatar_job por segmento + contratos Pub/Sub | L (1 dia) | Médio-Alto |

## Backlog futuro (fora deste intent)

| Descrição | Motivação |
|---|---|
| Testes automatizados do pipeline de vídeo | Evitar regressões nos BUGs 1 e 2 no futuro |
| Dashboard de status do pipeline (Firestore → frontend) | Victor não tem visibilidade em tempo real do progresso |
| Suporte a múltiplas séries no CMO Agent | Hoje série é string livre; deveria ser enum validado |
