# Design Decisions

1. Slides HTML são autossuficientes (sem dependências externas exceto Google Fonts CDN) — obrigatório para Playwright no Cloud Run
2. Elementos `fd1-fd4` são revelados por JavaScript no VideoEditorJob via `page.evaluate()` — não por CSS hover
3. `tipo_artigo` é badge colorido read-only na UI — não é input editável pelo usuário (o CMO define durante o chat)
4. GCS URL para plots usa bucket público ou URL com acesso autenticado — implementar com URL pública (Storage Object Viewer)
