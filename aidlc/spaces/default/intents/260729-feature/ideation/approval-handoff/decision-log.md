# Decision Log

| ID | Decisão | Alternativas consideradas | Rationale |
|---|---|---|---|
| D1 | Tavily API para BUG4 | SerpAPI, Bing API, DuckDuckGo (atual) | Gratuita para o volume, feita para AI agents, integração mínima |
| D2 | slide_designer_agent usa Gemini via Vertex AI para gerar HTML | Templates estáticos pré-definidos | LLM adapta o conteúdo visual ao contexto do segmento; templates estáticos são rígidos |
| D3 | `post_copy` com `Field(alias="copy")` para BUG5 | Remover campo copy | Compatibilidade retroativa com JSON já armazenado no Firestore |
| D4 | `tipo_artigo` opcional com fallback `"tecnico"` para BUG6 | Campo obrigatório | Sessões antigas sem o campo não quebram; fallback é o comportamento atual |
| D5 | Deploy coordenado de 3 serviços para BUG2 | Deploy rolling independente | Breaking change em AvatarCompletedMsg: consumer e producer devem estar na mesma versão |
| D6 | `_concatenate_audio()` removida em BUG2, não apenas desabilitada | Manter com flag feature | Código morto é pior que código removido; a concatenação é a causa-raiz do bug |
