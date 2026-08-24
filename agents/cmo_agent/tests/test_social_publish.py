# -*- coding: utf-8 -*-
"""
Cobertura da conversão `plano_social` → documentos de `social_queue`.

Por que existe: este é o ponto onde o conteúdo deixa de ser preview e vira
publicação sob a marca do dono do canal. Um mapeamento errado aqui não dá
erro — dá post publicado errado. Em particular:

  - thread sem a raiz publica a resposta como se fosse o post principal;
  - story com 4 frames num documento só publica 1 e descarta 3 em silêncio;
  - carrossel sem imagem é recusado pelo Instagram no momento da publicação,
    dias depois de qualquer chance de perceber;
  - peça agendada para D+0 sai antes do vídeo que ela promete.
"""

from datetime import datetime, timezone

import pytest

from social_publish import (
    BRT_OFFSET_HOURS,
    MINUTOS_ENTRE_FRAMES,
    SLOTS_BRT,
    montar_itens,
)

BASE = datetime(2026, 8, 23, 10, 0, 0, tzinfo=timezone.utc)


def _plano(**over):
    plano = {
        "linkedin": [{
            "id": "li-01", "gancho": "Gancho", "corpo": "Corpo",
            "hashtags": ["ia", "ml"], "comentario_fixado": "[LINK_ARTIGO]",
            "dia_offset": 1,
        }],
        "threads": [{"id": "th-01", "gancho": "Raiz", "posts": ["r1", "r2"], "dia_offset": 2}],
        "carrossel": [{
            "id": "ca-01", "gancho": "Gancho", "legenda": "Legenda", "dia_offset": 3,
            "slides": [
                {"numero": 2, "titulo": "T2", "corpo": "C2"},
                {"numero": 1, "titulo": "T1", "corpo": "C1"},
            ],
        }],
        "stories": [{
            "id": "st-01", "gancho": "Story", "dia_offset": 4,
            "frames": [
                {"ordem": 2, "texto": "F2", "ilustracao": "b",
                 "enquete": "Você já mediu isso?"},
                {"ordem": 1, "texto": "F1", "ilustracao": "a"},
            ],
        }],
        "youtube_community": [{
            "id": "yc-01", "gancho": "G", "texto": "Texto",
            "enquete_opcoes": ["a", "b"], "dia_offset": 5,
        }],
    }
    plano.update(over)
    return plano


def montar(**over):
    return montar_itens(
        _plano(**over),
        artigo_slug="meu-post",
        artigo_titulo="Meu post",
        artigo_url="https://eozore.com/pt-BR/blog/meu-post",
        serie="ia-para-lideres",
        session_id="s1",
        base=BASE,
    )


def por_canal(itens, platform, fmt=None):
    return [i for i in itens if i["platform"] == platform and (fmt is None or i["format"] == fmt)]


# ── Mapeamento de canal ───────────────────────────────────────────────────────

def test_cada_canal_vira_o_par_platform_format_que_o_publisher_conhece():
    itens = montar()
    pares = {(i["platform"], i["format"]) for i in itens}
    assert pares == {
        ("linkedin", "text"),
        ("threads", "thread"),
        ("instagram", "carousel"),
        ("instagram", "story"),
        ("youtube_community", "text"),
    }


def test_thread_leva_a_raiz_como_primeiro_post():
    # publish_thread_series posta a lista na ordem. Sem a raiz, a primeira
    # resposta vira o post principal e a thread perde o gancho.
    (t,) = por_canal(montar(), "threads")
    assert t["thread_posts"] == ["Raiz", "r1", "r2"]


def test_linkedin_mantem_o_link_fora_do_corpo():
    (p,) = por_canal(montar(), "linkedin")
    assert p["comentario_fixado"] == "[LINK_ARTIGO]"
    assert "[LINK_ARTIGO]" not in p["copy"]


def test_linkedin_anexa_as_hashtags_ao_corpo():
    (p,) = por_canal(montar(), "linkedin")
    assert p["copy"].endswith("#ia #ml")


def test_enquete_da_comunidade_entra_no_corpo_do_post():
    # A API do YouTube não expõe Community Posts: o publisher marca como
    # manual, então as opções precisam estar no texto para serem recriadas.
    (p,) = por_canal(montar(), "youtube_community")
    assert "• a" in p["copy"] and "• b" in p["copy"]


# ── Imagens ───────────────────────────────────────────────────────────────────

def test_carrossel_pede_uma_imagem_por_slide_na_ordem_do_numero():
    (c,) = por_canal(montar(), "instagram", "carousel")
    assert [r["nome"] for r in c["_render"]] == ["carrossel_ca-01_1", "carrossel_ca-01_2"]
    # Ordenado por `numero`, não pela ordem em que o modelo devolveu.
    assert "T1" in c["_render"][0]["html"]
    assert "T2" in c["_render"][1]["html"]


