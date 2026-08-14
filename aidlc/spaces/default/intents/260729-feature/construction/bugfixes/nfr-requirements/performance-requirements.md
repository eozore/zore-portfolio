# Performance Requirements
- BUG1 (slide_designer): latência /package não deve aumentar mais de 20s (parallelizar chamadas por segmento)
- BUG3 (plots): upload GCS síncrono no request — timeout 10s por imagem
- BUG4 (Tavily): timeout 8s (mesmo do DuckDuckGo atual)
- BUG2 (avatar per seg): N chamadas HeyGen sequenciais — delay 500ms entre chamadas para evitar rate limit
