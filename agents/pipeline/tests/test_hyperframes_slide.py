# -*- coding: utf-8 -*-
"""
Testes do conversor deck → composição HyperFrames.

Exercitam a montagem, que é pura. A renderização em si depende do CLI e do
Chromium e fica fora daqui — o que se prova neste arquivo é que o HTML que
chega ao renderizador diz o que deveria dizer.
"""

import re

import pytest

from shared.hyperframes_slide import (
    HyperFramesError,
    _acrescentar,
    _neutralizar_navegacao,
    aplicar_reveals,
    montar_composicao,
)

DECK = """<!doctype html><html><head><style>
.slide{display:none!important;position:absolute;inset:0;padding:60px;background:#0d0f14}
.slide.active{display:flex!important}
:root{--acento:#e8873a;--texto:#eae4dc}
#yt-02 .fd{animation:fadeIn__yt_02 .4s ease forwards}
#yt-02 .fd-hidden{display:none}
</style></head><body>
<div id="hud"><span id="slide-counter">1 / 2</span></div>
<section class="slide" id="yt-02" data-seg="yt-02" style="position:absolute;inset:0;">
  <div id="fd1" class="equation-box fd">primeiro</div>
  <div id="fd2" class="grid fd fd-hidden">segundo</div>
  <div id="b1" class="bullet fd fd-hidden">terceiro</div>
</section>
<section class="slide" id="yt-03" data-seg="yt-03"><div id="fd1">outro slide</div></section>
<script>var slides=document.querySelectorAll('.slide');</script>
</body></html>"""


# ── A armadilha do atributo duplicado ─────────────────────────────────────────

def test_acrescentar_nao_duplica_class():
    """
    Escrever um segundo `class=` descarta o estilo do elemento em silêncio.

    Defeito real: a primeira conversão gerava
    `<div id="fd1" class="hf-rev" class="equation-box fd">`. O navegador fica
    com o PRIMEIRO atributo, então `equation-box` sumia — o bloco perdia
    fundo, borda e espaçamento, e nenhuma etapa acusava erro.
    """
    tag = _acrescentar('<div id="fd1" class="equation-box fd">', "hf-rev", "animation-delay:2s")
    assert tag.count("class=") == 1
    assert "equation-box" in tag and "fd" in tag and "hf-rev" in tag
    assert tag.count("style=") == 1
    assert "animation-delay:2s" in tag


def test_acrescentar_preserva_style_existente():
    tag = _acrescentar('<section style="inset:0;">', "hf-rev", "animation-delay:1.5s")
    assert tag.count("style=") == 1
    assert "inset:0" in tag and "animation-delay:1.5s" in tag


def test_acrescentar_cria_atributos_quando_faltam():
    tag = _acrescentar('<div id="b1">', "hf-pulsa", "animation-delay:0.00s")
    assert 'class="hf-pulsa"' in tag
    assert "animation-delay:0.00s" in tag


# ── Reveals ───────────────────────────────────────────────────────────────────

def test_reveal_vira_atraso_de_animacao():
    slide = aplicar_reveals(
        '<div id="fd2" class="grid fd fd-hidden">x</div>',
        [(8.0, "reveal", "fd2")],
    )
    assert "hf-rev" in slide
    assert "animation-delay:8.00s" in slide


def test_reveal_remove_fd_hidden():
    """
    `fd-hidden` é `display:none`, e aqui nenhum JS o remove.

    Deixá-lo mataria a conversão inteira: a animação rodaria num elemento que
    o CSS mantém fora da tela, e o slide sairia com só o primeiro bloco — o
    mesmo sintoma que as âncoras existem para evitar.
    """
    slide = aplicar_reveals('<div id="fd2" class="fd fd-hidden">x</div>',
                            [(3.0, "reveal", "fd2")])
    assert "fd-hidden" not in slide


def test_bloco_sem_ancora_nao_fica_escondido():
    """Sem âncora e sem JS, `fd-hidden` deixaria metade do slide em branco."""
    slide = aplicar_reveals('<div id="fd9" class="fd fd-hidden">x</div>', [])
    assert "fd-hidden" not in slide


def test_destaque_usa_pulsa():
    slide = aplicar_reveals('<div id="b1" class="fd">x</div>', [(2.5, "destaque", "b1")])
    assert "hf-pulsa" in slide and "hf-rev" not in slide


# ── Navegação do deck ─────────────────────────────────────────────────────────

def test_neutraliza_display_none_da_navegacao():
    """
    `.slide{display:none!important}` venceria o recorte temporal do clipe.

    A regra existe para a navegação do deck, onde só o `.active` aparece. Se
    ela sobrevivesse, o clipe inteiro sairia invisível — 20 segundos de fundo
    liso, sem erro nenhum.
    """
    css = _neutralizar_navegacao(".slide{display:none!important;position:absolute}")
    assert "display:none!important" not in css
    assert "position:absolute" in css


