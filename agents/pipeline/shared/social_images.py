"""
social_images.py — templates de imagem para os formatos que não vinham com HTML.

Contexto: o distribution_agent gera `imageHtml` para posts de imagem e de
LinkedIn, mas NÃO para carrossel (só heading/body por slide) nem para stories
(só copy). Sem imagem, o Instagram rejeita os três formatos — eles eram
gerados, exibidos na aba de revisão, e descartados na aprovação.

Por que template determinístico em vez de pedir HTML ao modelo:

  1. Paleta garantida. A geração por LLM já saiu fora da marca uma vez (usou o
     tema escuro do GitHub), e carrossel tem N slides — N chances de variar.
  2. Consistência entre slides do mesmo carrossel, que precisam parecer uma
     sequência e não peças soltas.
  3. Custo e latência zero por slide.

A paleta abaixo é a mesma de slide_designer_agent, thumbnail_agent e
distribution_agent. Se mudar lá, mude aqui.
"""

from __future__ import annotations

import html as html_escape
import re

# ── Paleta da marca ───────────────────────────────────────────────────────────
BG          = "#0d0f14"
BG_ALT      = "#151920"
TEXT        = "#eae4dc"
TEXT_SOFT   = "#8a8378"
ACCENT      = "#e8873a"
ACCENT_SOFT = "#f5b56a"

# Dimensões exigidas por cada superfície do Instagram
CAROUSEL_SIZE = (1080, 1080)
FEED_SIZE     = (1080, 1080)
STORY_SIZE    = (1080, 1920)
LINKEDIN_SIZE = (1200, 628)

_FONT_STACK = "'Space Grotesk','Helvetica Neue',Arial,sans-serif"


def _shell(body: str, width: int, height: int, padding: int = 90) -> str:
    """Casca comum: sem JS, sem fonte externa, tamanho fixo — requisito do renderer."""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{width}px;height:{height}px;background:{BG};color:{TEXT};
font-family:{_FONT_STACK};padding:{padding}px;display:flex;flex-direction:column;
justify-content:center;overflow:hidden}}
.accent{{color:{ACCENT}}}
.soft{{color:{TEXT_SOFT}}}
</style></head><body>{body}</body></html>"""


def carousel_slide_html(
    heading: str,
    body: str,
    slide_number: int,
    total: int,
    series: str = "",
) -> str:
    """
    Um slide de carrossel do Instagram (1080x1080).

    O contador e a barra de progresso existem porque carrossel sem indicação de
    posição perde muito swipe — o leitor não sabe que há mais conteúdo adiante.
    """
    h = html_escape.escape(heading or "")
    # Quebras do corpo viram <br>, preservando listas numeradas que o agente gera
    b = "<br>".join(html_escape.escape(line) for line in (body or "").split("\n") if line.strip())
    pct = int(slide_number / max(total, 1) * 100)
    tag = html_escape.escape(series.replace("-", " ")) if series else ""

    return _shell(f"""
<div style="display:flex;flex-direction:column;height:100%;justify-content:space-between">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <span class="soft" style="font-size:26px;letter-spacing:.16em;text-transform:uppercase">{tag}</span>
    <span class="accent" style="font-size:30px;font-weight:700">{slide_number}/{total}</span>
  </div>
  <div>
    <h1 class="accent" style="font-size:{68 if len(h) < 46 else 54}px;line-height:1.15;font-weight:700;margin-bottom:36px">{h}</h1>
    <p style="font-size:{38 if len(b) < 260 else 32}px;line-height:1.5;color:{TEXT}">{b}</p>
  </div>
  <div style="height:8px;background:{BG_ALT};border-radius:4px">
    <div style="height:100%;width:{pct}%;background:{ACCENT};border-radius:4px"></div>
  </div>
</div>""", *CAROUSEL_SIZE)


def story_html(copy: str, interactive: str = "", angle: str = "") -> str:
    """
    Um story do Instagram (1080x1920).

    O elemento interativo entra como dica visual: a enquete/quiz real é um
    sticker que o Instagram só permite adicionar manualmente no app, então a
    imagem mostra as opções para o post fazer sentido sozinho.
    """
    raw = str(copy or "")
    a = html_escape.escape(angle or "")

    # O agente às vezes coloca as opções dentro do copy ("...? Opção A: x
    # Opção B: y") e manda só um rótulo em interactiveElement. Nesse caso a
    # pergunta e as alternativas precisam ser separadas, senão viram um
    # parágrafo único e o story perde a cara de enquete.
    options: list[str] = []
    question = raw
    marcadores = re.split(r"(?=\bOpç[ãa]o\s+[A-Z0-9]\s*[:\-])", raw)
    if len(marcadores) > 1:
        question = marcadores[0].strip()
        options = [m.strip() for m in marcadores[1:] if m.strip()]
    elif interactive and "|" in str(interactive):
        options = [o.strip() for o in str(interactive).split("|") if o.strip()]

    q = html_escape.escape(question)
    label = ""
    if interactive and not options:
        label = (f'<p class="accent" style="font-size:34px;font-weight:700;margin-top:40px">'
                 f'{html_escape.escape(str(interactive))}</p>')
    botoes = "".join(
        f'<div style="background:{BG_ALT};border:2px solid {ACCENT};border-radius:18px;'
        f'padding:30px;margin-top:24px;font-size:34px;line-height:1.3;color:{TEXT}">'
        f'{html_escape.escape(o)}</div>'
        for o in options
    )
    block = f'<div style="margin-top:50px">{botoes}</div>' if botoes else label

    # Um story tem 1920px de altura: sem distribuir os blocos, o conteúdo fica
    # empilhado no topo e sobra metade da tela vazia. `space-between` com um
    # corpo centralizado usa a área toda e mantém o rodapé ancorado embaixo.
    return _shell(f"""
<div style="display:flex;flex-direction:column;height:100%;justify-content:space-between">
  <div>{f'<span class="soft" style="font-size:30px;letter-spacing:.16em;text-transform:uppercase">{a}</span>' if a else ''}</div>
  <div style="flex:1;display:flex;flex-direction:column;justify-content:center;padding:40px 0">
    <p style="font-size:{56 if len(q) < 150 else 46}px;line-height:1.35;font-weight:600">{q}</p>
    {block}
  </div>
  <div class="soft"><span style="font-size:28px">eozore.com</span></div>
</div>""", *STORY_SIZE, padding=100)


def fallback_image_html(title: str, body: str, width: int, height: int) -> str:
    """Usado quando o agente não emitiu imageHtml para um post que precisa de imagem."""
    return _shell(f"""
<h1 class="accent" style="font-size:{62 if len(title) < 50 else 48}px;line-height:1.15;
font-weight:700;margin-bottom:32px">{html_escape.escape(title or '')}</h1>
<p style="font-size:34px;line-height:1.5">{html_escape.escape(body or '')}</p>
""", width, height)
