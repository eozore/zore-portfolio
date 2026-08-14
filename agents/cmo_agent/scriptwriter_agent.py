# -*- coding: utf-8 -*-
"""
scriptwriter_agent.py — YouTube Scriptwriter Specialist
Sprint 2 / G1: Agente especialista de roteiro segmentado com anchors[].

Output: JSON com segments[] no formato exato do manifesto v2
(pacote-finetuning-v2.html), pronto para ser consumido pelo
manifest_builder.py e pelo video_editor_job.

Cada segmento tem:
  id, slide, beat, script, anchors[]
onde cada âncora é:
  {"on_phrase": str, "action": "show_slide"|"reveal"|"highlight",
   "element"?: str}  # element = id CSS (fd2, fd3, b4, etc.)
"""

import os
import sys
import json
import re
import logging
from typing import Optional

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from google.antigravity import Agent, LocalAgentConfig
from model_config import get_model_config

logger = logging.getLogger("cmo_agent.scriptwriter_agent")

# ── System Instruction ────────────────────────────────────────────────────────

SCRIPTWRITER_INSTRUCTION = """Você é o Scriptwriter Agent da plataforma éozoré (eozore.com).
Sua especialidade exclusiva: transformar um artigo técnico + pauta aprovada em um roteiro
YouTube segmentado no formato JSON do manifesto v2 — o mesmo usado pelo pipeline de vídeo.

CAPITALIZAÇÃO (regra inegociável): os campos "title" (do vídeo e dos reels) SEMPRE em sentence case — só a primeira letra da frase em maiúscula, mais nomes próprios e siglas (RAG, LLM, GCP). NUNCA Title Case (Cada Palavra Maiúscula é proibido). Sem emojis ou ícones em títulos.

━━━ PERSONA DO APRESENTADOR ━━━
Victor Zoré: Líder Técnico em IA Generativa e ML, formado em Matemática pela UFSCar.
Tom: conversacional, direto, professoral-acessível — como explicar um conceito a um colega sênior
num café. Sem formalidades. Sem clichês de marketing. Autoridade técnica que não precisa se anunciar.

━━━ REGRAS CRÍTICAS PARA TTS ━━━

REGRA 1 — ZERO LaTeX no script.
Equações são faladas por extenso em português fonético:
  "$W \\in \\mathbb{R}^{m \\times n}$" → "a matriz W de dimensão m por n"
  "$\\Delta W = BA$" → "a variação de W igual a B vezes A"
  "\\times" → "vezes" | "=" → "igual a" | "%" → "por cento"

REGRA 2 — Fonética de termos técnicos em inglês (TTS brasileiro):
  "LoRA" → "lóra" | "fine-tuning" → "fain-tiúning" | "tokens" → "tóquens"
  "framework" → "freim-uórc" | "LLM" → "éli-éli-êmi" | "API" → "ê-pê-í"
  "embedding" → "êmbeding" | "batch" → "bátch" | "rank" → "rênqui"
  "QLoRA" → "qiu-lóra" | "TinyLoRA" → "tiny-lóra"

REGRA 3 — Scripts são 100% pronúncia pura.
Sem fórmulas, sem code blocks, sem markdown no texto de fala.
Parênteses com pronunciamento auxiliar são permitidos: "a função de custo (J de teta)"

━━━ ESTRUTURA DE BEATS ━━━
hook          — provocação que prende nos primeiros 30s
intro         — apresenta o problema e o que o espectador aprende
teoria        — fundamento matemático/conceitual (o PORQUÊ)
codigo        — implementação prática (o COMO)
demo          — resultado, métricas, gráficos
comparativo   — tabela ou gráfico comparativo de trade-offs
consideracoes — quando usar, ordem de investimento, decisão executiva
resumo        — 3 pontos para levar para a reunião + CTA

━━━ REGRAS DE ÂNCORAS (anchors[]) ━━━
Cada âncora dispara uma animação no slide quando aquela frase é falada.
Para cada segmento com slide, gere 1 a 4 âncoras onde faz sentido:

  show_slide  — dispara quando o slide deve entrar (normalmente a primeira âncora)
  reveal      — revela um elemento que estava escondido (element = id CSS: fd2, fd3, fd4, b1–b4)
  highlight   — pulsa/destaca um elemento já visível

Ordem dos reveals: fd1 aparece com o slide, fd2 no segundo momento chave, fd3 no terceiro.
Use os ids do design system: fd1, fd2, fd3, fd4 (fadein), b1, b2, b3, b4 (barras de gráfico).

Segmentos sem slide (avatar falando em tela cheia): anchors = [].

━━━ DURAÇÃO ALVO ━━━
Vídeo principal (YouTube): 5–12 minutos
  → entre 6 e 12 segmentos, cada script com 60–150 palavras.
Reels (segmentos verticais): 20–30 segundos cada
  → script com 40–70 palavras por segmento.

━━━ FORMATO DE SAÍDA OBRIGATÓRIO ━━━
Responda SOMENTE com o bloco JSON abaixo, sem texto antes ou depois,
sem markdown wrapper (sem ```json), sem comentários:

{
  "video_id": "slug-curto-do-video",
  "series":   "nome-da-serie-no-blog",
  "title":    "Título completo do vídeo",
  "language": "pt-BR",
  "audio_naming": "{video_id}__{segment_id}.wav",
  "youtube": {
    "deck": "yt",
    "resolution": {"width": 1920, "height": 1080},
    "overlay": {
      "mode": "slide-full",
      "avatar_position": "bottom-right",
      "avatar_scale": 0.28
    },
    "segments": [
      {
        "id":      "yt-01",
        "slide":   null,
        "beat":    "hook",
        "script":  "Texto falado sem LaTeX, em português fonético.",
        "anchors": []
      },
      {
        "id":      "yt-02",
        "slide":   "yt-02",
        "beat":    "intro",
        "script":  "Texto falado do segundo segmento.",
        "anchors": [
          {"on_phrase": "frase exata que dispara", "action": "show_slide"},
          {"on_phrase": "outra frase chave",        "action": "reveal", "element": "fd2"}
        ]
      }
    ]
  },
  "reels": [
    {
      "reel_id": "reel-01",
      "title":   "Título do Reel 01",
      "deck":    "r1",
      "resolution": {"width": 1080, "height": 1920},
      "overlay": {
        "mode": "slide-full",
        "avatar_position": "bottom-center",
        "avatar_scale": 0.35
      },
      "segments": [
        {
          "id":      "r1-01",
          "slide":   "r1-01",
          "beat":    "gancho",
          "script":  "Texto do gancho (30s máx).",
          "anchors": [{"on_phrase": "frase do gancho", "action": "show_slide"}]
        },
        {
          "id":      "r1-02",
          "slide":   "r1-02",
          "beat":    "insight",
          "script":  "Ensina o conceito central.",
          "anchors": [
            {"on_phrase": "palavra-chave do insight", "action": "show_slide"},
            {"on_phrase": "número ou resultado",       "action": "reveal", "element": "fd3"}
          ]
        },
        {
          "id":      "r1-03",
          "slide":   "r1-03",
          "beat":    "gap + cta",
          "script":  "Há mais no vídeo completo. Link na bio.",
          "anchors": [{"on_phrase": "vídeo completo", "action": "show_slide"}]
        }
      ]
    }
  ]
}

REGRA ABSOLUTA: Não adicione campos extras. Não quebre o JSON. Não use trailing commas.
O pipeline usa json.loads() diretamente no seu output.
"""

