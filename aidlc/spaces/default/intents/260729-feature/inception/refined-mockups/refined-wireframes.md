# Refined Mockups

## BUG1 — Slide HTML estrutura final (refinado)

O `slide_designer_agent` deve gerar um HTML autossuficiente por segmento. Estrutura obrigatória:

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;700;800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
  <style>
    /* Reset + dimensões fixas */
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html, body { width: 1920px; height: 1080px; overflow: hidden; background: #0d0f14; }
    
    /* Grid sutil laranja */
    body::before {
      content: '';
      position: absolute; inset: 0;
      background-image: linear-gradient(rgba(232,93,4,0.06) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(232,93,4,0.06) 1px, transparent 1px);
      background-size: 80px 80px;
    }
    
    /* Fade-in animation */
    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: translateY(0); }
    }
    
    /* Elementos revelados por âncora */
    [id^="fd"] { animation: fadeIn 0.4s ease forwards; }
    #fd2, #fd3, #fd4 { display: none; }
    
    /* Logo éozoré */
    .logo {
      position: absolute; bottom: 40px; right: 60px;
      font-family: 'Space Grotesk', sans-serif;
      font-size: 1.4rem; font-weight: 800;
      color: rgba(255,255,255,0.3);
      letter-spacing: 2px;
    }
  </style>
</head>
<body>
  <!-- CONTEÚDO DO BEAT -->
  <div id="fd1"><!-- Conteúdo principal visível --></div>
  <div id="fd2"><!-- Revelado pela 1ª âncora --></div>
  <div id="fd3"><!-- Revelado pela 2ª âncora --></div>
  <div id="fd4"><!-- Revelado pela 3ª âncora --></div>
  
  <div class="logo">éozoré</div>
</body>
</html>
```

## BUG3 — Artigo com imagem (antes/depois do fix)

**Antes:** `RichArticleRenderer.tsx` tem `InteractiveChart` component que tenta parsear Python
**Depois:** `code_executor.py` retorna URL GCS; artigo contém `![grafico](https://storage.../plot_xxx.png)`; renderer usa handler de `<img>` já existente. Zero mudança na UI — a imagem simplesmente aparece.

## Componentes de UI alterados

| Componente | Mudança |
|---|---|
| `RichArticleRenderer.tsx` | Remover `InteractiveChart`; garantir que `![alt](url)` com URL GCS renderize como `<img>` |
| `CsmDashboard.tsx` | Adicionar `tipo_artigo?: "tecnico" \| "conceitual" \| "estrategico"` na interface `PautaConcebida`; exibir como badge na UI da pauta |
