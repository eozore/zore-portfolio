# Stage Memory — Requirements Analysis

## Interpretations

- 2026-07-08T12:15:00Z — O usuário possui duas tools locais: `tool-videoyoutube` (editor automático de vídeo YouTube com pipeline GCP STT + Gemini + FFmpeg) e `tool-cromex` (scripts de processamento de dados para pricing/aderência). O refactor foca apenas na tool de vídeo.
- 2026-07-08T12:15:30Z — Existem DOIS pipelines de vídeo: `editor_pipeline.py` (versão legacy/hardcoded, usa paths fixos como `RAG2.mp4`) e `process_video.py` (versão genérica com argparse, usada pelo `server.js`). O refactor deve consolidar e o legacy pode ser removido.
- 2026-07-08T12:16:00Z — O `.gitignore` exclui `tool-*/` do versionamento. As pastas devem ser mantidas — é apenas um lembrete do usuário.
- 2026-07-08T12:20:00Z — O erro atual é `ModuleNotFoundError: No module named 'vertexai'` — dependência não instalada, mas sintoma de um problema maior: fragilidade arquitetural.
- 2026-07-08T12:25:00Z — O resultado desejado NÃO é apenas um refactor de limpeza — é uma evolução: API assíncrona com WebSocket, dois outputs (horizontal + vertical), e memória por projeto.
- 2026-07-08T12:27:00Z — O HTML vertical é gerado automaticamente pelo sistema a partir do horizontal. O sistema adapta/re-renderiza para 9:16.
- 2026-07-08T12:28:00Z — Cada vídeo é um "projeto com memória" — estado persistido, re-executável, consultável.

## Deviations

## Tradeoffs

## Open questions

- O "problema na ferramenta de video" é específico (crash em algum passo?) ou é a duplicação de lógica entre `editor_pipeline.py` e `process_video.py`?
- O `tool-cromex` também entra no escopo do refactor ou é apenas o `tool-videoyoutube`?
