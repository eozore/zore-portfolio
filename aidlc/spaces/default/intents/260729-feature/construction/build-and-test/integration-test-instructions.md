# Integration Test Instructions

## BUG4 — Testar Tavily após deploy
```bash
CMO="https://cmo-agent-4zffe4l4lq-uc.a.run.app"
curl -s -X POST "$CMO/interview" -H "Content-Type: application/json" \
  -d '{"message":"teste search_web","session_id":"test-123"}' | python3 -m json.tool
```

## BUG1 — Testar slide_designer após deploy
```bash
curl -s -X POST "$CMO/package" -H "Content-Type: application/json" \
  -d '{"pauta":{"titulo":"Teste LoRA","subtitulo":"","tese":"A","publico":"líderes","objetivo_aprendizado":"ok","hardskills":["x"],"duracao_alvo":"5 min","serie":"ia","tipo_artigo":"tecnico"},"articleContent":"Conteúdo aqui.","category":"ml","language":"pt-BR"}' \
  --max-time 120 | python3 -c "import sys,json; d=json.load(sys.stdin); print('manifest_len:', len(d.get('manifestHtml','')), 'slide_count:', d.get('manifestHtml','').count('section'))"
```
