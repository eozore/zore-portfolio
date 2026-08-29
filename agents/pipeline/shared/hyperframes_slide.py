# -*- coding: utf-8 -*-
"""
hyperframes_slide.py — Renderiza um slide do deck com o HyperFrames.

Alternativa determinística ao `render_slide_clip` do `compose.py`, que grava a
página em tempo real com o Playwright. A diferença não é de qualidade de
imagem, é de CONFIABILIDADE do tempo:

  Playwright   abre a página, dispara a animação, espera N segundos de relógio
               e salva o que o navegador conseguiu gravar. Quantos quadros
               saem, e o que está em cada um, depende da CPU no momento.

  HyperFrames  pergunta "como está o quadro 90?", posiciona toda animação em
               90/fps por matemática inteira, captura, e passa ao 91. O mesmo
               deck sempre produz o mesmo arquivo.

É por isso que aqui não existe `-ss lead_in` nem correção de duração: não há
diferença entre abrir a página e começar a animar, e o clipe já sai com a
duração pedida. O `-t` continua explícito porque quem manda no corte é a
locução, não o vídeo (ver `compose.py`).

## Reveals viram relógio, não temporizador

O deck normal esconde blocos com `.fd-hidden` e os revela por
`setTimeout` + `deckAPI.revelar()`. Um renderizador que percorre quadros não
tem como percorrer um `setTimeout`: ele nunca dispara, e o slide sai com só o
primeiro bloco — que é exatamente o defeito que as âncoras existiam para
evitar.

Aqui cada âncora vira `animation-delay` numa animação CSS com
`animation-fill-mode: both`. O `both` mantém o estado inicial durante o
atraso, então o elemento fica invisível até a hora dele E o renderizador
consegue posicionar a animação em qualquer instante. Sem JS, sem GSAP e sem
CDN — o container renderiza offline.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger("pipeline.hyperframes_slide")

# Duração da entrada de cada bloco revelado. Curta de propósito: o objetivo é
# dar movimento à ilustração, não fazer o espectador esperar o texto chegar.
ENTRADA_S = 0.6

# Classe e keyframes injetados por este módulo. Prefixo `hf-` para não colidir
# com nada que o slide_designer tenha gerado.
CSS_REVEAL = f"""
@keyframes hf-entra {{
  from {{ opacity: 0; transform: translateY(40px); }}
  to   {{ opacity: 1; transform: none; }}
}}
@keyframes hf-pulsa {{
  0%,100% {{ transform: none; }}
  50%     {{ transform: scale(1.04); }}
}}
/* Propriedades LONGAS, e `animation-delay` deliberadamente de fora.
   Duas forças puxam em sentidos opostos aqui, e o atalho não atende as duas:

   1. Precisa de `!important` para vencer o deck. O slide_designer emite
      `#yt-10 .fd {{ animation: fadeIn__yt_10 ... }}` — (1,1,0) contra os
      (0,1,0) de uma classe. Sem isso a animação do deck roda no instante 0 e
      a âncora é ignorada.

   2. NÃO pode marcar o delay como important. É escrevendo em
      `animation-delay` que o renderizador posiciona a animação em cada
      quadro; um `!important` nosso bloqueia essa escrita e o seek para de
      funcionar — o bloco aparece cedo, sem relação com a locução.

   O atalho `animation` com `!important` reinicia o delay junto, o que
   satisfaz (1) e destrói (2). Por isso, longhand. */
