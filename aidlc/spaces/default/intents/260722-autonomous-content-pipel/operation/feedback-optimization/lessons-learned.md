# Lessons Learned — Bolt 0 + Bolt 1

1. **HeyGen Lipsync v3 payload**: campo `video` exige `type: 'url'` explícito — não aceita apenas `{url: '...'}`
2. **Custo real medido**: $0.0335/s para Lipsync speed — confirma pricing público. Teto R$100 cobre ~50 min de vídeo.
3. **ElevenLabs Flash v2.5**: qualidade da voz clonada aprovada por Victor. Latência 1.19s para 237 chars — excelente.
4. **YouTube OAuth**: fluxo de Desktop App (urn:ietf:wg:oauth:2.0:oob) foi descontinuado em 2022. Usar Aplicativo da Web com redirect para localhost.
5. **Segmentos slide puro**: economizam ~20% do custo HeyGen. Manifesto v2 já suporta via `script=''`.