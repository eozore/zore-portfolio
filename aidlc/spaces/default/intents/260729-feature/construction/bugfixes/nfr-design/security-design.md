# Security Design
- TAVILY_API_KEY: `os.environ.get("TAVILY_API_KEY")` — nunca logado
- GCS plots: `blob.make_public()` apenas para o blob do plot gerado
