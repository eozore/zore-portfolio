"""
tests/test_fila_agendada.py
===========================
A fila agendada não pode ter peça invisível.

Defeito de 31/08: o job buscava `where(status==planned).limit(50)` SEM
ordenação. Com 71 pendentes na coleção, o Firestore devolvia 50 quaisquer, e
as 21 restantes não eram vistas — nem naquela rodada nem nas seguintes, porque
a janela não anda sozinha.

O sintoma foi um post do Threads vencido havia mais de um dia, junto com 7
outras peças. Nada acusava erro: do ponto de vista do job, aqueles documentos
não existiam. A fila crescia enquanto o canal ficava quieto.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _Doc:
    def __init__(self, dados):
        self._d = dict(dados)
        self.reference = self

    def to_dict(self):
        return dict(self._d)

    def update(self, patch):
        self._d.update(patch)


class _Query:
    """Firestore o suficiente para exercitar a paginação e a ordem."""

    def __init__(self, docs, limite=None, depois=None):
        self._docs, self._limite, self._depois = docs, limite, depois

    def where(self, campo, _op, valor):
        return _Query([d for d in self._docs if d.to_dict().get(campo) == valor])

    def limit(self, n):
        return _Query(self._docs, n, self._depois)

    def start_after(self, doc):
        i = self._docs.index(doc)
        return _Query(self._docs, self._limite, i + 1)

    def get(self):
        inicio = self._depois or 0
        fim = inicio + self._limite if self._limite else None
        return self._docs[inicio:fim]


class _DB:
    def __init__(self, docs):
        self._docs = docs

    def collection(self, _nome):
        return _Query(self._docs)


def _fila(n, vencidos=0):
    """`n` peças planejadas; as `vencidos` primeiras já passaram do horário."""
    docs = []
    for i in range(n):
        dia = "2026-08-20" if i < vencidos else "2026-12-01"
        docs.append(_Doc({
            "status": "planned",
            "platform": "threads" if i == 0 else "instagram",
            "scheduled_at": f"{dia}T{9 + (i % 12):02d}:00:00+00:00",
            "title": f"peça {i}",
        }))
    # Embaralha para que a ordem de chegada nunca seja a de vencimento — é o
    # que o Firestore faz sem `order_by`, e o que escondia as peças.
    return docs[::-1]


def _publisher(db):
    from publisher_job.job import PublisherJob
    p = PublisherJob.__new__(PublisherJob)
    p._db = db
    return p


def test_nenhuma_peca_fica_fora_da_varredura():
    """
    Com 71 pendentes e a janela antiga de 50, 21 eram invisíveis para sempre.
    """
    from publisher_job.job import PublisherJob

    docs = _fila(71)
    encontrados = _publisher(_DB(docs))._pendentes_por_vencimento()
    assert len(encontrados) == 71, f"{71 - len(encontrados)} peças invisíveis"


def test_varredura_vem_ordenada_por_vencimento():
    """
    A ordem é o que garante que a peça mais atrasada saia primeiro. Sem ela,
    um teto de vazão publicaria as futuras e deixaria as vencidas para trás.
    """
    docs = _fila(60, vencidos=5)
    encontrados = _publisher(_DB(docs))._pendentes_por_vencimento()
    quandos = [d.to_dict()["scheduled_at"] for d in encontrados]
    assert quandos == sorted(quandos)
    assert quandos[0].startswith("2026-08-20"), "a mais vencida tem que vir primeiro"


def test_pagina_alem_do_tamanho_de_uma_pagina():
    """A varredura não pode parar no tamanho da página do Firestore."""
    from publisher_job.job import PAGINA_FILA

    docs = _fila(PAGINA_FILA + 37)
    encontrados = _publisher(_DB(docs))._pendentes_por_vencimento()
    assert len(encontrados) == PAGINA_FILA + 37


def test_teto_e_de_vazao_nao_de_visibilidade():
    """
    O limite por rodada existe para não disparar 70 posts de uma vez. Ele age
    na PUBLICAÇÃO; a varredura continua enxergando a fila inteira, senão volta
    o defeito que ele deveria evitar.
    """
    import inspect
    from publisher_job.job import PublisherJob, MAX_PUBLICACOES_POR_RODADA

    assert MAX_PUBLICACOES_POR_RODADA > 0
    varredura = inspect.getsource(PublisherJob._pendentes_por_vencimento)
    assert "MAX_PUBLICACOES_POR_RODADA" not in varredura, (
        "o teto de vazão não pode limitar a busca"
    )
    corpo = inspect.getsource(PublisherJob.run)
    assert "MAX_PUBLICACOES_POR_RODADA" in corpo


def test_busca_nao_usa_limite_fixo_sem_ordem():
    """
    Trava a regressão exata: `.limit(50)` direto na busca, sem paginar, é o
    que criava a janela que não anda.
    """
    import inspect
    from publisher_job.job import PublisherJob

    corpo = inspect.getsource(PublisherJob.run)
    assert ".limit(50)" not in corpo
    assert "_pendentes_por_vencimento" in corpo


# ── Curtos entram na fila, não saem na hora ───────────────────────────────────

def test_curto_vai_para_a_fila_e_nao_publica_na_hora():
    """
    O Reel e o Short eram os únicos formatos que nunca apareciam na lista de
    conteúdos: o corte vertical disparava `trigger="immediate"` e eles iam ao
    ar em minutos. Sem revisão, sem distribuição no tempo, e concorrendo com o
    vídeo longo que tinha acabado de sair.
    """
    import inspect
    from vertical_cut_job.job import VerticalCutJob

    corpo = inspect.getsource(VerticalCutJob.run)
    # Tira comentários antes de checar: o que documenta o defeito cita o
    # `trigger="immediate"` que ele explica.
    codigo = "\n".join(
        l for l in corpo.splitlines() if not l.lstrip().startswith("#")
    )
    assert "VIDEO_READY_TOPIC" not in codigo, "o curto não publica na hora"
    assert 'trigger="immediate"' not in codigo
    assert "_enfileirar_curto" in codigo


def test_curto_e_agendado_depois_do_video_longo():
    """
    O curto existe para levar tráfego a um vídeo que JÁ está no ar. Agendá-lo
    para hoje o põe competindo com o próprio longo.
    """
    import inspect
    from vertical_cut_job.job import VerticalCutJob

    corpo = inspect.getsource(VerticalCutJob._enfileirar_curto)
    assert "range(1, 8)" in corpo, "o piso do agendamento tem que ser D+1"


def test_cada_canal_do_curto_vira_um_documento():
    """
    Short e Reel são peças independentes na fila. É isso que permite soltar um
    sem o outro — o Reel do Instagram precisou esperar o longo virar público,
    e o Short não.
    """
    import inspect
    from vertical_cut_job.job import VerticalCutJob

    corpo = inspect.getsource(VerticalCutJob._enfileirar_curto)
    assert "for canal in channels" in corpo
    assert "youtube_shorts" in corpo and "instagram" in corpo
