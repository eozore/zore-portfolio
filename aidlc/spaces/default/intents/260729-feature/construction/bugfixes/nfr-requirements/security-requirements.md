# Security Requirements
- TAVILY_API_KEY: lida via os.environ, nunca hardcoded, adicionada no Secret Manager
- GCS plots: bucket com allUsers Storage Object Viewer APENAS para o prefixo plots/ (não todo o bucket)
- Sem novos endpoints públicos introduzidos
