# Market Trends

Não aplicável como análise de mercado externo.

## Tendências técnicas relevantes para as decisões de implementação

1. **AI Agents + Search:** Tavily, Exa, Perplexity API são o padrão emergente para search em agentes autônomos. DuckDuckGo scraping está obsoleto nesse contexto.
2. **Vídeo por segmento (BUG2):** HeyGen e similares (Synthesia, D-ID) favorecem geração por cena curta (<60s) em vez de vídeos longos — menor custo, melhor sync, retry granular.
3. **HTML-to-video (BUG1):** Padrão Playwright+FFmpeg para renderizar slides HTML é estável e adotado (Remotion, Motion Canvas usam abordagens similares). O slide_designer_agent deve gerar HTML autossuficiente (CSS inline, sem dependências externas além de Google Fonts CDN).
