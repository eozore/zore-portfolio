# Accessibility Checklist

## BUG3 — Imagens no artigo
- [x] `alt` text presente em todas as imagens geradas (`plot-<uuid>` como fallback)
- [x] Imagens não são o único portador de informação (código fonte ainda visível acima)

## BUG6 — Badge tipo_artigo
- [x] Badge tem texto legível (não apenas cor)
- [x] Contraste adequado (texto claro em fundo escuro)
- [x] `aria-label` opcional: `tipo de artigo: técnico`

## BUG1 — Slides HTML (para vídeo — não é UI interativa)
- Slides são renderizados offline pelo Playwright para gerar vídeo — não são acessados por usuários com leitores de tela
- Não aplicável acessibilidade WCAG
