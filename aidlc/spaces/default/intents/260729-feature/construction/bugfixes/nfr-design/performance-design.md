# Performance Design
- BUG1: slide_designer chamadas paralelas via asyncio.gather() para os N segmentos do manifesto
- BUG2: asyncio.sleep(0.5) entre chamadas HeyGen para evitar 429
- BUG3: subprocess timeout=12s (já existente), GCS upload síncrono no executor thread
