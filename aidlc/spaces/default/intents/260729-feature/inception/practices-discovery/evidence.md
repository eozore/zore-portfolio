# Evidence

- vertex_generate.py: wrapper REST existente, usado por writing_agent, scriptwriter_agent, copy_agent, thumbnail_agent, distribution_agent
- distribution_agent.py: padrão ConfigDict(populate_by_name=True) + Field(alias=...) já em uso nas classes existentes
- shared/models.py: dataclasses Python puras para mensagens Pub/Sub
- agent.py: função async run_<agente> invocada no endpoint /package
