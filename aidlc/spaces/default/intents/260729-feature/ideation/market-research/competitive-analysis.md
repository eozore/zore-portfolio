# Competitive Analysis

Não aplicável como análise externa — o Content Studio é ferramenta interna proprietária.

## Referências técnicas relevantes para os bugfixes

### Padrão de slide HTML para vídeo (BUG1)
- **Revealjs + Playwright** é o padrão da indústria para renderizar slides HTML em vídeo. O projeto já usa esse padrão (Playwright + FFmpeg).
- Visual reference: `tool-videoyoutube/pacote-finetuning-v2.html` — define o design system que o slide_designer_agent deve replicar.

### Tavily para agentes de IA (BUG4)
- Tavily é a search API mais usada em frameworks de IA agents (LangChain, CrewAI, AutoGen). Projetada para retornar contexto limpo, sem HTML.
- Endpoint: `POST https://api.tavily.com/search` com `{"query": "...", "search_depth": "basic", "max_results": 5}`.

### Pydantic v2 field naming (BUG5)
- Pydantic v2 reserva `copy`, `dict`, `json`, `schema` como nomes de método. Usar `model_copy`, `model_dump`, etc. O alias `copy` ainda pode ser exposto via `Field(alias="copy")`.
