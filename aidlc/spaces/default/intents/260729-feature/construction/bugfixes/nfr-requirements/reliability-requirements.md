# Reliability Requirements
- Todos os bugfixes devem ter fallback silencioso (não quebrar a pipeline se falharem)
- BUG1: HTML inválido → manter placeholder original
- BUG3: upload GCS falha → retornar None, manter código sem imagem
- BUG4: Tavily falha → retornar string de erro (comportamento atual)
- BUG2: segmento HeyGen falha → marcar segmento como failed, não bloquear outros segmentos
