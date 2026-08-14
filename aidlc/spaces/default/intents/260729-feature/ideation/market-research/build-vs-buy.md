# Build vs Buy Analysis

## BUG4 — Web Search API

| Opção | Preço | Confiabilidade | Integração | Decisão |
|---|---|---|---|---|
| DuckDuckGo scraping (atual) | Gratuito | Baixa — rate limits, layout instável | Já implementado | **Substituir** |
| **Tavily API** | Gratuito até 1.000 req/mês | Alta — API estável, foco em IA agents | `requests.post()` simples | **Escolhido** |
| SerpAPI | $50/mês mínimo | Alta | requests simples | Caro demais para uso pessoal |
| Bing Search API | $7/1.000 req | Alta | Azure dependency | Overhead de conta Azure |

**Decisão:** Tavily API. Plano gratuito generoso, API projetada para agentes de IA, integração mínima (1 endpoint POST), sem custo adicional para o volume atual.

## BUG1 — Slide Generation

| Opção | Decisão |
|---|---|
| Serviço externo (Beautiful.ai, Gamma) | Descartado — custo + lock-in + não controlável via API |
| HTML/CSS gerado por LLM (Gemini via Vertex) | **Escolhido** — já temos a infra Vertex AI, o slide_designer_agent usa o mesmo padrão dos outros agentes |
| Bibliotecas Python de apresentação (python-pptx) | Descartado — formato incompatível com o Playwright que já renderiza HTML |

## BUG3 — Code Execution / Plot

| Opção | Decisão |
|---|---|
| Manter execução local + salvar em GCS (abordagem atual do code_executor) | **Escolhido + corrigido** — só precisa retornar a URL corretamente no Markdown |
| Serviço externo de execução (E2B, Modal) | Overkill — o code_executor já funciona, só o retorno está errado |