.hf-rev {{
  animation-name: hf-entra !important;
  animation-duration: {ENTRADA_S}s !important;
  animation-timing-function: cubic-bezier(.2,.7,.3,1) !important;
  animation-fill-mode: both !important;
  animation-iteration-count: 1 !important;
}}
.hf-pulsa {{
  animation-name: hf-pulsa !important;
  animation-duration: .8s !important;
  animation-timing-function: ease !important;
  animation-fill-mode: both !important;
  animation-iteration-count: 1 !important;
}}
"""


class HyperFramesError(RuntimeError):
    """Falha ao montar ou renderizar a composição."""


# ── Montagem da composição (puro, testável sem navegador) ─────────────────────

def _extrair_css(deck_html: str) -> str:
    return "\n".join(
        m.group(1) for m in re.finditer(r"<style[^>]*>(.*?)</style>", deck_html, re.S)
    )


def _extrair_slide(deck_html: str, slide_id: str) -> str:
    """O `<section>` do slide pedido, do início até o próximo slide ou script."""
    padrao = (
        r'<section class="slide" id="' + re.escape(slide_id) + r'".*?'
        r'(?=<section class="slide"|<script>|</body>)'
    )
    m = re.search(padrao, deck_html, re.S)
    if not m:
        raise HyperFramesError(
            f"slide '{slide_id}' não encontrado no deck. "
            "O manifesto e o HTML estão fora de sincronia."
        )
    return m.group(0)


def _neutralizar_navegacao(css: str) -> str:
    """
    Remove o par de regras que esconde slide inativo.

    `.slide{display:none!important}` existe para a NAVEGAÇÃO do deck, onde só
    o `.active` aparece. Na composição quem recorta o tempo é o próprio
    clipe — e uma regra com `!important` venceria qualquer coisa que o
    runtime tentasse fazer com `display`, deixando o clipe inteiro invisível.
    """
    css = css.replace(".slide{display:none!important;", ".slide{")
    css = css.replace(".slide.active{display:flex!important}", "")
    # Variante com espaços, caso o gerador mude de formatação.
    css = re.sub(r"\.slide\s*\{\s*display\s*:\s*none\s*!important\s*;", ".slide{", css)
    return css


def _acrescentar(tag: str, classe: str, estilo: str) -> str:
    """
    Acrescenta classe e estilo a uma tag SEM duplicar os atributos.

    Escrever `class="hf-rev"` numa tag que já tem `class` produz dois
    atributos `class`, e o navegador fica com o PRIMEIRO — o resto do estilo
    do elemento é descartado em silêncio. O mesmo vale para `style`.
    """
    if re.search(r'\sclass="', tag):
        tag = re.sub(r'class="([^"]*)"', lambda m: f'class="{m.group(1).strip()} {classe}"',
                     tag, count=1)
    else:
        tag = tag[:-1] + f' class="{classe}">'

    if re.search(r'\sstyle="', tag):
        tag = re.sub(r'style="([^"]*)"',
                     lambda m: f'style="{m.group(1).rstrip().rstrip(";")};{estilo}"',
                     tag, count=1)
    else:
        tag = tag[:-1] + f' style="{estilo}">'
    return tag


def aplicar_reveals(slide_html: str, plano: list[tuple[float, str, str]]) -> str:
    """
    Converte o plano de âncoras em atrasos de animação dentro do slide.

    `plano` vem de `compose.plano_de_reveals`: (segundo, ação, elemento).
    A ação `reveal` faz o bloco entrar; `destaque` faz pulsar.
    """
    for segundo, acao, elemento in plano:
        classe = "hf-rev" if acao == "reveal" else "hf-pulsa"
        alvo = re.compile(r"<(\w+)([^>]*\sid=\"" + re.escape(elemento) + r"\"[^>]*)>")

        def troca(m: re.Match) -> str:
            tag = m.group(0)
            # `fd-hidden` é `display:none` — o JS que o removia não roda aqui.
            tag = re.sub(r"\bfd-hidden\b", "", tag)
            # Delay inline e SEM `!important`: inline já vence a folha de
            # estilo, e deixar a propriedade "normal" é o que permite ao
            # renderizador reescrevê-la para posicionar cada quadro.
            return _acrescentar(
                tag, classe, f"animation-delay:{max(segundo, 0):.2f}s"
            )

        slide_html = alvo.sub(troca, slide_html, count=1)

    # Qualquer `fd-hidden` que sobrou não tinha âncora. Sem o JS de revelação
    # ele ficaria escondido o clipe inteiro — some com a regra e o bloco ao
    # menos aparece, que é melhor do que a metade em branco do slide.
    slide_html = re.sub(r"\bfd-hidden\b", "", slide_html)
    return slide_html


def montar_composicao(
    deck_html: str,
    slide_id: str,
    duration_s: float,
    width: int,
    height: int,
    *,
    plano: Optional[list[tuple[float, str, str]]] = None,
    fps: int = 30,
) -> str:
    """Deck + slide + plano de reveals → uma composição HyperFrames completa."""
    css   = _neutralizar_navegacao(_extrair_css(deck_html))
    slide = _extrair_slide(deck_html, slide_id)
    slide = aplicar_reveals(slide, plano or [])
    slide = slide.replace('class="slide"', 'class="slide clip"', 1)
    slide = slide.replace(
        "<section ", f'<section data-start="0" data-duration="{duration_s:.2f}" ', 1
    )

    # `data-no-timeline`: esta composição é movida só por CSS e nunca registra
    # `window.__timelines`. Sem o atributo o renderizador espera 45 segundos
    # por esse registro em TODO slide antes de desistir e renderizar mesmo
    # assim — meia hora desperdiçada num deck de oito slides.
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width={width}, height={height}" />
<style>
html,body{{margin:0;padding:0;background:#0d0f14;}}
#root{{position:relative;width:{width}px;height:{height}px;overflow:hidden;background:#0d0f14;}}
.clip{{position:absolute;inset:0;}}
/* O contador "4 / 13" e a barra laranja saíam queimados em todos os slides. */
#hud,#progress-bar{{display:none !important;}}
{css}
{CSS_REVEAL}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-no-timeline
     data-start="0" data-duration="{duration_s:.2f}"
     data-width="{width}" data-height="{height}" data-fps="{fps}">
{slide}
</div>
</body>
</html>"""


# ── Renderização ──────────────────────────────────────────────────────────────

def disponivel() -> bool:
    """O CLI do HyperFrames está instalado nesta imagem?"""
    return shutil.which("hyperframes") is not None


def renderizar_composicao(
    composicao_html: str,
    dest_mp4: Path,
    *,
    fps: int = 30,
    qualidade: str = "standard",
    workers: str = "auto",
    timeout_s: int = 900,
) -> Path:
    """Escreve a composição num projeto temporário e chama o CLI."""
    with tempfile.TemporaryDirectory(prefix="hf-") as tmp:
        proj = Path(tmp)
        (proj / "index.html").write_text(composicao_html, encoding="utf-8")
        saida = proj / "out.mp4"
        cmd = [
            "hyperframes", "render", str(proj),
            "-o", str(saida),
            "--fps", str(fps),
            "--quality", qualidade,
            "--workers", workers,
            "--quiet",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
        if proc.returncode != 0 or not saida.exists():
            cauda = (proc.stderr or proc.stdout or "")[-1200:]
            raise HyperFramesError(f"hyperframes render falhou ({proc.returncode}): {cauda}")
        dest_mp4.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(saida), str(dest_mp4))
    return dest_mp4
