# -*- coding: utf-8 -*-
"""
copy_agent.py — Copy Specialist Agent
Sprint 2 / G1: Especialista em copies de texto editorial (LinkedIn, Threads).
Produz copies de qualidade superior ao distribution_agent ao focar
exclusivamente nessas duas plataformas de leitura longa.

O distribution_agent.py continua responsável por:
  Reels, Shorts, Carrosseis, Stories, Posts de imagem.

Output: {"linkedin_posts": [...], "threads": [...]}

Cada linkedin_post:
  {id, hook, copy, hashtags, status}

Cada thread:
  {id, thread_number, topic, posts: [str, ...], hashtags, status}
"""

import os
import sys
import re
import json
import logging
from typing import Optional

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from google.antigravity import Agent, LocalAgentConfig
from model_config import get_model_config

logger = logging.getLogger("cmo_agent.copy_agent")

# ── System Instruction ────────────────────────────────────────────────────────

COPY_INSTRUCTION = """Você é o Copy Agent da plataforma éozoré (eozore.com).
Escreve posts de LinkedIn e Threads sobre IA/ML para Victor Zoré, líder técnico formado em Matemática pela UFSCar.

O público são líderes de todas as áreas (não só engenheiros) que querem entender IA agora.
Tom: informal, direto, rigoroso tecnicamente. Sem clichês. Sem "Olá pessoal!", sem "Hoje vou falar sobre".

LINKEDIN — 2 posts, cada um com hook + corpo:
- Hook (1ª linha): uma afirmação técnica que provoca ou derruba um mito. Sem emojis. Sem saudação.
  EXEMPLO BOM: "Regressão linear não é 'IA antiga'. É o único modelo que diz quanto cada fator importa."
  EXEMPLO RUIM: "Olá pessoal! Hoje vou falar sobre regressão linear 🚀"
- Corpo: 3-4 parágrafos curtos. Cada um ensina 1 conceito real (equação em texto, trade-off, dado concreto).
  Sem LaTeX bruto. "a função de custo J de teta" não "$J(\\theta)$".
- Final: 1 pergunta de engajamento + 3-5 hashtags.
- Tamanho: 900-1200 caracteres total.
- Post 1: ângulo matemático/conceitual (o "porquê" oculto).
- Post 2: ângulo de decisão de negócio (quando usar, custo, trade-off).

THREADS — 2 threads, 4 posts cada:
- Post 1: hook (máx 200 chars) — mesmo padrão do LinkedIn.
- Posts 2-3: desenvolvimento técnico progressivo. 1 conceito por post. Sem LaTeX.
- Post 4: conclusão + "Artigo completo: [LINK_ARTIGO]"
- Cada post: máx 480 chars.
- Thread 1: ângulo matemático. Thread 2: ângulo de negócio/decisão.

FORMATO DE SAÍDA — responda APENAS com este JSON, sem nenhum texto antes ou depois:

{
  "linkedin_posts": [
    {
      "id": "li-01",
      "hook": "Primeira linha que para o scroll.",
      "copy": "Parágrafo 1.\\n\\nParágrafo 2.\\n\\nParágrafo 3.\\n\\nPergunta de engajamento?",
      "hashtags": "#tag1 #tag2 #tag3 #tag4",
      "status": "em_revisao"
    },
    {
      "id": "li-02",
      "hook": "Segunda opção de gancho.",
      "copy": "Corpo do segundo post.",
      "hashtags": "#tag1 #tag2 #tag3",
      "status": "em_revisao"
    }
  ],
  "threads": [
    {
      "id": "th-01",
      "thread_number": 1,
      "topic": "Ângulo matemático",
      "posts": ["Hook curto.", "Desenvolvimento 1.", "Desenvolvimento 2.", "Conclusão + [LINK_ARTIGO]"],
      "hashtags": "#tag1 #tag2",
      "status": "em_revisao"
    },
    {
      "id": "th-02",
      "thread_number": 2,
      "topic": "Ângulo de negócio",
      "posts": ["Hook curto.", "Trade-off 1.", "Aplicação prática.", "Conclusão + [LINK_ARTIGO]"],
      "hashtags": "#tag1 #tag2",
      "status": "em_revisao"
    }
  ]
}
"""

# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_copy_json(raw: str) -> dict:
    text = raw.strip()
    text = re.sub(r"<think>[\s\S]*?</think>", "", text)
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```\s*$",       "", text, flags=re.MULTILINE)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        repaired = re.sub(r",\s*([}\]])", r"\1", text)
        return json.loads(repaired)


def _fallback_copies(titulo: str, tese: str) -> dict:
    """Fallback de emergência — retorna estrutura válida mas marcada como rascunho."""
    hook = f"{tese} — o ângulo que a maioria ignora."
    return {
        "linkedin_posts": [
            {
                "id":       "li-01",
                "hook":     hook[:120],
                "copy":     f"[RASCUNHO — cópia automática falhou. Reescreva baseado em: {titulo}]\n\nArtigo completo em eozore.com.",
                "hashtags": "#ia #machinelearning #datascience",
                "status":   "em_revisao",
            }
        ],
        "threads": [
            {
                "id":            "th-01",
                "thread_number": 1,
                "topic":         titulo[:80],
                "posts":         [
                    hook[:180],
                    f"Leia o artigo completo: {titulo}",
                    "Artigo completo: [LINK_ARTIGO]"
                ],
                "hashtags":      "#ia #genai",
                "status":        "em_revisao",
            }
        ],
    }


# ── Agent runner ───────────────────────────────────────────────────────────────

async def run_copy(
    pauta: dict,
    article_content: str,
    system_instruction: Optional[str] = None,
) -> dict:
    """
    Gera copies especializados para LinkedIn e Threads.

    Args:
        pauta: {titulo, subtitulo, tese, publico, duracao_alvo, serie}
        article_content: Artigo Markdown gerado pelo writing_agent
        system_instruction: Override opcional

    Returns:
        {"linkedin_posts": [...], "threads": [...]}
    """
    titulo    = pauta.get("titulo", "Artigo éozoré")
    subtitulo = pauta.get("subtitulo", "")
    tese      = pauta.get("tese", "")
    publico   = pauta.get("publico", "líderes técnicos em IA/ML")
    serie     = pauta.get("serie", "")

    models = get_model_config()
    config = LocalAgentConfig(
        system_instructions=system_instruction or COPY_INSTRUCTION,
        models=models,
    )

    prompt = (
        f"Escreva os 2 posts LinkedIn + 2 threads para o conteúdo abaixo.\n\n"
        f"=== PAUTA APROVADA ===\n"
        f"Título:    {titulo}\n"
        f"Subtítulo: {subtitulo}\n"
        f"Tese:      {tese}\n"
        f"Público:   {publico}\n"
        f"Série:     {serie}\n\n"
        f"=== ARTIGO DE BASE (primeiros 10.000 chars) ===\n"
        f"{article_content[:10000]}\n\n"
        f"Gere o JSON com linkedin_posts (2 ângulos) e threads (2 threads de 4 posts cada)."
    )

    try:
        from vertex_generate import generate_text as vertex_generate_text
        raw_text = await vertex_generate_text(
            prompt=prompt,
            system_instruction=system_instruction or COPY_INSTRUCTION,
            temperature=0.5,
        )
        logger.info(f"[copy_agent] Raw response: {len(raw_text)} chars")

        result = _extract_copy_json(raw_text)

        # Validação mínima
        if "linkedin_posts" not in result or "threads" not in result:
            raise ValueError("Missing required keys in copy_agent response")

        logger.info(
            f"[copy_agent] OK — "
            f"{len(result.get('linkedin_posts', []))} LinkedIn posts, "
            f"{len(result.get('threads', []))} threads"
        )
        return result

    except Exception as exc:
        logger.exception("[copy_agent] Failed — using fallback")
        return _fallback_copies(titulo, tese)
