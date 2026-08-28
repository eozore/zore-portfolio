"""
Cobertura da regra do produto: todo vídeo alterna avatar e ilustração.

Por que existe: no primeiro ciclo real de produção o roteiro de 8 segmentos
com 7 ilustrações chegou à pipeline como 1 segmento sem ilustração nenhuma —
`pipeline-submit` mandava a fala concatenada em texto puro e o cmo_agent
reparseava. O resultado foi 163 segundos de avatar puro, US$ 5,47 de HeyGen
onde o correto seria menos de um dólar, e zero apoio visual ao conteúdo
técnico. Nada no caminho checou as contagens antes de gastar o crédito.

O gate agora roda em `validate_manifest`, ANTES de publicar a
PackageApprovedMsg. Falhar ali custa zero.
"""

import sys
from pathlib import Path

import pytest

# manifest_builder mora no cmo_agent, que não é pacote da pipeline.
sys.path.insert(
    0, str(Path(__file__).resolve().parents[3] / "agents" / "cmo_agent")
)

from manifest_builder import manifest_stats, validate_manifest  # noqa: E402

from shared.models import Manifest, Segment  # noqa: E402


def seg(sid, kind, dur, slide=None, script="palavra " * 40):
    return {
        "id": sid, "kind": kind, "slide": slide, "beat": "teoria",
        "script": script.strip(), "min_duration_s": dur, "anchors": [],
    }


def manifesto(segments, vertical_cut=None):
    return {
        "version": 2, "video_id": "v", "title": "t", "language": "pt-BR",
        "youtube": {"deck": "yt", "resolution": {"width": 1920, "height": 1080},
                    "segments": segments},
        "vertical_cut": vertical_cut or {"segments": []},
    }


# ── Um vídeo bem formado ─────────────────────────────────────────────────────
#
# A definição mudou em 28/08 e esta fixture mudou junto. O manifesto anterior
# somava 3min25 e não tinha CTA nenhum — era exatamente o formato do vídeo que
# foi para produção e motivou as duas novas regras: duração de 5 a 12 minutos,
# e os dois CTAs obrigatórios. Manter a fixture antiga seria congelar no teste
# o defeito que as regras existem para impedir.

def seg_beat(sid, kind, dur, slide=None, beat="teoria"):
    s = seg(sid, kind, dur, slide)
    s["beat"] = beat
    return s


BEM_FORMADO = manifesto([
    seg_beat("yt-01", "avatar", 18.0, beat="hook"),
    seg_beat("yt-02", "slide",  38.0, "yt-02"),
    seg_beat("yt-03", "slide",  40.0, "yt-03"),
    seg_beat("yt-04", "avatar", 15.0),
    seg_beat("yt-05", "slide",  42.0, "yt-05"),
    seg_beat("yt-06", "slide",  36.0, "yt-06"),
    seg_beat("yt-07", "avatar", 12.0, beat="cta_meio"),
    seg_beat("yt-08", "slide",  40.0, "yt-08"),
    seg_beat("yt-09", "slide",  38.0, "yt-09"),
    seg_beat("yt-10", "avatar", 16.0),
    seg_beat("yt-11", "slide",  36.0, "yt-11"),
    seg_beat("yt-12", "avatar", 14.0, beat="cta_artigo"),
    seg_beat("yt-13", "avatar", 16.0, beat="resumo"),
])


def test_manifesto_bem_formado_passa():
    violacoes, stats = validate_manifest(BEM_FORMADO)
    assert violacoes == [], violacoes
    assert stats["segment_count"] == 13
    # 6 de avatar: gancho, duas reentradas, os dois CTAs e o fecho. Os CTAs
    # são avatar de propósito — pedido feito de cara limpa funciona, em cima
    # de um slide não.
    assert stats["avatar_segments"] == 6
    assert stats["slide_segments"] == 7
    # 91s de avatar em 361s ≈ 25%, dentro do alvo de 20%.
    assert 0.15 <= stats["avatar_share"] <= 0.30
    # E dentro da faixa de duração, que é o que a fixture antiga violava.
    assert 300 <= stats["total_duration_s"] <= 720


# ── O que quebrou em produção ─────────────────────────────────────────────────

def test_manifesto_colapsado_em_um_segmento_e_recusado():
    # Exatamente o manifesto que a pipeline recebeu em 16/08: um segmento de
    # 178,3s, sem slide, gerado pelo parser de Markdown sobre texto plano.
    achatado = manifesto([seg("seg_001", "avatar", 178.3)])
    violacoes, stats = validate_manifest(achatado)

    assert stats["segment_count"] == 1
    assert stats["slide_segments"] == 0
    assert stats["avatar_share"] == 1.0
    assert any("colapsado" in v for v in violacoes)
    assert any("ilustração" in v for v in violacoes)
    assert any("teto" in v for v in violacoes)


def test_video_sem_ilustracao_e_recusado_mesmo_com_varios_segmentos():
    # Vários segmentos não bastam: se todos forem avatar, o custo explode e o
    # conteúdo técnico fica sem apoio visual.
    so_avatar = manifesto([seg(f"yt-{i:02d}", "avatar", 20.0) for i in range(1, 6)])
    violacoes, _ = validate_manifest(so_avatar)
    assert any("100% avatar" in v or "ilustração" in v for v in violacoes)


