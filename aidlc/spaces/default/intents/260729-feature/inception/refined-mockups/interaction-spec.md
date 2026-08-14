# Interaction Spec

## BUG6 — tipo_artigo badge
- Exibido em `IdeaTab` quando a pauta é definida (bloco JSON detectado)
- Read-only: não é editável pelo usuário
- Fallback: se ausente no JSON, não exibir badge (campo opcional)

## BUG1 — Slide transitions (VideoEditorJob)
- Âncoras (`anchors[].on_phrase`) disparam `document.getElementById("fd2").style.display = "block"` via `page.evaluate()` no Playwright
- Ordem: fd1 visível → frase âncora → fd2 aparece → próxima frase → fd3 aparece, etc.

## BUG3 — Artigo imagens
- Sem interação adicional. Imagem renderizada inline no artigo.
- Alt text: nome do arquivo sem extensão (ex: `plot-abc12345`)
