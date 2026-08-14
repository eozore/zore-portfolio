# Intent Statement — éozoré Content Studio Bugfixes

## Problem Statement
A pipeline de criação de conteúdo do éozoré (eozore.com/admin/csm) está em produção mas com 6 bugs que impedem o funcionamento correto ponta a ponta. Os mais críticos (BUG1 e BUG2) fazem com que todos os vídeos YouTube gerados tenham telas pretas (sem slides visuais) e timing de áudio incorreto (todos os segmentos concatenados num único vídeo em vez de individuais). Os demais bugs degradam a qualidade do artigo gerado (pesquisa web quebrada, gráficos Python não renderizados, validator injusto para artigos conceituais) e causam warnings nos logs (Pydantic v2).

## Target Customer
**Victor Zore** — Líder técnico em IA Generativa. Usa a plataforma diariamente para criar conteúdo técnico (artigos, roteiros YouTube, copies LinkedIn/Threads) de forma automatizada. A dor principal é: investe tempo cocriando a pauta com o CMO Agent e aprovando o conteúdo, mas o vídeo final sai inutilizável (tela preta, áudio dessincronizado).

## Success Metrics
1. **BUG1 resolvido:** Vídeos gerados têm slides HTML visuais reais por segmento (hook, intro, teoria, código, demo, comparativo, resumo) em vez de tela preta.
2. **BUG2 resolvido:** Cada segmento gera um vídeo HeyGen individual; VideoEditor concatena corretamente na ordem do manifesto; áudio e imagem estão sincronizados.
3. **BUG3 resolvido:** Gráficos matplotlib do artigo renderizam como `<img>` via URL GCS; zero erros de parser JavaScript.
4. **BUG4 resolvido:** `search_web()` usa Tavily API; taxa de sucesso > 95% nas pesquisas do CMO.
5. **BUG5 resolvido:** Zero warnings `Field name "copy" shadows an attribute` no startup do cmo-agent.
6. **BUG6 resolvido:** Artigos conceituais/estratégicos não são reprovados por "ausência de código Python".

## Initiative Trigger
**Débito técnico acumulado em produção.** A pipeline foi construída iterativamente e chegou a um ponto onde a integração completa (CMO chat → vídeo final) não funciona. Com os bugs corrigidos, Victor pode usar a ferramenta para publicar conteúdo real, que é o objetivo central da plataforma.

## Initial Scope Signal
`feature` — envolve criação de novo agente Python (`slide_designer_agent.py`), refatoração de contratos Pub/Sub (`AvatarCompletedMsg`), e modificações em múltiplos serviços Cloud Run. Não é `bugfix` puro porque BUG1 e BUG2 requerem implementação de funcionalidade nova e redesign de arquitetura de mensagens.

## Constraints
- Stack imutável: Next.js 14 + Python FastAPI + GCP (vazfy-417019)
- Todos os LLMs devem usar Vertex AI (Gemini) — sem OpenAI/Anthropic direto
- BUG2 (mudança de contrato Pub/Sub) deve ser o último a ser deployado — breaking change em 3 serviços simultâneos
- Variáveis de ambiente adicionais (`TAVILY_API_KEY`) via Secret Manager do GCP
