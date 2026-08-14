# User Stories

## BUG3 — Gráficos
**US-3.1** Como Victor, quero que gráficos matplotlib no artigo apareçam como imagens reais, não como código quebrado, para que o artigo seja publicável sem edição manual.
- Critério: bloco `python-plot` → imagem `<img>` com URL GCS válida no artigo renderizado

## BUG4 — Busca web
**US-4.1** Como Victor, quero que o CMO Agent pesquise na web de forma confiável durante a fase de research, para que as teses propostas sejam embasadas em dados reais e atuais.
- Critério: `search_web("LoRA fine-tuning 2025")` retorna ≥3 resultados relevantes sem erro

## BUG5 — Pydantic
**US-5.1** Como Victor, quero ver os logs do cmo-agent sem warnings de Pydantic no startup, para que seja fácil identificar erros reais nos logs.
- Critério: startup do cmo-agent sem nenhuma linha `Field name "copy" shadows an attribute`

## BUG6 — Validator contextual
**US-6.1** Como Victor, quero que artigos sobre liderança, estratégia ou negócios não sejam reprovados por "ausência de código Python", para que eu possa publicar conteúdo para um público não-técnico.
- Critério: artigo com `tipo_artigo: "estrategico"` e sem código Python → aprovado pelo validator se tiver LaTeX e ≥800 palavras

## BUG1 — Slides visuais
**US-1.1** Como Victor, quero que cada segmento do vídeo YouTube tenha um slide visual real (não tela preta), para que o vídeo final seja profissional e publicável.
- Critério: manifesto HTML tem `<section class="slide">` com HTML visual completo por segmento (não placeholder vazio)

## BUG2 — Sync de vídeo
**US-2.1** Como Victor, quero que o avatar fale sincronizado com o conteúdo visual de cada segmento, para que o vídeo final não tenha áudio e imagem dessincronizados.
- Critério: cada segmento do manifesto corresponde a um vídeo HeyGen individual; VideoEditor concatena na ordem correta
