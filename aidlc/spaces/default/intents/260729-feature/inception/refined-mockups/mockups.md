# Mockups — éozoré Content Studio Bugfixes

Ver `refined-wireframes.md` para wireframes completos.

## Resumo dos mockups por bug

### BUG1 — Slide Designer (principal)
HTML 1920×1080 (horizontal) e 1080×1920 (vertical) gerado por `slide_designer_agent.py`.
Design system: `#0d0f14` bg, Space Grotesk + JetBrains Mono, grid laranja sutil, logo éozoré br.
8 beat types com layouts específicos documentados em `refined-wireframes.md`.

### BUG3 — Artigo com gráfico
Sem mudança de layout UI. O `![alt](url_gcs)` é renderizado como `<img className="w-full rounded-lg">` pelo handler de imagens existente no RichArticleRenderer.

### BUG6 — Badge tipo_artigo
Badge colorido read-only ao lado do título da pauta aprovada.
- `tecnico` → `bg-blue-900 text-blue-300`
- `conceitual` → `bg-purple-900 text-purple-300`
- `estrategico` → `bg-green-900 text-green-300`
