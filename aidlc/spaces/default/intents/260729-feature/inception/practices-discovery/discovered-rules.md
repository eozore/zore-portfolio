# Discovered Rules

1. vertex_generate.py é o wrapper universal para todos os LLMs — todos os novos agentes devem usá-lo
2. Novos agentes Python exportam uma função `run_<nome>(params...) -> dict` assíncrona
3. Todos os modelos Pydantic usam `ConfigDict(populate_by_name=True)` quando há aliases
4. Campos JSON de saída dos agentes devem ter fallback para dict vazio se o LLM falhar
5. requirements.txt do cmo_agent usa ranges (>=), pipeline usa versões fixas (==)
6. Mensagens Pub/Sub são dataclasses Python simples (não Pydantic)
