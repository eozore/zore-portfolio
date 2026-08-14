# Reliability Design
- try/except em todas as funções de bugfix — retornar None/fallback, não propagar exceção
- Logging com logger.warning() para falhas silenciosas
- BUG2: cada segmento tem seu próprio try/except — falha de 1 segmento não cancela os outros
