"""
tests/test_gate_duracao.py
===========================
O manifesto tem que respeitar a duração que o próprio prompt manda.

O scriptwriter já pedia 5–12 minutos e segmentos de slide de 25–45s. O vídeo
de 27/08 saiu com 3min29 e slides de 13,5 a 21,4s — porque NADA validava.
`validate_manifest` conferia proporção de avatar, contagem de segmentos e fala
vazia, e nenhuma duração.

O mecanismo de 3 tentativas corretivas já existia. Faltava o que checar.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from manifest_builder import (  # noqa: E402
    DURACAO_MAX_S,
    DURACAO_MIN_S,
    validate_manifest,
)


def _manifesto(segs):
    return {"youtube": {"segments": segs}}


def _seg(sid, kind, dur, script="fala do segmento com palavras suficientes"):
    s = {"id": sid, "kind": kind, "script": script, "min_duration_s": dur}
    if kind == "slide":
        s["slide"] = sid
    return s


def _equilibrado(n_slides, dur_slide, dur_avatar=20):
    """Alterna avatar e slide mantendo a proporção dentro da faixa do produto."""
    segs = [_seg("yt-01", "avatar", dur_avatar)]
    for i in range(n_slides):
        segs.append(_seg(f"yt-s{i}", "slide", dur_slide))
        if i % 3 == 2:
            segs.append(_seg(f"yt-a{i}", "avatar", dur_avatar))
    segs.append(_seg("yt-fim", "avatar", dur_avatar))
    return segs


def test_video_curto_demais_e_recusado():
    """O caso exato de 27/08: 12 segmentos somando 3min29."""
    problemas, stats = validate_manifest(_manifesto(_equilibrado(8, 16)))
    assert stats["total_duration_s"] < DURACAO_MIN_S
    assert any("abaixo do piso" in p for p in problemas)


def test_video_na_faixa_passa():
    problemas, stats = validate_manifest(_manifesto(_equilibrado(14, 32)))
    assert DURACAO_MIN_S <= stats["total_duration_s"] <= DURACAO_MAX_S
    assert not any("piso" in p or "teto" in p for p in problemas), problemas


def test_video_longo_demais_e_recusado():
    problemas, _ = validate_manifest(_manifesto(_equilibrado(30, 40)))
    assert any("acima do teto" in p for p in problemas)


def test_slide_curto_e_recusado_mesmo_com_total_na_faixa():
    """
    Um total dentro da faixa pode esconder muitos slides atropelados. Foi
    assim que o vídeo saiu: cada slide com metade do tempo especificado.
    """
    segs = _equilibrado(24, 14)          # muitos slides curtos, total alto
    problemas, stats = validate_manifest(_manifesto(segs))
    assert stats["total_duration_s"] >= DURACAO_MIN_S
    assert any("curtos demais" in p for p in problemas)


def test_a_mensagem_diz_como_corrigir():
    """
    A nota volta para o modelo numa retentativa. "Alongue" e "não corte o
    assunto" evitam a saída fácil de encher com segmento vazio.
    """
    problemas, _ = validate_manifest(_manifesto(_equilibrado(8, 16)))
    curta = next(p for p in problemas if "abaixo do piso" in p)
    assert "Alongue" in curta and "não corte o assunto" in curta


def test_segmento_sem_duracao_declarada_nao_quebra():
    """`min_duration_s` ausente é estimado pelo texto; não pode levantar."""
    segs = [
        {"id": "yt-01", "kind": "avatar", "script": "palavra " * 40},
        {"id": "yt-02", "kind": "slide", "slide": "yt-02", "script": "palavra " * 90},
    ]
    problemas, _ = validate_manifest(_manifesto(segs))
    assert isinstance(problemas, list)


# ── CTAs ──────────────────────────────────────────────────────────────────────

def _com_ctas(segs):
    """Insere os dois CTAs onde o roteiro real os teria."""
    meio = len(segs) // 2
    return (
        segs[:meio]
        + [_seg("yt-cta", "avatar", 12)]
        + segs[meio:-1]
        + [_seg("yt-art", "avatar", 14), segs[-1]]
    )


def test_roteiro_sem_cta_e_recusado():
    """
    Nenhum dos beats disponíveis era CTA e o roteirista nunca foi instruído a
    criar um — o vídeo fechava no assunto e não convidava a nada.
    """
    problemas, _ = validate_manifest(_manifesto(_equilibrado(14, 32)))
    assert any("cta_meio" in p for p in problemas)
    assert any("cta_artigo" in p for p in problemas)


def test_roteiro_com_os_dois_ctas_passa():
    segs = _com_ctas(_equilibrado(14, 32))
    segs[len(segs) // 2]["beat"] = "cta_meio"
    segs[-2]["beat"] = "cta_artigo"
    problemas, _ = validate_manifest(_manifesto(segs))
    assert not any("cta" in p for p in problemas), problemas


def test_video_nao_pode_terminar_num_pedido():
    """O vídeo fecha no resumo. Terminar pedindo algo desperdiça o fecho."""
    segs = _equilibrado(14, 32)
    segs[len(segs) // 2]["beat"] = "cta_meio"
    segs[-1]["beat"] = "cta_artigo"
    problemas, _ = validate_manifest(_manifesto(segs))
    assert any("termina num pedido" in p for p in problemas)
