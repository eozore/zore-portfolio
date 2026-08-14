# External Dependency Map

| Dependência | Bug | Ação necessária antes do deploy |
|---|---|---|
| Tavily API key | BUG4 | Criar conta em tavily.com, obter API key, adicionar no Secret Manager GCP |
| GCS bucket cmo-agent | BUG3 | Confirmar variável `GCS_BUCKET` no env do cmo-agent Cloud Run |
