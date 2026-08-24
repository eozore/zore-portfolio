"""
tests/test_captions.py
=======================
Cobertura de shared.captions — legendas queimadas na peça vertical.

Por que existe: a maior parte do público de Reels/Shorts assiste sem som, e o
corte vertical do CSM saía sem legenda nenhuma. Os tempos vêm do alinhamento
por caractere que o ElevenLabs devolve junto com o áudio (endpoint
/with-timestamps) — não de ASR sobre o áudio já gerado.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.captions import (  # noqa: E402
    ASS_BRAND_ORANGE,
    ASS_WHITE,
    CUE_BREAK_GAP_S,
    MAX_CUE_CHARS,
    WordTiming,
    build_ass,
    group_into_cues,
    words_from_alignment,
    words_from_text_estimated,
)


def _alignment(text: str, per_char_s: float = 0.06) -> dict:
    """Constrói um alinhamento no formato exato do ElevenLabs."""
    chars, starts, ends = [], [], []
    t = 0.0
    for ch in text:
        chars.append(ch)
        starts.append(round(t, 4))
        t += per_char_s
        ends.append(round(t, 4))
    return {
        "characters": chars,
        "character_start_times_seconds": starts,
        "character_end_times_seconds": ends,
    }


# ── Alinhamento → palavras ────────────────────────────────────────────────────

def test_caracteres_viram_palavras_com_tempos_reais():
    words = words_from_alignment(_alignment("Testes A/B agora"))
    assert [w.text for w in words] == ["Testes", "A/B", "agora"]
    # O início da primeira palavra é o início do primeiro caractere.
    assert words[0].start_s == pytest.approx(0.0)
    # "Testes" = 6 chars * 0.06
    assert words[0].end_s == pytest.approx(0.36, abs=0.001)
    # A palavra seguinte começa depois do espaço, não colada no fim da anterior.
    assert words[1].start_s > words[0].end_s


def test_pontuacao_fica_colada_na_palavra():
    # Separar "morreram." em "morreram" + "." faria um ponto solto piscar na
    # tela como se fosse uma palavra própria.
    words = words_from_alignment(_alignment("não morreram."))
    assert [w.text for w in words] == ["não", "morreram."]


def test_alinhamento_inconsistente_nao_derruba_o_job():
    # O job de vídeo não pode morrer por causa de legenda: sem alinhamento
    # utilizável ele cai na estimativa por texto.
    assert words_from_alignment({
        "characters": ["a", "b"],
        "character_start_times_seconds": [0.0],
        "character_end_times_seconds": [0.1, 0.2],
    }) == []
    assert words_from_alignment({}) == []


def test_espacos_multiplos_nao_geram_palavras_vazias():
    words = words_from_alignment(_alignment("um   dois"))
    assert [w.text for w in words] == ["um", "dois"]


# ── Palavras → cues ───────────────────────────────────────────────────────────

def test_pausa_na_fala_quebra_a_cue():
    # A respiração do apresentador é limite de cue: legenda que atravessa a
    # pausa parece fatiada por contador de caracteres, não editada.
    words = [
        WordTiming("um", 0.0, 0.30),
        WordTiming("dois", 0.35, 0.60),
        WordTiming("três", 0.60 + CUE_BREAK_GAP_S + 0.1, 2.30),
    ]
    cues = group_into_cues(words)
    assert [c.text for c in cues] == ["um dois", "três"]


def test_cue_respeita_limite_de_caracteres():
    words = [WordTiming("palavra", i * 0.3, i * 0.3 + 0.25) for i in range(10)]
    for cue in group_into_cues(words):
        assert len(cue.text) <= MAX_CUE_CHARS


def test_cue_respeita_limite_de_palavras():
    # Palavras curtas e rápidas não podem encher a tela só porque cabem nos
    # caracteres.
    words = [WordTiming("ok", i * 0.1, i * 0.1 + 0.08) for i in range(12)]
    for cue in group_into_cues(words):
        assert len(cue.words) <= 5


def test_cue_preserva_a_ordem_e_nao_perde_palavras():
    words = [WordTiming(f"p{i}", i * 0.4, i * 0.4 + 0.3) for i in range(11)]
    cues = group_into_cues(words)
    recomposto = " ".join(c.text for c in cues).split()
    assert recomposto == [w.text for w in words]


def test_lista_vazia_nao_gera_cue():
    assert group_into_cues([]) == []


# ── Cues → ASS ────────────────────────────────────────────────────────────────

def test_ass_declara_a_resolucao_do_vídeo():
    ass = build_ass(group_into_cues(words_from_alignment(_alignment("oi mundo"))), 1080, 1920)
    assert "PlayResX: 1080" in ass
    assert "PlayResY: 1920" in ass


def test_karaoke_acende_a_palavra_falada_e_nao_o_contrário():
    # No ASS, SecondaryColour é a cor ANTES da sílaba e PrimaryColour DEPOIS.
    # Primary tem que ser a cor de destaque: a palavra entra branca e acende
    # em laranja ao ser dita. Invertido, ela nasceria destacada e apagaria —
    # o olho seguiria o texto que ainda não foi falado.
    ass = build_ass(group_into_cues(words_from_alignment(_alignment("oi"))), 1080, 1920)
    style = next(l for l in ass.splitlines() if l.startswith("Style: Legenda"))
    campos = style.split(",")
    assert campos[3] == ASS_BRAND_ORANGE, "PrimaryColour (depois de falado) = destaque"
    assert campos[4] == ASS_WHITE, "SecondaryColour (antes de falado) = neutro"


def test_karaoke_cobre_a_pausa_entre_palavras():
    # O \k de cada palavra vai até o INÍCIO da próxima, não até o próprio fim:
    # senão o destaque apaga durante a pausa e o efeito pisca.
    words = [WordTiming("um", 0.0, 0.20), WordTiming("dois", 0.50, 0.70)]
    ass = build_ass([group_into_cues(words)[0]], 1080, 1920)
    dialogue = next(l for l in ass.splitlines() if l.startswith("Dialogue:"))
    # 0.50 - 0.0 = 0.5s = 50 centésimos, não 20.
    assert "{\\k50}um" in dialogue


def test_chaves_no_script_nao_quebram_o_ass():
    # `{` e `}` delimitam tags de override — um script com JSON falado ou
    # código apagaria o resto da linha silenciosamente.
    ass = build_ass(group_into_cues([WordTiming("{payload}", 0.0, 1.0)]), 1080, 1920)
    assert "\\{payload\\}" in ass


def test_legenda_fica_acima_da_ui_das_plataformas():
    # Instagram e TikTok desenham a própria UI sobre os ~15% de baixo.
    ass = build_ass(group_into_cues([WordTiming("oi", 0, 1)]), 1080, 1920)
    style = next(l for l in ass.splitlines() if l.startswith("Style: Legenda"))
    margin_v = int(style.split(",")[-2])
    assert margin_v >= 1920 * 0.15


def test_fonte_escala_com_a_altura_do_video():
    vertical   = build_ass(group_into_cues([WordTiming("oi", 0, 1)]), 1080, 1920)
    horizontal = build_ass(group_into_cues([WordTiming("oi", 0, 1)]), 1920, 1080)
    tam_v = int(next(l for l in vertical.splitlines() if l.startswith("Style:")).split(",")[2])
    tam_h = int(next(l for l in horizontal.splitlines() if l.startswith("Style:")).split(",")[2])
    assert tam_v > tam_h


def test_modo_sem_destaque_nao_emite_tags_de_karaoke():
    ass = build_ass(
        group_into_cues(words_from_alignment(_alignment("oi mundo"))),
        1080, 1920, highlight=False,
    )
    assert "\\k" not in ass


# ── Fallback sem alinhamento ──────────────────────────────────────────────────

def test_estimativa_cobre_exatamente_a_duracao_do_audio():
    # Projetos cujo áudio foi gerado antes do /with-timestamps caem aqui.
    words = words_from_text_estimated("uma frase de teste completa", 5.0)
    assert words[0].start_s == pytest.approx(0.0)
    assert words[-1].end_s == pytest.approx(5.0, abs=0.01)


def test_estimativa_da_mais_tempo_a_palavra_mais_longa():
    words = words_from_text_estimated("a palavraenorme", 4.0)
    curta, longa = words[0], words[1]
    assert (longa.end_s - longa.start_s) > (curta.end_s - curta.start_s)


def test_estimativa_com_texto_vazio_ou_duracao_zero():
    assert words_from_text_estimated("", 5.0) == []
    assert words_from_text_estimated("oi", 0.0) == []


# ── Deslocamento na linha do tempo da peça montada ────────────────────────────

def test_shifted_desloca_sem_mutar_o_original():
    # O corte vertical junta N clipes; cada um traz tempos começando em zero e
    # precisa ser deslocado pela posição do clipe. Mutar o original faria o
    # segundo uso do mesmo clipe sair deslocado duas vezes.
    w = WordTiming("oi", 1.0, 2.0)
    s = w.shifted(10.0)
    assert (s.start_s, s.end_s) == (11.0, 12.0)
    assert (w.start_s, w.end_s) == (1.0, 2.0)
