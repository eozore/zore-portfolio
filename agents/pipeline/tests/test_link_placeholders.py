"""
Cobertura da substituição de [LINK_ARTIGO] / [LINK_CANAL].

Por que existe: os prompts de copy_agent e distribution_agent mandam os modelos
emitirem esses marcadores em vez de URLs reais, mas a etapa de substituição
nunca tinha sido construída — 9 ocorrências de [LINK_ARTIGO] saíam LITERALMENTE
nos posts de Threads e no carrossel. Como isso decide o que vai a público sob a
marca do usuário, a regressão precisa doer no CI, não no feed.
"""

from unittest.mock import MagicMock

import pytest

from publisher_job.job import (
    ARTICLE_PLACEHOLDER,
    CHANNEL_PLACEHOLDER,
    YOUTUBE_CHANNEL_URL,
    PublisherJob,
    _article_url_from,
)


@pytest.fixture
def job() -> PublisherJob:
    j = PublisherJob.__new__(PublisherJob)   # sem tocar Firestore no __init__
    j._project_id = "test-project"
    j._db = MagicMock()
    j._video_url_cache = {}
    return j


# ── URL do artigo ─────────────────────────────────────────────────────────────

def test_article_url_prefere_o_campo_direto():
    data = {"article_url": "https://eozore.com/pt-BR/blog/meu-post", "article_slug": "outro"}
    assert _article_url_from(data) == "https://eozore.com/pt-BR/blog/meu-post"


def test_article_url_monta_a_partir_do_slug_quando_nao_ha_url():
    data = {"article_slug": "testes-ab", "language": "pt-BR"}
    assert _article_url_from(data).endswith("/pt-BR/blog/testes-ab")


def test_article_url_cai_no_indice_do_blog_sem_slug():
    # Pior caso ainda precisa ser um link válido, nunca um placeholder vazio.
    assert _article_url_from({}).endswith("/blog")


# ── Substituição ──────────────────────────────────────────────────────────────

def test_substitui_link_do_artigo(job):
    texto = f"Conclusão. Artigo completo: {ARTICLE_PLACEHOLDER}"
    out = job._resolve_placeholders(texto, {"article_url": "https://eozore.com/x"})
    assert out == "Conclusão. Artigo completo: https://eozore.com/x"
    assert ARTICLE_PLACEHOLDER not in out


def test_link_do_canal_usa_o_video_quando_ja_publicado(job):
    doc = MagicMock()
    doc.to_dict.return_value = {"publish_results": {"youtube": "abc123"}, "created_at": "2026-01-01"}
    job._db.collection.return_value.where.return_value.limit.return_value.get.return_value = [doc]

    out = job._resolve_placeholders(f"Veja: {CHANNEL_PLACEHOLDER}", {"session_id": "s1"})
    assert out == "Veja: https://youtu.be/abc123"


def test_link_do_canal_cai_no_canal_quando_video_ainda_nao_existe(job):
    # Item da fila publicado antes do vídeo, ou upload que falhou: publicar um
    # link do canal é aceitável; publicar "[LINK_CANAL]" nunca é.
    job._db.collection.return_value.where.return_value.limit.return_value.get.return_value = []

    out = job._resolve_placeholders(f"Veja: {CHANNEL_PLACEHOLDER}", {"session_id": "s1"})
    assert out == f"Veja: {YOUTUBE_CHANNEL_URL}"
    assert CHANNEL_PLACEHOLDER not in out


def test_falha_do_firestore_nao_derruba_a_publicacao(job):
    job._db.collection.side_effect = RuntimeError("firestore fora do ar")

    out = job._resolve_placeholders(f"Veja: {CHANNEL_PLACEHOLDER}", {"session_id": "s1"})
    assert out == f"Veja: {YOUTUBE_CHANNEL_URL}"


def test_texto_sem_placeholder_passa_intacto(job):
    texto = "Post normal, sem marcadores."
    assert job._resolve_placeholders(texto, {}) == texto
    job._db.collection.assert_not_called()   # nem consulta o Firestore à toa


def test_consulta_do_video_e_cacheada_entre_itens(job):
    doc = MagicMock()
    doc.to_dict.return_value = {"publish_results": {"youtube": "v1"}, "created_at": "2026-01-01"}
    job._db.collection.return_value.where.return_value.limit.return_value.get.return_value = [doc]

    for _ in range(3):
        job._resolve_placeholders(f"{CHANNEL_PLACEHOLDER}", {"session_id": "mesma"})

    # Uma execução da fila publica vários itens da mesma sessão.
    assert job._db.collection.call_count == 1
