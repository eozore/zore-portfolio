"""
Cobertura dos templates de imagem social.

Estes templates existem porque carrossel e stories não vinham com HTML nenhum
do distribution_agent — eram gerados, exibidos na revisão e descartados na
aprovação, porque o Instagram rejeita post sem mídia.

Como o HTML daqui vira imagem pública sob a marca do usuário, os testes travam
o que já quebrou antes: paleta fora da marca (a geração por LLM chegou a usar o
tema escuro do GitHub) e HTML malformado por texto não escapado.
"""

import re

import pytest

from shared.social_images import (
    ACCENT, BG, CAROUSEL_SIZE, STORY_SIZE, TEXT,
    carousel_slide_html, fallback_image_html, story_html,
)

BRAND = {BG.lower(), "#151920", TEXT.lower(), "#8a8378", ACCENT.lower(), "#f5b56a"}
GITHUB_DARK = {"#0d1117", "#58a6ff", "#c9d1d9", "#30363d", "#8b949e"}


def cores(html: str) -> set[str]:
    return {c.lower() for c in re.findall(r"#[0-9a-fA-F]{6}", html)}


# ── Paleta ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("html", [
    carousel_slide_html("Título", "Corpo do slide", 1, 6, "serie-teste"),
    story_html("Texto do story", "Sim | Não", "Quiz"),
    fallback_image_html("Título", "Corpo", 1080, 1080),
])
def test_so_usa_cores_da_marca(html):
    fora = cores(html) - BRAND
    assert not fora, f"cores fora da marca: {sorted(fora)}"


@pytest.mark.parametrize("html", [
    carousel_slide_html("t", "b", 1, 3),
    story_html("c", "", ""),
])
def test_nunca_usa_o_tema_do_github(html):
    # Foi o default que o modelo escolhia sozinho quando o prompt não definia paleta.
    assert not (cores(html) & GITHUB_DARK)


# ── Dimensões ─────────────────────────────────────────────────────────────────

def test_carrossel_e_quadrado_1080():
    html = carousel_slide_html("t", "b", 1, 4)
    assert f"width:{CAROUSEL_SIZE[0]}px" in html and f"height:{CAROUSEL_SIZE[1]}px" in html


def test_story_e_vertical_9x16():
    html = story_html("c")
    assert f"width:{STORY_SIZE[0]}px" in html and f"height:{STORY_SIZE[1]}px" in html


# ── Conteúdo ──────────────────────────────────────────────────────────────────

def test_carrossel_mostra_posicao_na_sequencia():
    # Sem contador o leitor não sabe que há mais slides, e o swipe despenca.
    assert "3/7" in carousel_slide_html("t", "b", 3, 7)


def test_carrossel_preserva_quebras_de_linha_do_corpo():
    html = carousel_slide_html("t", "1. um\n2. dois\n3. três", 1, 2)
    assert html.count("<br>") == 2   # listas numeradas do agente não podem colapsar


def test_story_renderiza_opcoes_de_quiz_como_botoes():
    html = story_html("Pergunta?", "Sim | Não, ele apenas prediz texto", "Quiz")
    assert "Sim" in html and "Não, ele apenas prediz texto" in html


def test_story_sem_elemento_interativo_nao_quebra():
    html = story_html("Só texto", "", "Dica")
    assert "Só texto" in html and "<body" in html


# ── Segurança do HTML ─────────────────────────────────────────────────────────

def test_escapa_html_do_texto_gerado():
    # O texto vem de LLM; um "<" solto quebraria o layout inteiro na renderização.
    html = carousel_slide_html("A < B & C", "if x > 1: pass", 1, 2)
    assert "&lt;" in html and "&amp;" in html
    assert "A < B & C" not in html


def test_nao_carrega_recurso_externo():
    # O renderer roda offline no Cloud Run; fonte ou imagem externa trava o load.
    html = carousel_slide_html("t", "b", 1, 2)
    assert "http://" not in html and "https://" not in html
    assert "<script" not in html.lower()
