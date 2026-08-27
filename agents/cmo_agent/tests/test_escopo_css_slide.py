"""
tests/test_escopo_css_slide.py
===============================
O CSS do slide precisa chegar inteiro ao deck.

Regressão de produção (27/08/2026): o vídeo saiu com os slides sem estilo
nenhum — texto corrido a 18px encostado à esquerda de um quadro 1920x1080.

O manifesto gerado referenciava `var(--…)` 173 vezes e definia ZERO
variáveis. A rotina de escopamento apagava blocos `:root` para impedir que
regras de documento vazassem para o deck, e junto com eles ia embora toda a
declaração de custom properties do slide_designer. Cada `font-size`, `color`
e `gap` virava valor inválido e caía no padrão do navegador.

Não havia erro em lugar nenhum: o HTML era válido, o deck navegava, o vídeo
era gravado e publicado.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from manifest_builder import (  # noqa: E402
    _blocos_de_topo,
    escopar_css_do_slide,
)


def test_custom_properties_do_root_sobrevivem():
    """O defeito exato: `:root` era apagado e levava as variáveis junto."""
    css = escopar_css_do_slide(
        ":root { --accent: #e8873a; --fs-title: 64px; } "
        ".titulo { color: var(--accent); font-size: var(--fs-title); }",
        "yt-02",
    )
    assert "--accent: #e8873a" in css, "as custom properties precisam sobreviver"
    assert "#yt-02 {" in css, ":root deve virar #yt-02, não sumir"
    assert "#yt-02 .titulo" in css


def test_toda_variavel_referenciada_tem_definicao():
    """
    A verificação que teria pego o defeito olhando só o resultado: contar
    `var(--x)` contra `--x:`. Em produção deu 173 contra 0.
    """
    css = escopar_css_do_slide(
        ":root { --a: 1px; --b: red; } .x { margin: var(--a); color: var(--b); }",
        "yt-01",
    )
    import re
    usadas = set(re.findall(r"var\(\s*(--[\w-]+)", css))
    definidas = set(re.findall(r"(--[\w-]+)\s*:", css))
    assert usadas <= definidas, f"sem definição: {usadas - definidas}"


def test_keyframes_nao_viram_seletor():
    """
    A regex antiga entrava no `@keyframes` e emitia `#yt-02 to { … }`.
    O passo `from`/`to` tem que continuar dentro do bloco.
    """
    css = escopar_css_do_slide(
        "@keyframes fadeIn { from { opacity: 0 } to { opacity: 1 } } "
        ".fd { animation: fadeIn 0.4s ease forwards; }",
        "yt-02",
    )
    assert "#yt-02 to" not in css and "#yt-02 from" not in css
    assert "@keyframes fadeIn__yt_02" in css


def test_animacao_aponta_para_o_keyframe_renomeado():
    """Renomear sem reescrever quem referencia deixaria a animação morta."""
    css = escopar_css_do_slide(
        "@keyframes fadeIn { to { opacity: 1 } } .fd { animation: fadeIn 0.4s ease; }",
        "yt-03",
    )
    assert "animation: fadeIn__yt_03 0.4s ease" in css


def test_slides_diferentes_nao_colidem_em_keyframes():
    """
    Antes, `shared_keyframes_added` mantinha apenas os @keyframes do PRIMEIRO
    slide — do segundo em diante as animações apontavam para nada.
    """
    a = escopar_css_do_slide("@keyframes ent { to { opacity: 1 } }", "yt-01")
    b = escopar_css_do_slide("@keyframes ent { to { opacity: .5 } }", "yt-02")
    assert "ent__yt_01" in a and "ent__yt_02" in b


def test_media_query_preserva_a_condicao_e_escopa_o_conteudo():
    css = escopar_css_do_slide(
        "@media (max-width: 1200px) { .grid { gap: 20px } }", "yt-04",
    )
    assert "@media (max-width: 1200px)" in css
    assert "#yt-04 .grid" in css


def test_seletor_composto_com_body_mantem_o_resto():
    css = escopar_css_do_slide("body .painel { padding: 40px }", "yt-05")
    assert "#yt-05 .painel" in css


def test_seletores_em_lista_sao_escopados_um_a_um():
    css = escopar_css_do_slide(".a, .b { color: red }", "yt-06")
    assert "#yt-06 .a" in css and "#yt-06 .b" in css


def test_font_face_nao_e_escopado():
    """`@font-face` é global por definição; escopar quebraria a fonte."""
    css = escopar_css_do_slide(
        "@font-face { font-family: X; src: url(a.woff2) }", "yt-07",
    )
    assert "@font-face {" in css and "#yt-07 @font-face" not in css


def test_blocos_de_topo_conta_chaves_aninhadas():
    blocos = _blocos_de_topo("@media screen { .a { color: red } } .b { color: blue }")
    assert len(blocos) == 2
    assert blocos[0][0] == "@media screen"
    assert blocos[1][0] == ".b"


def test_comentario_com_chave_nao_desalinha_o_scanner():
    blocos = _blocos_de_topo("/* } não conta */ .a { color: red }")
    assert len(blocos) == 1 and blocos[0][0] == ".a"
