# -*- coding: utf-8 -*-
"""
knowledge.py — Memória e base de conhecimento do time de agentes.

Três camadas, com propósitos distintos:

1. MEMÓRIA DE MARCA (`brand_memory`) — voz, público, temas proibidos, CTAs que
   funcionam. Editada pelo dono do canal, lida por todo agente. É o que
   impede cada geração de reinventar o tom do zero.

2. BASE DE CONHECIMENTO (`recall_artigos`) — o que já foi publicado. Serve
   para duas coisas concretas: não repetir tema já coberto, e criar links
   internos entre conteúdos. Sem isso, o agente propõe pela terceira vez o
   mesmo assunto sem saber.

3. MEMÓRIA EPISÓDICA (`recall_decisoes`) — o que o humano aprovou, rejeitou e
   por quê nos gates. É a camada que faz o time melhorar: se três artigos
   seguidos foram rejeitados por "muito raso", isso entra no prompt do
   próximo.

Tudo em Firestore, isolado por tenant. Sem banco vetorial: o volume é de
dezenas de artigos, não milhões — busca por campo resolve, e um índice
vetorial seria infra nova para manter sem ganho real nessa escala.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger("cmo_agent.graph.knowledge")

MAX_ARTIGOS_CONTEXTO  = 8
MAX_DECISOES_CONTEXTO = 6


def _col(db, tenant_id: Optional[str], nome: str):
    base = f"tenants/{tenant_id}/{nome}" if tenant_id else nome
    return db.collection(base)


# ── 1. Memória de marca ───────────────────────────────────────────────────────

DEFAULT_BRAND = {
    "voz": (
        "Conversacional, direto, professoral-acessível. Autoridade técnica que "
        "não precisa se anunciar. Sem clichê de marketing, sem emoji em título."
    ),
    "publico": "Líderes técnicos e profissionais de IA/ML no Brasil.",
    "evitar": ["hype sem dado", "promessa de resultado garantido", "Title Case"],
    "objetivo_funil": (
        "Todo conteúdo social existe para gerar view no vídeo do YouTube."
    ),
}


def carregar_marca(db, tenant_id: Optional[str]) -> dict[str, Any]:
    """Perfil de marca do tenant, com defaults quando ainda não configurado."""
    try:
        snap = _col(db, tenant_id, "agent_configurations").document("brand").get()
        if snap.exists:
            return {**DEFAULT_BRAND, **(snap.to_dict() or {})}
    except Exception as exc:
        logger.warning("[kb] Falha ao ler marca do tenant %s: %s", tenant_id, exc)
    return dict(DEFAULT_BRAND)


# ── 2. Base de conhecimento: o que já foi publicado ───────────────────────────

def recall_artigos(db, tenant_id: Optional[str], limite: int = MAX_ARTIGOS_CONTEXTO) -> list[dict]:
    """Artigos já publicados, do mais recente para o mais antigo."""
    try:
        docs = (
            _col(db, tenant_id, "articles")
            .order_by("publishedAt", direction="DESCENDING")
            .limit(limite)
            .stream()
        )
        saida = []
        for d in docs:
            data = d.to_dict() or {}
            saida.append({
                "titulo": data.get("title", ""),
                "slug":   data.get("slug", ""),
                "categoria": data.get("category", ""),
                # Só o resumo: o corpo inteiro estouraria a janela de contexto
                # sem acrescentar nada à decisão de "isto já foi coberto?".
                "resumo": (data.get("content") or "")[:280],
            })
        return saida
    except Exception as exc:
        logger.warning("[kb] Falha ao recuperar artigos: %s", exc)
        return []


# ── 3. Memória episódica: decisões dos gates ──────────────────────────────────

def registrar_decisao(
    db,
    tenant_id: Optional[str],
    *,
    gate: str,
    decisao: str,
    comentario: str,
    tema: str,
) -> None:
    """Grava uma decisão do humano para alimentar as gerações seguintes."""
    try:
        _col(db, tenant_id, "agent_memory").add({
            "tipo": "decisao_gate",
            "gate": gate,
            "decisao": decisao,
            "comentario": comentario,
            "tema": tema,
            "em": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(),
        })
    except Exception as exc:
        logger.warning("[kb] Falha ao registrar decisão: %s", exc)


def recall_decisoes(db, tenant_id: Optional[str], limite: int = MAX_DECISOES_CONTEXTO) -> list[dict]:
    """
    Decisões recentes, priorizando as que pediram ajuste.

    Uma aprovação sem comentário não ensina nada; uma rejeição com motivo é
    exatamente o que o próximo prompt precisa saber.
    """
    try:
        docs = (
            _col(db, tenant_id, "agent_memory")
            .where("tipo", "==", "decisao_gate")
            .order_by("em", direction="DESCENDING")
            .limit(limite * 2)
            .stream()
        )
        itens = [d.to_dict() or {} for d in docs]
        com_licao = [i for i in itens if (i.get("comentario") or "").strip()]
        return com_licao[:limite]
    except Exception as exc:
        logger.warning("[kb] Falha ao recuperar decisões: %s", exc)
        return []


# ── Montagem do bloco de contexto ─────────────────────────────────────────────

def montar_contexto(db, tenant_id: Optional[str]) -> str:
    """
    Bloco de texto injetado no system instruction de todo agente.

    Compacto de propósito: contexto longo demais dilui a instrução principal e
    o modelo passa a otimizar para o histórico em vez da tarefa.
    """
    marca    = carregar_marca(db, tenant_id)
    artigos  = recall_artigos(db, tenant_id)
    decisoes = recall_decisoes(db, tenant_id)

    partes = [
        "━━━ MARCA ━━━",
        f"Voz: {marca['voz']}",
        f"Público: {marca['publico']}",
        f"Evitar: {', '.join(marca.get('evitar', []))}",
        f"Funil: {marca['objetivo_funil']}",
    ]

    if artigos:
        partes.append("\n━━━ JÁ PUBLICADO (não repita, mas pode referenciar) ━━━")
        for a in artigos:
            partes.append(f"- {a['titulo']} (/{a['slug']})")

    if decisoes:
        partes.append("\n━━━ APRENDIZADO DE REVISÕES ANTERIORES ━━━")
        for d in decisoes:
            partes.append(f"- [{d.get('decisao')}] {d.get('comentario', '')[:160]}")

    return "\n".join(partes)