def test_video_sem_apresentador_e_recusado():
    # O oposto também viola a regra: uma apresentação sem ninguém na tela.
    so_slides = manifesto([
        seg(f"yt-{i:02d}", "slide", 30.0, f"yt-{i:02d}") for i in range(1, 6)
    ])
    violacoes, stats = validate_manifest(so_slides)
    assert stats["avatar_segments"] == 0
    assert any("sem apresentador" in v for v in violacoes)


def test_avatar_acima_do_teto_e_recusado():
    # 60% de avatar: tecnicamente alterna, mas o custo é o de um talking head.
    caro = manifesto([
        seg("yt-01", "avatar", 60.0),
        seg("yt-02", "slide",  40.0, "yt-02"),
    ])
    violacoes, stats = validate_manifest(caro)
    assert stats["avatar_share"] == 0.6
    assert any("teto" in v for v in violacoes)


def test_segmento_sem_fala_e_reportado_com_o_id():
    mudo = manifesto([
        seg("yt-01", "avatar", 18.0),
        seg("yt-02", "slide",  38.0, "yt-02", script=""),
    ])
    violacoes, _ = validate_manifest(mudo)
    assert any("yt-02" in v for v in violacoes)


# ── Só segmento de avatar consome HeyGen ──────────────────────────────────────

def test_apenas_segmentos_de_avatar_vao_para_o_heygen():
    m = Manifest(
        version=2, video_id="v", title="t", language="pt-BR",
        youtube=BEM_FORMADO["youtube"], reels=[],
    )
    heygen = [s.id for s in m.get_heygen_segments("horizontal")]
    slides = [s.id for s in m.get_slide_with_audio_segments("horizontal")]

    assert heygen == ["yt-01", "yt-04", "yt-07", "yt-10", "yt-12", "yt-13"]
    assert slides == ["yt-02", "yt-03", "yt-05", "yt-06", "yt-08", "yt-09", "yt-11"]
    # Toda fala vira áudio TTS, inclusive a dos segmentos de ilustração.
    assert len(m.get_tts_segments("horizontal")) == 13


def test_kind_ausente_e_derivado_do_slide():
    # Manifestos gerados antes do campo `kind` continuam funcionando.
    antigo = {"id": "yt-02", "script": "fala", "beat": "intro", "slide": "yt-02"}
    assert Segment.from_raw(antigo).kind == "slide"
    assert Segment.from_raw(antigo).needs_heygen is False

    hook = {"id": "yt-01", "script": "fala", "beat": "hook", "slide": None}
    assert Segment.from_raw(hook).kind == "avatar"
    assert Segment.from_raw(hook).needs_heygen is True


# ── O corte vertical aponta para o vídeo longo, não tem roteiro próprio ───────

def test_corte_vertical_referencia_segmentos_do_video_longo():
    m = Manifest(
        version=2, video_id="v", title="t", language="pt-BR",
        youtube=BEM_FORMADO["youtube"], reels=[],
        vertical_cut={
            "resolution": {"width": 1080, "height": 1920},
            "segments": [
                {"id": "v-01", "source": "yt-01", "kind": "avatar", "slide": None,
                 "script": "fala", "min_duration_s": 18.0},
                {"id": "v-02", "source": "yt-05", "kind": "slide", "slide": "v-02",
                 "script": "fala", "min_duration_s": 42.0},
            ],
        },
    )
    itens = [Segment.from_raw(s) for s in m._get_raw_segments("vertical")]

    assert [i.source for i in itens] == ["yt-01", "yt-05"]
    # Todo item aponta para um segmento que existe no vídeo horizontal — é o
    # que permite reaproveitar o clipe de avatar e o áudio já gerados.
    for item in itens:
        assert m.segment_by_id(item.source) is not None
    # O item de avatar não tem slide: ele é um crop do clipe horizontal.
    assert itens[0].kind == "avatar" and itens[0].slide is None
    # O de ilustração tem um slide PRÓPRIO, desenhado para 9:16.
    assert itens[1].slide == "v-02"
    assert m.vertical_resolution() == {"width": 1080, "height": 1920}


def test_manifesto_sem_vertical_cut_nao_quebra():
    m = Manifest(
        version=2, video_id="v", title="t", language="pt-BR",
        youtube=BEM_FORMADO["youtube"], reels=[],
    )
    assert m._get_raw_segments("vertical") == []


# ── Estatísticas usadas no gate e nos logs ────────────────────────────────────

def test_stats_estima_duracao_quando_o_manifesto_nao_traz():
    sem_duracao = manifesto([
        {"id": "yt-01", "kind": "avatar", "slide": None, "beat": "hook",
         "script": " ".join(["palavra"] * 140)},
    ])
    stats = manifest_stats(sem_duracao)
    # 140 palavras a 140 wpm = 60s.
    assert stats["total_duration_s"] == pytest.approx(60.0, abs=1.0)