def test_neutralizar_preserva_o_resto_do_css():
    css = _neutralizar_navegacao(DECK)
    assert ":root{--acento:#e8873a" in css or "--acento" in css


# ── Composição completa ───────────────────────────────────────────────────────

def test_composicao_declara_a_raiz_e_a_duracao():
    doc = montar_composicao(DECK, "yt-02", 17.8, 1920, 1080)
    assert 'data-composition-id="main"' in doc
    assert 'data-duration="17.80"' in doc
    assert 'data-width="1920"' in doc and 'data-height="1080"' in doc


def test_composicao_declara_no_timeline():
    """
    Sem `data-no-timeline` o renderizador espera 45s por um
    `window.__timelines` que uma composição só-CSS nunca registra — em todo
    slide, antes de renderizar mesmo assim.
    """
    assert "data-no-timeline" in montar_composicao(DECK, "yt-02", 10.0, 1920, 1080)


def test_composicao_leva_so_o_slide_pedido():
    doc = montar_composicao(DECK, "yt-02", 10.0, 1920, 1080)
    assert "primeiro" in doc
    assert "outro slide" not in doc


def test_composicao_esconde_o_hud():
    """O contador e a barra de progresso saíam queimados em todos os slides."""
    doc = montar_composicao(DECK, "yt-02", 10.0, 1920, 1080)
    assert re.search(r"#hud[^}]*display:\s*none", doc)


def test_composicao_marca_o_slide_como_clipe():
    doc = montar_composicao(DECK, "yt-02", 10.0, 1920, 1080)
    assert 'class="slide clip"' in doc
    assert 'data-start="0" data-duration="10.00"' in doc


def test_composicao_aplica_o_plano():
    doc = montar_composicao(
        DECK, "yt-02", 17.8, 1920, 1080,
        plano=[(0.5, "reveal", "fd1"), (9.0, "reveal", "fd2"), (12.0, "destaque", "b1")],
    )
    assert "animation-delay:0.50s" in doc
    assert "animation-delay:9.00s" in doc
    assert "animation-delay:12.00s" in doc
    # A REGRA `.fd-hidden{display:none}` continua no CSS; o que não pode
    # sobreviver é um ELEMENTO carregando a classe.
    corpo = doc.split("<body>", 1)[1]
    assert 'class="' in corpo and "fd-hidden" not in corpo


def test_composicao_nao_depende_de_rede():
    """
    O container renderiza offline: nenhuma tag externa pode entrar aqui.

    Uma composição que busca GSAP num CDN falha em Cloud Run sem saída para a
    internet — e falha DEPOIS de o avatar já ter sido pago.
    """
    doc = montar_composicao(DECK, "yt-02", 10.0, 1920, 1080)
    assert "http://" not in doc and "https://" not in doc
    assert "<script" not in doc


def test_slide_inexistente_falha_alto():
    """Um id errado gravava 15 segundos de tela preta sem ninguém perceber."""
    with pytest.raises(HyperFramesError, match="fora de sincronia"):
        montar_composicao(DECK, "yt-99", 10.0, 1920, 1080)


def test_reveal_vence_a_animacao_do_proprio_deck():
    """
    O deck emite `#yt-02 .fd{animation:...}` — (1,1,0) contra os (0,1,0) de
    uma classe.

    Sem `!important` a animação do deck roda no instante 0 e a âncora é
    ignorada: o bloco aparece animado, no tempo errado, e nada acusa erro.
    """
    doc = montar_composicao(DECK, "yt-02", 10.0, 1920, 1080,
                            plano=[(4.0, "reveal", "fd2")])
    regra = re.search(r"\.hf-rev\s*\{([^}]*)\}", doc, re.S)
    assert regra and "animation-name: hf-entra !important" in regra.group(1)


def test_delay_fica_fora_do_important():
    """
    É escrevendo em `animation-delay` que o renderizador posiciona a
    animação em cada quadro.

    Marcar o delay como `!important` bloqueia essa escrita: o seek para de
    funcionar e o bloco aparece cedo, sem relação com a locução. O sintoma é
    traiçoeiro porque o slide sai completo e bonito — só o tempo está errado.
    Por isso a regra usa propriedades longas e deixa o delay de fora.
    """
    slide = aplicar_reveals('<div id="fd2" class="row-item fd">x</div>',
                            [(4.05, "reveal", "fd2")])
    assert "animation-delay:4.05s" in slide
    assert "animation-delay:4.05s !important" not in slide


def test_regra_de_reveal_nao_usa_o_atalho_animation():
    """
    O atalho `animation` com `!important` reinicia `animation-delay` junto —
    e o delay é justamente o que precisa ficar livre para o seek.
    """
    doc = montar_composicao(DECK, "yt-02", 10.0, 1920, 1080)
    regra = re.search(r"\.hf-rev\s*\{([^}]*)\}", doc, re.S).group(1)
    assert "animation-delay" not in regra
    assert re.search(r"\banimation\s*:", regra) is None
