# Security Test Instructions
- TAVILY_API_KEY: confirmar que não aparece nos logs do Cloud Run
- GCS plots: confirmar que apenas o prefixo plots/ está público (não o bucket inteiro)
- AvatarCompletedMsg: sem dados sensíveis no payload Pub/Sub
