"""
tests/test_compose.py
======================
Guardas de regressão do compositor.

Estes testes não rodam FFmpeg — inspecionam o código. Existem porque as
falhas que eles previnem são silenciosas: produzem um vídeo que abre, toca e
parece certo, e só se revela errado quando alguém assiste até o fim.
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared import compose  # noqa: E402


def test_render_de_slide_nao_usa_shortest():
    """
    `-shortest` não é determinístico entre builds do FFmpeg.

    Medido com o MESMO áudio de 10,475s: o binário do macOS cortou o vídeo em
    10,449s, o do container Debian deixou 11,167s — 0,7s de slide congelado
    depois da voz acabar, em cada segmento de ilustração. Num Reel de quatro
    segmentos isso vira quase 3 segundos de tela morta.

    A duração de saída tem que ser explícita (`-t`).
    """
    src = inspect.getsource(compose.render_slide_clip)
    assert '"-shortest"' not in src, "duração do slide precisa ser explícita, não -shortest"
    assert '"-t"' in src


def test_render_de_slide_mede_o_audio_em_vez_de_confiar_na_estimativa():
    """
    `duration_s` chega como `seg.min_duration_s` — o chute do roteirista a 140
    palavras por minuto. Quando o áudio real sai mais longo que o chute,
    gravar pela estimativa cortava a fala no meio.
    """
    src = inspect.getsource(compose.render_slide_clip)
    assert "probe_duration(audio_path)" in src


def test_concat_reencoda_em_vez_de_copiar_streams():
    """
    O concat demuxer com `-c copy` exige parâmetros de codec idênticos e o
    mesmo número de streams. Misturar um MP4 do HeyGen com um WebM convertido
    do Playwright quebrava ali — e o caminho nunca era exercitado porque toda
    produção real até então teve um clipe só.
    """
    src = inspect.getsource(compose.concat_clips)
    assert "concat=n=" in src, "usar o filtro concat, não o demuxer"
    assert "libx264" in src


def test_clipe_mudo_ganha_faixa_de_silencio():
    """
    O concat exige o mesmo número de streams em todas as entradas. Uma cartela
    sem locução derrubava a montagem inteira.
    """
    assert "anullsrc" in inspect.getsource(compose.normalize_clip)


def test_crop_vertical_calcula_a_janela_em_python():
    """
    `min(iw,ih*9/16)` dentro do filtergraph contém uma vírgula, que o parser
    do FFmpeg lê como separador de filtro: o comando morria com
    "No such filter: 'ih*1080/1920):ih:(iw-(min(iw'".
    """
    src = inspect.getsource(compose.crop_to_vertical)
    assert "probe_size(src)" in src
    # Olha a expressão do filtro, não o comentário que explica o bug: a
    # string `min(iw` aparece de propósito na documentação da função.
    vf_line = next(l for l in src.splitlines() if l.strip().startswith('f"crop='))
    assert "min(" not in vf_line, "a janela do crop tem que vir pronta em inteiros"


def test_legenda_e_queimada_com_a_resolucao_original():
    """
    Sem `original_size`, o libass reescala a fonte pela resolução de saída e a
    legenda sai com tamanho diferente do que o PlayResX/PlayResY do ASS pediu.
    """
    src = inspect.getsource(compose.burn_subtitles)
    assert "original_size=" in src
    # O áudio não pode ser recodificado de novo só para queimar legenda.
    assert '"-c:a", "copy"' in src


def test_burn_preserva_o_audio_sem_recodificar():
    assert '"-c:a", "copy"' in inspect.getsource(compose.burn_subtitles)
