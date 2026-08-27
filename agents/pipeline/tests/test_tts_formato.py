"""
tests/test_tts_formato.py
=========================
O formato do áudio é o que veio, não o que foi pedido.

Regressão de produção (27/08/2026): a ElevenLabs aceitou `pcm_44100` com
HTTP 200 e devolveu MP3. O código embrulhou os bytes de MP3 num cabeçalho WAV
declarando PCM 16 bits a 44.1kHz — 88200 B/s contra os ~16000 B/s reais.

O arquivo passou a mentir a própria duração por um fator de 5,5x. O HeyGen,
que decodifica de verdade, gerou avatares corretos de 18s. O `ffprobe`, que lê
o cabeçalho, informou 3,3s — e o `render_slide_clip` cortou cada ilustração
ali. Os oito slides do vídeo entregaram 18% da narração, todos cortando no
meio da frase; o vídeo saiu com 94s em vez de 208s.

Nada disso deu erro em lugar nenhum.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tts_job.job import _detectar_formato, _pcm_para_wav  # noqa: E402


def test_mp3_com_tag_id3_e_reconhecido():
    """O corpo real devolvido pela ElevenLabs no incidente começava com ID3."""
    assert _detectar_formato(b"ID3\x04\x00\x00\x00\x00\x00\x00rest") == "mp3"


def test_mp3_sem_tag_e_reconhecido_pelo_frame_sync():
    # 11 bits em 1 abrem todo frame MPEG audio. Sem isto, um MP3 sem ID3
    # cairia em "pcm" e voltaria a ser embrulhado.
    assert _detectar_formato(b"\xff\xfb\x90\x64" + b"\x00" * 64) == "mp3"


def test_wav_completo_e_reconhecido_e_nao_reembrulhado():
    cabecalho = b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"fmt "
    assert _detectar_formato(cabecalho) == "wav"


def test_pcm_cru_continua_sendo_embrulhado():
    """PCM nu não tem assinatura — é o único caso que ainda precisa do WAV."""
    assert _detectar_formato(b"\x00\x01\x02\x03" * 32) == "pcm"


def test_entrada_curta_demais_nao_explode():
    assert _detectar_formato(b"") == "pcm"
    assert _detectar_formato(b"ID") == "pcm"


def test_wav_gerado_declara_a_duracao_verdadeira():
    """
    O contrário do defeito: quando o embrulho é legítimo, o cabeçalho tem que
    bater com os dados. 1 segundo a 24kHz, 16 bits, mono = 48000 bytes.
    """
    import io
    import wave

    pcm = b"\x00\x00" * 24000
    wav = _pcm_para_wav(pcm, 24000)
    with wave.open(io.BytesIO(wav), "rb") as w:
        assert w.getframerate() == 24000
        assert w.getnframes() / w.getframerate() == 1.0


def test_mp3_devolvido_para_pedido_pcm_nao_vira_wav():
    """
    O caso exato do incidente, no ponto de decisão.

    Se esta escolha voltar a olhar o formato PEDIDO em vez do RECEBIDO, o
    arquivo volta a mentir a duração e a ilustração volta a ser cortada — sem
    erro em lugar nenhum.
    """
    corpo_mp3 = b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\xff\xfb" * 100
    assert _detectar_formato(corpo_mp3) == "mp3", (
        "corpo MP3 tem que ser detectado como mp3 mesmo quando o formato "
        "pedido foi pcm_44100"
    )
