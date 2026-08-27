# -*- coding: utf-8 -*-
"""
youtube_copy.py
===============
Parte editorial da descrição do YouTube.

A primeira versão colava prefixos nos campos da pauta: `"Neste vídeo eu
explico " + tese`. Como a tese já é uma frase inteira, o resultado saía
quebrado — "Neste vídeo eu explico sem um harness de testes bem estruturado,
o desenvolvimento com IA se torna..." — e "Se você é " + publico virava
"Se você é líderes técnicos, engenheiros de ML".

Concordância não sai de concatenação. As descrições que o canal usa são
escritas, então esta parte é escrita também.

O que NÃO vem daqui: os capítulos, que dependem da duração medida de cada
clipe e são montados pelo publisher a partir do `timeline.json`.
"""

from __future__ import annotations

import logging
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger("cmo_agent.youtube_copy")


class CopyDoYouTube(BaseModel):
    """Blocos escritos da descrição. Os capítulos entram depois."""

    abertura: str = Field(
        ...,
        min_length=80,
        max_length=420,
        description=(
            "Primeiro parágrafo, em primeira pessoa. Nomeia o problema e o que "
            "o vídeo entrega. Começa com 'Neste vídeo eu explico'."
        ),
    )
    contexto: str = Field(
        ...,
        min_length=60,
        max_length=380,
        description=(
            "Segundo parágrafo: por que isso importa para quem assiste, em "
            "termos concretos. Sem repetir a abertura."
        ),
    )
    aprendizados: list[str] = Field(
        ...,
        min_length=5,
        max_length=8,
        description=(
            "Promessas do vídeo, uma por item, 6 a 14 palavras cada. Cada uma "
            "é algo que a pessoa saberá fazer ou reconhecer depois de assistir."
        ),
    )
    hashtags: list[str] = Field(
        ...,
        min_length=8,
        max_length=15,
        description="Hashtags sem '#', minúsculas, sem acento e sem espaço.",
    )


_INSTRUCAO = """Você escreve as descrições do canal do Victor Zoré, sobre
engenharia de IA e machine learning para quem trabalha com isso.

O tom é de quem já apanhou do problema: direto, técnico, sem hipérbole e sem
promessa de atalho. Primeira pessoa.

Molde real deste canal:

  abertura: "Neste vídeo eu explico o erro mais caro em modelos de previsão —
  o vazamento temporal — e as quatro técnicas de validação feitas pra dados
  onde o tempo importa: Rolling Window, Expanding Window, Out-of-Time e
  Out-of-Sample."

  contexto: "Se o seu modelo prevê vendas, demanda, churn, risco ou qualquer
  coisa no eixo do tempo, validar com K-Fold embaralhado significa treinar com
  o futuro — e a nota vira ficção."

  aprendizados: "Vazamento temporal: como o modelo 'vê o futuro' na validação
  e desaba em produção", "A regra de ouro: treino sempre antes do teste na
  linha do tempo"

Cada aprendizado é uma promessa concreta, não um nome de tecnologia:
"LangGraph" não é aprendizado; "quando o checkpoint durável evita refazer o
trabalho" é.

Sem emoji. Sem "neste artigo". Sem chamar o espectador de "pessoal"."""


async def gerar_copy_do_youtube(
    titulo: str,
    tese: str = "",
    publico: str = "",
    objetivo: str = "",
    roteiro: str = "",
) -> Optional[dict]:
    """
    Devolve os blocos escritos da descrição, ou None se não der.

    Falha ABERTO: sem isto a descrição cai no encadeamento mecânico dos campos
    da pauta, que é feio mas publica. Travar um vídeo pronto por causa da
    descrição seria pior.
    """
    from structured import generate_structured

    prompt = (
        f"Título: {titulo}\n"
        f"Tese: {tese or '(não informada)'}\n"
        f"Público: {publico or '(não informado)'}\n"
        f"Objetivo de aprendizado: {objetivo or '(não informado)'}\n\n"
        f"=== ROTEIRO FALADO ===\n{(roteiro or '')[:4000]}\n\n"
        "Escreva a abertura, o contexto, os aprendizados e as hashtags."
    )
    try:
        r = await generate_structured(
            CopyDoYouTube, prompt, system_instruction=_INSTRUCAO, temperature=0.6,
        )
        return {
            "abertura":     r.abertura.strip(),
            "contexto":     r.contexto.strip(),
            "aprendizados": [a.strip().rstrip(".;") for a in r.aprendizados],
            "hashtags":     [h.strip().lstrip("#").lower() for h in r.hashtags],
        }
    except Exception as exc:                                   # noqa: BLE001
        logger.warning("[youtube_copy] copy indisponível: %s", exc)
        return None
