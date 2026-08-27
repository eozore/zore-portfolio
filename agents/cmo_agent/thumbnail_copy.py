# -*- coding: utf-8 -*-
"""
thumbnail_copy.py
=================
Frase de impacto da thumbnail do YouTube.

Existe porque a pipeline passava o TÍTULO do vídeo para o gerador de
thumbnail. As capas que o canal usa não trazem o título: trazem uma frase
curta que provoca ("O ERRO / MAIS CARO / DE ML"), e o título fica ao lado do
vídeo, onde já é lido.

Com o título de 63 caracteres do ciclo de 27/08, a capa saiu com sete linhas
de texto e nada mais — ilegível em miniatura, indistinguível na lista de
recomendados.

Nenhum layout resolve isso: o problema é o texto, não a diagramação.
"""

from __future__ import annotations

import logging
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger("cmo_agent.thumbnail_copy")


class FraseDeCapa(BaseModel):
    """Texto da capa. Curto por contrato, não por convenção."""

    frase: str = Field(
        ...,
        min_length=6,
        max_length=32,
        description=(
            "Frase de impacto em CAIXA ALTA, 2 a 5 palavras, no máximo 32 "
            "caracteres. Nomeia a dor ou a promessa, não o assunto."
        ),
    )
    apoio: str = Field(
        ...,
        min_length=8,
        max_length=46,
        description=(
            "Linha de apoio em caixa normal, até 46 caracteres. Diz o que o "
            "vídeo entrega, de forma concreta."
        ),
    )


_INSTRUCAO = """Você escreve capas de vídeo para o canal do Victor Zoré, sobre
engenharia de IA e machine learning para quem trabalha com isso.

A capa NÃO repete o título — o título já aparece ao lado do vídeo. Ela dá o
motivo de clicar em duas a cinco palavras.

Exemplos reais deste canal:
  frase: "O ERRO MAIS CARO DE ML"     apoio: "Validação temporal em 5 min"
  frase: "SEU MODELO TE ENGANOU"      apoio: "Por que 95% no teste não vale nada"

O que funciona: nomear a perda, o erro, o custo ou a surpresa. Concreto.
O que não funciona: "GUIA COMPLETO", "TUDO SOBRE X", "ENTENDA X" — categoria
de assunto não é motivo para clicar.

Sem emoji, sem ponto final, sem aspas."""


async def gerar_frase_de_capa(
    titulo: str,
    tese: str = "",
    publico: str = "",
) -> Optional[dict]:
    """
    Devolve `{"frase": ..., "apoio": ...}`, ou None se não der.

    Falha ABERTO de propósito: sem a frase, o gerador de thumbnail cai no
    título. Uma capa fraca é ruim; bloquear a publicação de um vídeo pronto
    por causa da capa é pior.
    """
    from structured import generate_structured

    prompt = (
        f"Título do vídeo: {titulo}\n"
        f"Tese: {tese or '(não informada)'}\n"
        f"Público: {publico or '(não informado)'}\n\n"
        "Escreva a frase de capa e a linha de apoio."
    )
    try:
        r = await generate_structured(
            FraseDeCapa, prompt, system_instruction=_INSTRUCAO, temperature=0.8,
        )
        return {"frase": r.frase.strip().upper(), "apoio": r.apoio.strip()}
    except Exception as exc:                                   # noqa: BLE001
        logger.warning("[thumbnail_copy] frase de capa indisponível: %s", exc)
        return None
