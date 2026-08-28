"""
tests/test_link_social.py
=========================
Toda peça social sai com link — quando a plataforma sabe renderizá-lo.

As 51 peças do ciclo de 27/08 foram para a fila sem link NENHUM: nem do
vídeo, nem do artigo. A maquinaria de resolução existia e estava certa
(`_video_url_for` busca o id do YouTube no momento da publicação), mas ela só
age se o marcador `[LINK_CANAL]` estiver no texto — e o modelo emitiu marcador
em UMA das 51.

Pedir o marcador ao modelo é sugestão. Isto é a garantia.

A ordem vídeo → artigo → canal existe porque o vídeo é o item mais demorado do
ciclo: o plano social é enfileirado logo depois do gate, e o vídeo fica pronto
horas ou dias depois. Congelar o link no enfileiramento gravaria
`video_url: None` para sempre.
"""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from publisher_job.job import PublisherJob  # noqa: E402

VIDEO = "https://youtu.be/abc123"
ARTIGO = "https://eozore.com/pt-BR/blog/harness"


def _job(video: str | None = VIDEO) -> PublisherJob:
    j = object.__new__(PublisherJob)
    j._video_url_cache = {}
    j._video_url_for = lambda *_a, **_k: video      # type: ignore[method-assign]
    return j


def base(**extra):
    return {"session_id": "s1", "article_url": ARTIGO, **extra}


def test_linkedin_ganha_o_link_no_primeiro_comentario():
    """No corpo o link derruba o alcance; o lugar é o primeiro comentário."""
    d = _job()._garantir_link(base(copy="Post sem link."), "linkedin")
    assert VIDEO in d["comentario_fixado"]
    assert VIDEO not in d["copy"]


def test_linkedin_com_comentario_sem_link_preserva_o_texto():
    d = _job()._garantir_link(
        base(copy="x", comentario_fixado="Comento aqui embaixo."), "linkedin",
    )
    assert "Comento aqui embaixo." in d["comentario_fixado"]
    assert VIDEO in d["comentario_fixado"]


def test_linkedin_que_ja_tem_link_nao_e_tocado():
    original = f"Já linkei: {VIDEO}"
    d = _job()._garantir_link(base(copy="x", comentario_fixado=original), "linkedin")
    assert d["comentario_fixado"] == original


def test_threads_recebe_o_link_no_ultimo_post():
    d = _job()._garantir_link(
        base(thread_posts=["Gancho.", "Meio.", "Fecho."]), "threads",
    )
    assert VIDEO in d["thread_posts"][-1]
    assert VIDEO not in d["thread_posts"][0]


def test_instagram_nunca_recebe_url():
    """
    O Instagram não renderiza link em legenda nem em comentário. Enfiar uma
    URL ali só suja o texto — lá o caminho é a bio.
    """
    d = _job()._garantir_link(base(copy="Legenda do carrossel."), "instagram")
    assert "http" not in d["copy"]
    assert not d.get("comentario_fixado")


def test_sem_video_cai_no_artigo():
    """O vídeo pode não existir ainda: o artigo já está no ar e serve."""
    d = _job(video=None)._garantir_link(base(copy="Post."), "youtube_community")
    assert ARTIGO in d["copy"]


def test_sem_video_e_sem_artigo_cai_no_canal():
    """Melhor o canal que um post sem destino nenhum."""
    j = _job(video=None)
    d = j._garantir_link({"session_id": "s1", "copy": "Post."}, "youtube_community")
    assert "http" in d["copy"]


def test_prefere_video_a_artigo():
    """
    A ordem é o pedido explícito do dono do canal: o link tem que levar ao
    VÍDEO, não ao canal nem só ao artigo, assim que o vídeo existir.
    """
    d = _job()._garantir_link(base(copy="Post."), "youtube_community")
    assert VIDEO in d["copy"] and ARTIGO not in d["copy"]
