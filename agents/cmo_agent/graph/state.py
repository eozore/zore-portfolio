# -*- coding: utf-8 -*-
"""
state.py — Estado do grafo do time de marketing.

Um TypedDict, não um dict solto: cada nó declara o que lê e o que escreve, e o
que não está aqui não atravessa o grafo. O estado anterior era um dict com
`partial_errors: list[str]` — quando algo falhava, a informação virava uma
string no meio de uma lista e ninguém conseguia agir sobre ela.

O estado inteiro é serializado a cada passo pelo checkpointer, então ele
guarda REFERÊNCIAS (URLs do GCS, ids de projeto) para artefatos pesados —
nunca o HTML do deck nem base64 de imagem. Um documento Firestore tem teto de
1MB, e o deck sozinho passa de 80KB.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, Optional, TypedDict

# Fases do funil. A ordem é a do produto: artigo → vídeo → social.
Fase = Literal[
    "briefing",
    "aguardando_briefing",
    "planejamento",
    "artigo",
    "aguardando_aprovacao_artigo",
    "video",
    "aguardando_aprovacao_video",
    "social",
    "concluido",
    "erro",
]

Decisao = Literal["aprovado", "ajustar", "rejeitado"]


class Aprovacao(TypedDict, total=False):
    """Resposta do humano num gate."""
    decisao:    Decisao
    comentario: str
    em:         str          # ISO 8601


class Erro(TypedDict):
    """
    Falha de um nó, estruturada.

    `fatal=False` significa que o grafo segue sem aquela peça — uma thumbnail
    que não gerou não pode impedir a publicação do vídeo. `fatal=True` para.
    """
    no:       str
    mensagem: str
    fatal:    bool


class EstadoMarketing(TypedDict, total=False):
    # ── Identidade ────────────────────────────────────────────────────────────
    tenant_id:  str
    session_id: str
    thread_id:  str

    # ── Entrada ───────────────────────────────────────────────────────────────
    tema:      str
    contexto:  str
    idioma:    str

    # ── Fase corrente ─────────────────────────────────────────────────────────
    fase: Fase

    # ── Briefing ──────────────────────────────────────────────────────────────
    # A conversa que acontece ANTES de qualquer coisa ser escrita.
    #
    # Existe porque o primeiro ponto de contato humano era o gate do artigo —
    # depois de o ângulo já estar escolhido, pesquisado e redigido. Quando o
    # recorte saía errado, não havia onde corrigir sem refazer tudo: o vídeo
    # de SDD de 29/08 explicou como montar os arquivos Python por baixo do
    # capô, quando o pedido era mostrar como usar arquivos .md para configurar
    # agentes na IDE. Nada no fluxo tinha perguntado qual dos dois era.
    briefing:          dict[str, Any]
    conversa_briefing: Annotated[list[dict[str, str]], operator.add]

    # ── Planejamento ──────────────────────────────────────────────────────────
    pauta: dict[str, Any]

    # ── Artigo ────────────────────────────────────────────────────────────────
    artigo_markdown: str
    artigo_titulo:   str
    artigo_slug:     str
    artigo_resumo:   str
    artigo_url:      str

    # ── Vídeo ─────────────────────────────────────────────────────────────────
    manifesto:        dict[str, Any]
    slide_htmls:      dict[str, str]
    video_project_id: str
    video_url:        str
    video_titulo:     str

    # ── Social ────────────────────────────────────────────────────────────────
    plano_social: dict[str, Any]

    # ── Gates ─────────────────────────────────────────────────────────────────
    aprovacao_briefing: Aprovacao
    aprovacao_artigo:   Aprovacao
    aprovacao_video:  Aprovacao

    # ── Diagnóstico ───────────────────────────────────────────────────────────
    # `operator.add` faz o LangGraph CONCATENAR as listas devolvidas por nós
    # paralelos em vez de a última escrita sobrescrever as outras. Sem isso, o
    # fan-out dos canais perderia o erro de todos menos um.
    erros:      Annotated[list[Erro], operator.add]
    trilha:     Annotated[list[str], operator.add]
    custo_usd:  float


def novo_estado(
    tenant_id: str,
    session_id: str,
    tema: str,
    contexto: str = "",
    idioma: str = "pt-BR",
) -> EstadoMarketing:
    return EstadoMarketing(
        tenant_id=tenant_id,
        session_id=session_id,
        thread_id=f"{tenant_id}:{session_id}",
        tema=tema,
        contexto=contexto,
        idioma=idioma,
        fase="briefing",
        conversa_briefing=[],
        erros=[],
        trilha=[],
        custo_usd=0.0,
    )


def tem_erro_fatal(estado: EstadoMarketing) -> bool:
    return any(e.get("fatal") for e in (estado.get("erros") or []))
