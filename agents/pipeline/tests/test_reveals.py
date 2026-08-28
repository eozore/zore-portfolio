"""
tests/test_reveals.py
=====================
As âncoras do manifesto têm que virar movimento no slide.

O manifesto SEMPRE gerou âncoras `reveal` apontando para `fd2`, `fd3` e `fd4`,
e o gravador nunca as executou — o deck nem sequer tinha uma função de
revelar. Esses elementos nascem com `fd-hidden` (display:none) e ficavam
escondidos o clipe inteiro.

O efeito era exatamente a queixa do dono do canal: a ilustração mostrava só o
primeiro bloco enquanto a locução falava do resto, e nada se movia.

O tempo vem do `.alignment.json` que o TTS grava ao lado de cada áudio: tempo
por caractere, então o reveal dispara no instante da frase.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.compose import plano_de_reveals, tempo_da_frase  # noqa: E402

# "Ola mundo. Tudo bem?" com um tempo por caractere.
ALIGN = {
    "characters": list("Ola mundo. Tudo bem?"),
    "character_start_times_seconds": [i * 0.1 for i in range(20)],
    "character_end_times_seconds": [(i + 1) * 0.1 for i in range(20)],
}


def test_encontra_o_instante_da_frase():
    t = tempo_da_frase(ALIGN, "Tudo bem")
    assert t is not None and 1.0 <= t <= 1.4


def test_frase_ausente_devolve_none():
    assert tempo_da_frase(ALIGN, "frase que não está no áudio") is None


def test_sem_alinhamento_devolve_none():
    assert tempo_da_frase(None, "Tudo bem") is None
    assert tempo_da_frase({}, "Tudo bem") is None


def test_ancora_localizada_dispara_no_tempo_da_fala():
    plano = plano_de_reveals(
        [{"on_phrase": "Tudo bem", "action": "reveal", "element": "fd2"}], ALIGN, 10.0,
    )
    assert len(plano) == 1
    t, acao, el = plano[0]
    assert acao == "reveal" and el == "fd2" and 1.0 <= t <= 1.4


def test_ancora_sem_frase_localizavel_ainda_dispara():
    """
    Um reveal no tempo errado é melhor que um elemento que nunca aparece —
    que é o que acontecia com TODOS eles.
    """
    plano = plano_de_reveals(
        [{"on_phrase": "inexistente", "action": "reveal", "element": "fd3"}], ALIGN, 20.0,
    )
    assert len(plano) == 1
    assert 0 < plano[0][0] < 20.0


def test_reveals_saem_em_ordem_cronologica():
    plano = plano_de_reveals(
        [
            {"on_phrase": "Tudo bem", "action": "reveal", "element": "fd3"},
            {"on_phrase": "Ola", "action": "reveal", "element": "fd2"},
        ],
        ALIGN, 10.0,
    )
    assert [e for _, _, e in plano] == ["fd2", "fd3"]
    assert plano[0][0] <= plano[1][0]


def test_ancora_sem_elemento_ou_acao_desconhecida_e_ignorada():
    plano = plano_de_reveals(
        [
            {"on_phrase": "Ola", "action": "reveal"},              # sem element
            {"on_phrase": "Ola", "action": "show_slide", "element": "fd2"},
        ],
        ALIGN, 10.0,
    )
    assert plano == []


def test_distribuicao_fica_no_miolo_do_segmento():
    """
    Nem no primeiro instante (o slide acabou de entrar) nem no fim (ninguém
    veria).
    """
    plano = plano_de_reveals(
        [{"on_phrase": "x", "action": "reveal", "element": f"fd{i}"} for i in (2, 3, 4)],
        None, 20.0,
    )
    tempos = [t for t, _, _ in plano]
    assert all(20.0 * 0.2 <= t <= 20.0 * 0.9 for t in tempos), tempos


def test_renderizador_agenda_os_reveals_antes_do_replay():
    """
    A ordem importa: os timers têm que começar a contar junto com a animação,
    não depois dela.
    """
    import inspect

    from shared import compose

    src = inspect.getsource(compose.render_slide_clip)
    assert src.index("plano_de_reveals") < src.index("deckAPI.replay")
