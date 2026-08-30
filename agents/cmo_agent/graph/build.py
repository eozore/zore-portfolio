# -*- coding: utf-8 -*-
"""
build.py — Montagem do StateGraph do time de marketing.

    planejamento → artigo → [GATE artigo] → video → [GATE video] → social → fim
                      ↑          │                    ↑        │
                      └──ajustar─┘                    └─ajustar┘

Os dois gates usam `interrupt_before`: o LangGraph persiste o checkpoint e a
execução TERMINA. Não há thread parada, não há espera ativa, não há instância
de Cloud Run segurada. A retomada acontece quando a aprovação chega pela API,
possivelmente dias depois e certamente em outro processo.

É por isso que o checkpointer precisa ser o Firestore e não memória: entre a
pausa e a retomada, o container que rodou o grafo já morreu.
"""

from __future__ import annotations

import logging
from typing import Optional

from langgraph.graph import END, StateGraph

from graph.checkpointer import FirestoreCheckpointSaver
from graph.nodes import (
    no_artigo,
    no_briefing,
    no_gate_artigo,
    no_gate_briefing,
    no_gate_video,
    no_planejamento,
    no_social,
    no_video,
    rota_gate_artigo,
    rota_gate_briefing,
    rota_gate_video,
)
from graph.state import EstadoMarketing

logger = logging.getLogger("cmo_agent.graph.build")


def construir_grafo(db, tenant_id: Optional[str] = None):
    """Compila o grafo com checkpoint durável em Firestore."""
    g = StateGraph(EstadoMarketing)

    g.add_node("briefing",      no_briefing)
    g.add_node("gate_briefing", no_gate_briefing)
    g.add_node("planejamento", no_planejamento)
    g.add_node("artigo",       no_artigo)
    g.add_node("gate_artigo",  no_gate_artigo)
    g.add_node("video",        no_video)
    g.add_node("gate_video",   no_gate_video)
    g.add_node("social",       no_social)

    # A entrada é o BRIEFING, não o planejamento: o recorte é negociado antes
    # de qualquer coisa ser pesquisada ou escrita.
    g.set_entry_point("briefing")
    g.add_edge("briefing", "gate_briefing")
    g.add_conditional_edges(
        "gate_briefing", rota_gate_briefing,
        {"planejamento": "planejamento", "briefing": "briefing", "fim": END},
    )
    g.add_edge("planejamento", "artigo")
    g.add_edge("artigo", "gate_artigo")

    g.add_conditional_edges(
        "gate_artigo", rota_gate_artigo,
        {"video": "video", "artigo": "artigo", "fim": END},
    )
    g.add_edge("video", "gate_video")
    g.add_conditional_edges(
        "gate_video", rota_gate_video,
        {"social": "social", "video": "video", "fim": END},
    )
    g.add_edge("social", END)

    return g.compile(
        checkpointer=FirestoreCheckpointSaver(db, tenant_id),
        # Interrompe ANTES do nó de gate. O estado com o artigo/vídeo pronto
        # já está persistido, e o humano revisa a partir dele.
        interrupt_before=["gate_briefing", "gate_artigo", "gate_video"],
    )


def config_thread(tenant_id: str, session_id: str) -> dict:
    """
    Config que identifica a execução para o checkpointer.

    A thread é (tenant, sessão): dois tenants com o mesmo session_id nunca
    compartilham checkpoint.
    """
    return {"configurable": {"thread_id": f"{tenant_id}:{session_id}"}}
