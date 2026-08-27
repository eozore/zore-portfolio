# -*- coding: utf-8 -*-
"""
sessoes_index.py
================
Índice das sessões do Studio.

Existe porque o checkpoint do LangGraph é INLISTÁVEL. Ele grava em
`graph_threads/{thread}/checkpoints/{id}`, e o documento PAI nunca é criado —
no Firestore, um documento que só tem subcoleção não aparece em listagem nem
responde a `get()`. O estado sobrevive a um refresh, mas só se você já souber
o `sessionId`.

Na prática isso significava: o Studio guardava o id da sessão corrente no
`localStorage` do navegador, e "Começar outro tema" sobrescrevia esse
ponteiro. O ciclo anterior continuava inteiro no Firestore e ficava
inalcançável pela interface — sem lista, sem histórico, sem como voltar.

Este índice é um documento leve por sessão, atualizado a cada transição do
grafo. Não duplica o estado: guarda o suficiente para LISTAR e para levar de
volta ao checkpoint, que continua sendo a fonte da verdade.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("cmo_agent.sessoes_index")

COLECAO = "studio_sessions"


def _ref(db, tenant_id: Optional[str], session_id: str):
    base = f"tenants/{tenant_id}/{COLECAO}" if tenant_id else COLECAO
    return db.collection(base).document(session_id)


def registrar(
    db,
    tenant_id: Optional[str],
    session_id: str,
    *,
    tema: str = "",
    fase: str = "",
    artigo_slug: str = "",
    artigo_url: str = "",
    video_project_id: str = "",
    erros: int = 0,
) -> None:
    """
    Cria ou atualiza a entrada da sessão.

    Nunca levanta: um índice que falha não pode derrubar um ciclo em
    andamento. O pior caso é a sessão não aparecer na lista — que é
    exatamente o comportamento de antes deste arquivo existir.
    """
    if db is None or not session_id:
        return

    agora = datetime.now(timezone.utc).isoformat()
    dados: dict[str, Any] = {"session_id": session_id, "atualizado_em": agora}
    # Só grava o que foi informado: uma retomada não sabe o tema, e sobrescrever
    # com string vazia apagaria o que o start registrou.
    if tema:             dados["tema"] = tema
    if fase:             dados["fase"] = fase
    if artigo_slug:      dados["artigo_slug"] = artigo_slug
    if artigo_url:       dados["artigo_url"] = artigo_url
    if video_project_id: dados["video_project_id"] = video_project_id
    dados["erros"] = int(erros)

    try:
        ref = _ref(db, tenant_id, session_id)
        if not ref.get().exists:
            dados["criado_em"] = agora
        ref.set(dados, merge=True)
    except Exception as exc:                                   # noqa: BLE001
        logger.warning("[sessoes_index] falhou para %s: %s", session_id, exc)


def listar(db, tenant_id: Optional[str], limite: int = 50) -> list[dict]:
    """Sessões mais recentes primeiro. Lista vazia em qualquer falha."""
    if db is None:
        return []
    base = f"tenants/{tenant_id}/{COLECAO}" if tenant_id else COLECAO
    try:
        docs = (
            db.collection(base)
            .order_by("atualizado_em", direction="DESCENDING")
            .limit(limite)
            .stream()
        )
        return [{**(d.to_dict() or {}), "session_id": d.id} for d in docs]
    except Exception as exc:                                   # noqa: BLE001
        logger.warning("[sessoes_index] listagem falhou: %s", exc)
        return []
