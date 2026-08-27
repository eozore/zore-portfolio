"""
tests/test_capitulos.py
=======================
Capítulos do YouTube a partir do timeline medido.

O vídeo de 27/08 subiu com uma descrição de duas linhas — link do artigo e
"assine o canal" — enquanto os vídeos que o dono do canal escreve à mão trazem
capítulos com timestamp, e o YouTube os transforma em marcadores na barra de
progresso.

O dado sempre existiu: o `video_editor` grava `timeline.json` com o início e o
fim MEDIDOS de cada clipe. Ninguém lia.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from publisher_job.job import montar_capitulos, _titulo_do_slide  # noqa: E402

TIMELINE = [
    {"segment_id": "yt-01", "kind": "avatar", "slide": None,    "beat": "hook",   "start_s": 0.0},
    {"segment_id": "yt-02", "kind": "slide",  "slide": "yt-02", "beat": "intro",  "start_s": 18.1},
    {"segment_id": "yt-03", "kind": "slide",  "slide": "yt-03", "beat": "teoria", "start_s": 35.9},
    {"segment_id": "yt-04", "kind": "slide",  "slide": "yt-04", "beat": "codigo", "start_s": 75.5},
]

# `yt-02` declara o capítulo (contrato atual); `yt-03` só tem `main-title`
# (fallback para decks gerados antes da regra existir). `badge-label` NÃO é
# fonte: carrega o rótulo da categoria, que se repete slide a slide.
DECK = (
    '<section class="slide" id="yt-02">'
    '<div data-capitulo="A ponte da infraestrutura">'
    '<div class="badge-label">ENGENHARIA DE IA MODERNA</div></div></section>'
    '<section class="slide" id="yt-03">'
    '<div class="main-title">Estocasticidade em produção</div>'
    '<div class="badge-label">ENGENHARIA DE IA MODERNA</div></section>'
)


def test_primeiro_capitulo_e_sempre_zero():
    """O YouTube só cria marcadores se o primeiro capítulo for 00:00."""
    saida = montar_capitulos(TIMELINE, DECK)
    linhas = [l for l in saida.splitlines() if "—" in l]
    assert linhas[0].startswith("00:00")


def test_timestamp_vem_do_tempo_medido():
    """18,1s → 00:18. Estimar pelo manifesto daria capítulo deslocado."""
    saida = montar_capitulos(TIMELINE, DECK)
    assert "00:18 —" in saida
    assert "01:15 —" in saida          # 75,5s


def test_titulo_vem_do_slide_quando_existe():
    saida = montar_capitulos(TIMELINE, DECK)
    assert "A ponte da infraestrutura" in saida
    assert "Estocasticidade em produção" in saida


def test_segmento_de_avatar_usa_rotulo_do_beat():
    """Avatar não tem slide de onde tirar título; o beat dá o rótulo."""
    saida = montar_capitulos(TIMELINE, DECK)
    assert "O problema" in saida       # beat=hook


def test_menos_de_tres_capitulos_devolve_vazio():
    """
    Lista pela metade não vira capítulo no YouTube e ainda ocupa a descrição —
    pior que não ter.
    """
    assert montar_capitulos(TIMELINE[:2], DECK) == ""


def test_rotulos_repetidos_viram_um_capitulo_so():
    """Três "Como funciona" seguidos não ajudam ninguém a navegar."""
    repetido = [
        {"slide": None, "beat": "hook",   "start_s": 0.0},
        {"slide": None, "beat": "teoria", "start_s": 10.0},
        {"slide": None, "beat": "teoria", "start_s": 20.0},
        {"slide": None, "beat": "teoria", "start_s": 30.0},
        {"slide": None, "beat": "resumo", "start_s": 40.0},
    ]
    saida = montar_capitulos(repetido, "")
    assert saida.count("Como funciona") == 1


def test_titulo_do_slide_ignora_outros_slides_do_deck():
    """O regex tem que parar na `</section>` do slide pedido."""
    assert _titulo_do_slide(DECK, "yt-02") == "A ponte da infraestrutura"
    assert _titulo_do_slide(DECK, "yt-03") == "Estocasticidade em produção"
    assert _titulo_do_slide(DECK, "yt-99") == ""


def test_rotulo_de_categoria_nunca_vira_capitulo():
    """
    `badge-label`/`eyebrow` trazem a categoria, idêntica em todo slide. No
    deck real de 27/08 isso produziu "ENGENHARIA DE IA MODERNA" como capítulo.
    """
    so_categoria = (
        '<section class="slide" id="yt-05">'
        '<div class="badge-label">ENGENHARIA DE IA MODERNA</div></section>'
    )
    assert _titulo_do_slide(so_categoria, "yt-05") == ""


def test_capitulo_declarado_no_slide_tem_precedencia():
    """
    Adivinhar o título por nome de classe é frágil: o slide_designer varia a
    marcação a cada geração, e no deck real de 27/08 TODOS os capítulos
    degradaram para o rótulo genérico do beat. Por isso o slide declara.
    """
    deck = (
        '<section class="slide" id="yt-02">'
        '<div class="wrap" data-capitulo="Vazamento temporal na validação">'
        '<div class="main-title">Outro texto qualquer</div></div></section>'
    )
    assert _titulo_do_slide(deck, "yt-02") == "Vazamento temporal na validação"


def test_beat_desconhecido_nao_vira_continuacao():
    """Linha "Continuação" não ajuda a navegar — melhor não existir."""
    tl = [
        {"slide": None, "beat": "hook",       "start_s": 0.0},
        {"slide": None, "beat": "inexistente", "start_s": 10.0},
        {"slide": None, "beat": "teoria",     "start_s": 20.0},
        {"slide": None, "beat": "resumo",     "start_s": 30.0},
    ]
    saida = montar_capitulos(tl, "")
    assert "Continuação" not in saida
    assert saida.count("—") == 3
