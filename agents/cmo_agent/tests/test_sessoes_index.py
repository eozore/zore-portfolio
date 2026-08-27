"""
tests/test_sessoes_index.py
============================
O índice das sessões do Studio.

Existe porque o checkpoint do LangGraph é INLISTÁVEL: grava em
`graph_threads/{thread}/checkpoints/{id}` e o documento PAI nunca é criado.
No Firestore, um documento que só tem subcoleção não aparece em listagem nem
responde a `get()` — verificado em produção, onde o pai da thread de 27/08
devolve 404 enquanto os cinco checkpoints estão lá.

A consequência era a queixa do dono do canal: o Studio guardava o id da
sessão no `localStorage`, e "Começar outro tema" sobrescrevia o ponteiro. O
ciclo anterior continuava inteiro no Firestore e ficava inalcançável pela
interface.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fake_firestore import FakeFirestore  # noqa: E402
from sessoes_index import listar, registrar  # noqa: E402


def test_registra_e_lista_a_sessao():
    db = FakeFirestore()
    registrar(db, None, "s1", tema="Harness em IA", fase="artigo")
    (s,) = listar(db, None)
    assert s["session_id"] == "s1"
    assert s["tema"] == "Harness em IA"


def test_mais_recente_primeiro():
    db = FakeFirestore()
    registrar(db, None, "antiga", tema="A", fase="concluido")
    registrar(db, None, "nova", tema="B", fase="artigo")
    # `atualizado_em` é ISO 8601, ordenável como string.
    db.store["studio_sessions/antiga"]["atualizado_em"] = "2026-01-01T00:00:00+00:00"
    db.store["studio_sessions/nova"]["atualizado_em"] = "2026-08-27T00:00:00+00:00"
    assert [s["session_id"] for s in listar(db, None)] == ["nova", "antiga"]


def test_criado_em_so_no_primeiro_registro():
    """A data de criação não pode ser reescrita a cada transição do grafo."""
    db = FakeFirestore()
    registrar(db, None, "s1", tema="A", fase="artigo")
    criado = db.store["studio_sessions/s1"]["criado_em"]
    registrar(db, None, "s1", fase="video")
    assert db.store["studio_sessions/s1"]["criado_em"] == criado


def test_campo_vazio_nao_apaga_o_que_ja_existe():
    """
    Uma retomada não sabe o tema. Gravar string vazia apagaria o que o start
    registrou, e a sessão apareceria sem título na lista.
    """
    db = FakeFirestore()
    registrar(db, None, "s1", tema="Harness em IA", fase="artigo")
    registrar(db, None, "s1", fase="concluido")
    guardado = db.store["studio_sessions/s1"]
    assert guardado["tema"] == "Harness em IA"
    assert guardado["fase"] == "concluido"


def test_falha_do_indice_nao_derruba_o_ciclo():
    """
    Um índice que quebra não pode matar um ciclo em andamento. O pior caso é
    a sessão não aparecer na lista — o comportamento de antes deste arquivo.
    """
    class DbQuebrado:
        def collection(self, _):
            raise RuntimeError("Firestore fora do ar")

    registrar(DbQuebrado(), None, "s1", tema="x")     # não levanta
    assert listar(DbQuebrado(), None) == []


def test_sem_db_nao_explode():
    registrar(None, None, "s1", tema="x")
    assert listar(None, None) == []


def test_tenant_isola_a_lista():
    """A biblioteca de um tenant não pode vazar para outro."""
    db = FakeFirestore()
    registrar(db, "acme", "s1", tema="da acme")
    registrar(db, None, "s2", tema="do default")
    assert [s["session_id"] for s in listar(db, "acme")] == ["s1"]
    assert [s["session_id"] for s in listar(db, None)] == ["s2"]
