# -*- coding: utf-8 -*-
"""
registry.py — Agentes, skills e knowledge base como DADO, não como código.

Três coleções por tenant, todas editáveis pelo dono do canal:

    tenants/{t}/agents/{id}     prompt + quais skills consulta + quais KBs lê
    tenants/{t}/skills/{id}     métodos (copy, cta, design)
    tenants/{t}/knowledge/{id}  documentos de apoio — começa vazio

Por que dado e não código: mudar o tom de voz do redator, acrescentar um
framework de copy ou desativar um CTA não deveria exigir deploy. Hoje o prompt
de cada agente é uma constante Python, e ajustar uma vírgula no tom obriga a
subir imagem nova.

Semeadura na primeira leitura: se o tenant não tem skills, o catálogo padrão
é gravado. A partir daí o documento é dele — reeditar não é sobrescrito.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from skills.catalog import TODAS_AS_SKILLS

logger = logging.getLogger("cmo_agent.skills.registry")


def _col(db, tenant_id: Optional[str], nome: str):
    base = f"tenants/{tenant_id}/{nome}" if tenant_id else nome
    return db.collection(base)


# ── Perfis padrão dos agentes ─────────────────────────────────────────────────
#
# Cada um vira um documento editável. `skills` lista as CATEGORIAS que o agente
# consulta — não skills específicas, porque quem escolhe a específica é ele.

AGENTES_PADRAO: dict[str, dict[str, Any]] = {
    "planejador": {
        "nome": "Planejador de pauta",
        "papel": "Fecha o tema da semana em pauta, com o ângulo do vídeo.",
        "prompt": (
            "Você é o CMO do canal éozoré. Fecha a pauta da semana: título, "
            "tese, público e o ângulo que SÓ o vídeo entrega — é dele que todo "
            "o conteúdo social vai depender."
        ),
        "skills": [],
        "temperatura": 0.6,
    },
    "redator": {
        "nome": "Redator técnico",
        "papel": "Escreve o artigo do blog.",
        "prompt": (
            "Você escreve para líderes técnicos em IA e ML. Rigor sem "
            "formalidade: fórmula quando ela explica, código quando ele prova, "
            "e nenhuma afirmação sem sustentação.\n\n"
            "O artigo é o destino de quem quer a profundidade que o vídeo não "
            "coube. Ele pode e deve ser MAIS técnico — mas técnico é ser "
            "preciso e aplicável, não ser difícil.\n\n"
            "Regras que valem para todo artigo:\n"
            "• Toda seção conceitual traz um exemplo EXECUTÁVEL logo depois — "
            "um bloco ```python (ou da linguagem do assunto) que a pessoa "
            "consegue colar e rodar. Conceito sem exemplo não fica no texto.\n"
            "• O código é mínimo e completo: sem `...`, sem `# resto da "
            "implementação`, sem import que não existe. Se não couber "
            "completo, escolha um recorte menor que caiba.\n"
            "• Mostre o resultado do código — a saída, o número, o erro que "
            "ele evita. Código sem resultado não prova nada.\n"
            "• Prefira UM caso levado até o fim a três casos pela metade.\n"
            "• Quando houver trade-off, diga qual escolher e sob que condição. "
            "Listar opções sem critério de decisão é catálogo, não artigo.\n"
            "• Feche com o que dá para fazer hoje, com o que a pessoa já tem."
        ),
        "skills": [],
        "temperatura": 0.7,
    },
    "roteirista": {
        "nome": "Roteirista de vídeo",
        "papel": "Transforma o artigo no manifesto segmentado do vídeo.",
        "prompt": (
            "Você segmenta o conteúdo entre o apresentador e as ilustrações, "
            "respeitando o orçamento de 20% de avatar distribuído do início ao fim."
        ),
        "skills": [],
        "temperatura": 0.5,
    },
    "distribuidor": {
        "nome": "Estrategista de distribuição",
        "papel": "Monta o plano de mídias sociais que leva ao vídeo.",
        "prompt": (
            "Você decide, peça a peça, qual método de copy e qual CTA servem "
            "MELHOR àquele conteúdo naquela mídia. Não aplique o mesmo método a "
            "tudo: variedade é o que evita que o público canse.\n\n"
            "O objetivo do plano é gerar audiência para o vídeo do YouTube. Isso "
            "NÃO significa mandar toda peça para o vídeo — um 'salve este post' "
            "não gera view hoje, mas aumenta a entrega do próximo post, que gera. "
            "Misture conversão direta e alcance."
        ),
        # As categorias que este agente consulta antes de escrever.
        "skills": ["copy", "cta"],
        "temperatura": 0.6,
    },
    "designer": {
        "nome": "Designer de slides",
        "papel": "Desenha as ilustrações do vídeo e das peças sociais.",
        "prompt": (
            "Você desenha telas que são lidas em segundos. Uma ideia por tela, "
            "tipografia grande, e nenhum elemento que não sustente o argumento."
        ),
        "skills": ["design"],
        "temperatura": 0.7,
    },
}


# ── Skills ────────────────────────────────────────────────────────────────────

def carregar_skills(db, tenant_id: Optional[str]) -> list[dict[str, Any]]:
    """
    Skills do tenant, semeando o catálogo padrão na primeira vez.

    A semeadura é idempotente e só acontece quando a coleção está VAZIA: uma
    vez que o dono do canal editou as suas, reescrever o padrão por cima
    apagaria o trabalho dele.
    """
    col = _col(db, tenant_id, "skills")
    try:
        existentes = [d.to_dict() or {} for d in col.stream()]
    except Exception as exc:
        logger.warning("[skills] Falha ao ler skills, usando catálogo: %s", exc)
        return list(TODAS_AS_SKILLS)

    if existentes:
        return existentes

    logger.info("[skills] Tenant sem skills — semeando %d padrão.", len(TODAS_AS_SKILLS))
    try:
        lote = db.batch()
        for s in TODAS_AS_SKILLS:
            lote.set(col.document(s["id"]), {**s, "ativo": True, "fonte": "padrao"})
        lote.commit()
    except Exception as exc:
        logger.warning("[skills] Falha ao semear: %s", exc)
    return [{**s, "ativo": True, "fonte": "padrao"} for s in TODAS_AS_SKILLS]


# ── Agentes ───────────────────────────────────────────────────────────────────

def carregar_agente(db, tenant_id: Optional[str], agente_id: str) -> dict[str, Any]:
    """Configuração de um agente, com o padrão como base."""
    padrao = AGENTES_PADRAO.get(agente_id, {})
    try:
        snap = _col(db, tenant_id, "agents").document(agente_id).get()
        if snap.exists:
            return {**padrao, **(snap.to_dict() or {})}
    except Exception as exc:
        logger.warning("[skills] Falha ao ler agente %s: %s", agente_id, exc)
    return dict(padrao)


def semear_agentes(db, tenant_id: Optional[str]) -> None:
    """Grava os perfis padrão que ainda não existem, sem tocar nos editados."""
    col = _col(db, tenant_id, "agents")
    for aid, perfil in AGENTES_PADRAO.items():
        try:
            if not col.document(aid).get().exists:
                col.document(aid).set({**perfil, "id": aid, "editavel": True})
        except Exception as exc:
            logger.warning("[skills] Falha ao semear agente %s: %s", aid, exc)


# ── Knowledge base ────────────────────────────────────────────────────────────

def carregar_knowledge(
    db, tenant_id: Optional[str], tags: Optional[list[str]] = None, limite: int = 5,
) -> list[dict[str, Any]]:
    """
    Documentos de apoio do tenant. Começa VAZIO de propósito.

    Semear isto com "conhecimento de marketing" genérico seria inventar
    folclore e vesti-lo de referência. A KB ganha valor quando recebe material
    escolhido pelo dono do canal e, na fase seguinte, resultados reais de
    publicação — não antes.
    """
    try:
        q = _col(db, tenant_id, "knowledge")
        if tags:
            q = q.where("tags", "array_contains_any", tags[:10])
        return [d.to_dict() or {} for d in q.limit(limite).stream()]
    except Exception as exc:
        logger.warning("[skills] Falha ao ler knowledge: %s", exc)
        return []


# ── Montagem da instrução do agente ───────────────────────────────────────────

def montar_instrucao(
    db,
    tenant_id: Optional[str],
    agente_id: str,
    contexto_extra: str = "",
) -> str:
    """
    Instrução completa: prompt do agente + skills que ele consulta + KB.

    As skills entram como CATÁLOGO, não como ordem. O texto pede que o agente
    escolha e justifique — a inteligência da escolha é dele; o que o código
    exige é que a escolha seja declarada no output e possa ser validada.
    """
    from skills.catalog import catalogo_para_prompt
    from structured import PT_BR_ORTOGRAFIA

    agente = carregar_agente(db, tenant_id, agente_id)

    # As regras de escrita vão na FRENTE e valem para TODOS os agentes.
    #
    # Antes elas só existiam no caminho de saída estruturada. O redator usa
    # streaming e escapava: o artigo voltava com título em Title Case
    # ("Além do Prompt: Por que Testes A/B são Inegociáveis...") e slug em
    # inglês num texto em português. Um agente que escreve não pode depender
    # do transporte para saber ortografar.
    partes = [PT_BR_ORTOGRAFIA, agente.get("prompt", "")]

    categorias = agente.get("skills") or []
    if categorias:
        skills = carregar_skills(db, tenant_id)
        partes.append(
            "\n━━━ MÉTODOS DISPONÍVEIS ━━━\n"
            "Escolha por peça o que MELHOR serve àquele conteúdo naquela mídia. "
            "Declare o id do método escolhido no campo correspondente. "
            "Repetir o mesmo método em todas as peças é erro."
        )
        for cat in categorias:
            partes.append(f"\n── {cat.upper()} ──\n{catalogo_para_prompt(skills, cat)}")

    docs = carregar_knowledge(db, tenant_id)
    if docs:
        partes.append("\n━━━ BASE DE CONHECIMENTO ━━━")
        for d in docs:
            partes.append(f"[{d.get('titulo', 'sem título')}]\n{(d.get('conteudo') or '')[:1200]}")

    if contexto_extra:
        partes.append(f"\n{contexto_extra}")

    return "\n".join(p for p in partes if p)