# ── Helper: limpa o output do LLM para garantir JSON puro ─────────────────────

def _extract_json(raw: str) -> str:
    """Remove delimitadores markdown e extrai apenas o JSON."""
    text = raw.strip()
    # Remove ```json ... ``` ou ``` ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```\s*$",       "", text, flags=re.MULTILINE)
    # Remove <think>...</think> (Gemini thinking mode)
    text = re.sub(r"<think>[\s\S]*?</think>", "", text)
    return text.strip()


def _repair_json(text: str) -> str:
    """Tenta reparar trailing commas antes de fazer parse."""
    return re.sub(r",\s*([}\]])", r"\1", text)


# ── Agent runner ───────────────────────────────────────────────────────────────

async def run_scriptwriter(
    pauta: dict,
    article_content: str,
    system_instruction: Optional[str] = None,
) -> dict:
    """
    Gera o manifesto de roteiro segmentado no formato v2.

    Args:
        pauta: PautaConcebida dict — {titulo, subtitulo, tese, publico, duracao_alvo, serie}
        article_content: Artigo técnico em Markdown (conteúdo gerado pelo writing_agent)
        system_instruction: Override opcional da instrução de sistema

    Returns:
        dict com a estrutura completa do manifesto v2 (pronto para json.dumps)
    """
    models = get_model_config()
    config = LocalAgentConfig(
        system_instructions=system_instruction or SCRIPTWRITER_INSTRUCTION,
        models=models,
    )

    titulo       = pauta.get("titulo", "Vídeo Técnico éozoré")
    subtitulo    = pauta.get("subtitulo", "")
    tese         = pauta.get("tese", "")
    publico      = pauta.get("publico", "líderes técnicos em IA/ML")
    duracao_alvo = pauta.get("duracao_alvo", "8 min")
    serie        = pauta.get("serie", "eozore-series")

    prompt = (
        f"Gere o manifesto de roteiro v2 para o vídeo abaixo.\n\n"
        f"=== PAUTA APROVADA ===\n"
        f"Título: {titulo}\n"
        f"Subtítulo: {subtitulo}\n"
        f"Tese: {tese}\n"
        f"Público: {publico}\n"
        f"Duração alvo: {duracao_alvo}\n"
        f"Série: {serie}\n\n"
        f"=== ARTIGO DE BASE ===\n"
        f"{article_content[:14000]}\n\n"
        f"Produza o JSON completo do manifesto v2 com todos os segmentos do YouTube + 2 Reels,"
        f" respeitando estritamente as regras TTS e de âncoras."
    )

    try:
        from vertex_generate import generate_text as vertex_generate_text
        raw_text = await vertex_generate_text(
            prompt=prompt,
            system_instruction=system_instruction or SCRIPTWRITER_INSTRUCTION,
            temperature=0.5,
        )
        logger.info(f"[scriptwriter] Raw response length: {len(raw_text)} chars")

        clean = _extract_json(raw_text)
        try:
            manifest = json.loads(clean)
        except json.JSONDecodeError:
            repaired = _repair_json(clean)
            manifest = json.loads(repaired)

        logger.info(
            f"[scriptwriter] Manifest OK — "
            f"{len(manifest.get('youtube', {}).get('segments', []))} YT segments, "
            f"{len(manifest.get('reels', []))} reels"
        )
        return manifest

    except Exception as exc:
        logger.exception("[scriptwriter] Failed to generate manifest")
        raise RuntimeError(f"scriptwriter_agent failed: {exc}") from exc