def test_cada_frame_de_story_vira_um_documento_com_sua_propria_imagem():
    frames = por_canal(montar(), "instagram", "story")
    assert len(frames) == 2
    assert [len(f["_render"]) for f in frames] == [1, 1]
    assert "F1" in frames[0]["_render"][0]["html"]
    assert "F2" in frames[1]["_render"][0]["html"]


def test_enquete_do_frame_e_renderizada_como_pergunta():
    # `enquete` é a pergunta inteira (FrameStory), não opções separadas por
    # '|'. Tratá-la como lista imprimia a pergunta dentro de um único botão.
    frames = por_canal(montar(), "instagram", "story")
    assert "Você já mediu isso?" in frames[1]["_render"][0]["html"]


def test_peca_de_texto_nao_pede_render():
    for canal in ("linkedin", "threads", "youtube_community"):
        for item in por_canal(montar(), canal):
            assert "_render" not in item or not item["_render"]


def test_carrossel_sem_slide_nao_entra_na_fila():
    # Instagram recusa carrossel sem mídia; melhor não enfileirar do que
    # falhar dias depois no publisher.
    itens = montar(carrossel=[{"id": "ca-x", "legenda": "L", "dia_offset": 1, "slides": []}])
    assert por_canal(itens, "instagram", "carousel") == []


def test_story_sem_frame_nao_entra_na_fila():
    itens = montar(stories=[{"id": "st-x", "gancho": "G", "dia_offset": 1, "frames": []}])
    assert por_canal(itens, "instagram", "story") == []


# ── Agenda ────────────────────────────────────────────────────────────────────

def _hora_brt(iso: str) -> int:
    return datetime.fromisoformat(iso).hour - BRT_OFFSET_HOURS


def test_nada_e_agendado_para_o_mesmo_dia_do_video():
    # O vídeo é a âncora e sai primeiro. Uma peça em D+0 promete um vídeo que
    # ainda não existe.
    itens = montar(linkedin=[{"id": "li-x", "gancho": "G", "corpo": "C",
                              "hashtags": [], "dia_offset": 0}])
    (p,) = por_canal(itens, "linkedin")
    assert datetime.fromisoformat(p["scheduled_at"]).date() > BASE.date()


def test_dia_offset_do_modelo_e_respeitado():
    itens = montar()
    dia = {i["platform"]: datetime.fromisoformat(i["scheduled_at"]).day for i in itens}
    assert dia["linkedin"] == BASE.day + 1
    assert dia["threads"] == BASE.day + 2


def test_pecas_do_mesmo_dia_ocupam_slots_diferentes():
    # Sem isto, três posts do mesmo dia saem todos às 9h e o publisher despeja
    # a campanha inteira numa execução.
    itens = montar(
        linkedin=[
            {"id": f"li-{n}", "gancho": "G", "corpo": "C", "hashtags": [], "dia_offset": 1}
            for n in range(3)
        ],
        threads=[], carrossel=[], stories=[], youtube_community=[],
    )
    assert sorted(_hora_brt(i["scheduled_at"]) for i in itens) == sorted(SLOTS_BRT)


def test_frames_do_mesmo_story_saem_em_sequencia():
    frames = por_canal(montar(), "instagram", "story")
    t0 = datetime.fromisoformat(frames[0]["scheduled_at"])
    t1 = datetime.fromisoformat(frames[1]["scheduled_at"])
    assert (t1 - t0).total_seconds() == MINUTOS_ENTRE_FRAMES * 60


# ── Contrato com o publisher ──────────────────────────────────────────────────

CAMPOS_OBRIGATORIOS = {
    "platform", "format", "title", "copy", "scheduled_at", "status",
    "article_slug", "article_title", "article_url", "language",
    "thread_posts", "image_url", "video_url", "asset_urls",
    "session_id", "retry_count", "error_message", "published_at",
    "platform_post_id", "created_at", "updated_at",
}


@pytest.mark.parametrize("item", montar())
def test_todo_item_traz_os_campos_que_o_publisher_le(item):
    assert CAMPOS_OBRIGATORIOS <= set(item)
    assert item["status"] == "planned"
    assert item["retry_count"] == 0
    assert item["published_at"] is None


def test_url_do_artigo_viaja_com_cada_item():
    # É o que resolve [LINK_ARTIGO] no momento da publicação, dias depois,
    # quando a sessão do Studio já pode ter sido descartada.
    for item in montar():
        assert item["article_url"] == "https://eozore.com/pt-BR/blog/meu-post"
