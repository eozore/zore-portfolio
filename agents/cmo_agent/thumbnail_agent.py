# -*- coding: utf-8 -*-
"""
thumbnail_agent.py — Thumbnail Design Specialist
Sprint 2 / G1: Gera 2 opções de thumbnail HTML dark premium (1200x628px)
prontas para renderizar via Playwright.

Segue o design system da série éozoré:
  Paleta: #0d0f14 (bg), #e8873a (laranja), #5fce8a (verde), #eae4dc (texto)
  Fontes: Space Grotesk (display) + JetBrains Mono (mono)
  Estilo: minimalista, contraste numérico, ilustração SVG inline

Output: {"option_minimal": html_str, "option_provocative": html_str}
"""

import os
import sys
import re
import logging
from typing import Optional

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from google.antigravity import Agent, LocalAgentConfig
from model_config import get_model_config

logger = logging.getLogger("cmo_agent.thumbnail_agent")

# ── System Instruction ────────────────────────────────────────────────────────

THUMBNAIL_INSTRUCTION = """Você é o Thumbnail Designer da plataforma éozoré (eozore.com).
Sua especialidade: gerar thumbnails HTML+SVG dark premium, prontos para renderização via Playwright.

━━━ DESIGN SYSTEM ━━━
Dimensões: 1200 × 628px (og:image, 16:9 YouTube)
Fundo: #0d0f14 (quase preto)
Paleta de destaque: laranja #e8873a, âmbar #f5b56a, verde #5fce8a, vermelho #e06555
Texto principal: #eae4dc
Texto secundário/muted: #8a8378
Fontes: Space Grotesk (display) + JetBrains Mono (mono) — via Google Fonts
Grid de fundo (sutil): linhas horizontais e verticais rgba(232,135,58,0.045) a cada 44px
Logo "éozoré" no canto inferior direito: cor #e8873a, JetBrains Mono, 0.9rem

━━━ ANATOMIA DAS 2 OPÇÕES ━━━

OPÇÃO MINIMAL (contraste conceitual):
- Elemento dominante: ilustração SVG inline do conceito central (matriz, grafo, equação visual)
- Título em Space Grotesk Bold, máx 2 linhas, letra-spacing -0.03em
- Kicker (// série · episódio) em JetBrains Mono, laranja, uppercase, letter-spacing 0.3em
- Paleta fria — sem cores quentes no fundo, apenas no elemento SVG
- Objetivo: atrai o público técnico que reconhece a ilustração do conceito

OPÇÃO PROVOCATIVA (contraste numérico ou de dados):
- Elemento dominante: número grande ou contraste chocante (ex: "70B → 13", "140GB → 35GB")
- Número principal: Space Grotesk Bold, 6–10rem, cor laranja ou verde
- Subtexto: JetBrains Mono, muted, que explica o número
- Background com gradiente radial sutil partindo do centro
- Objetivo: maior CTR — gera curiosidade imediata antes de qualquer contexto

━━━ REGRAS TÉCNICAS ━━━
1. HTML self-contained: fontes via <link Google Fonts>, sem arquivos externos além das fontes
2. Dimensões fixas: <div style="width:1200px;height:628px;..."> — não use vw/vh/%, use px absoluto
3. SVG inline: todos os SVGs inline dentro do HTML, sem src externo
4. Sem JavaScript
5. Sem animações CSS (Playwright renderiza frame estático)
6. Use position:absolute para compor os elementos sobre o fundo
7. Cada HTML é completo: <!DOCTYPE html>...<html>...<head>...<body>...</body></html>

━━━ FORMATO DE SAÍDA ━━━
Responda APENAS com o bloco JSON abaixo (sem markdown wrapper, sem ```json):

{
  "option_minimal": "<!DOCTYPE html>...(HTML completo da opção minimal)...",
  "option_provocative": "<!DOCTYPE html>...(HTML completo da opção provocativa)..."
}

REGRA ABSOLUTA: O JSON deve ter exatamente 2 chaves. As strings HTML devem ter aspas internas
escapadas como \\". Não use single quotes dentro das strings HTML para evitar conflito.
Use aspas duplas para todos os atributos HTML e escape-as com \\\\.
"""

# ── Fallback: gera thumbnails HTML sem LLM para o caso de falha ────────────────

_BASE_CSS = """
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{width:1200px;height:628px;overflow:hidden;background:#0d0f14;font-family:'Space Grotesk',sans-serif;color:#eae4dc;position:relative}
body::before{content:'';position:absolute;inset:0;background:linear-gradient(rgba(232,135,58,.045) 1px,transparent 1px),linear-gradient(90deg,rgba(232,135,58,.045) 1px,transparent 1px);background-size:44px 44px;pointer-events:none}
.wrap{position:relative;width:100%;height:100%;display:flex;flex-direction:column;justify-content:center;padding:64px 72px}
.kicker{font-family:'JetBrains Mono',monospace;font-size:.85rem;letter-spacing:.28em;text-transform:uppercase;color:#e8873a;margin-bottom:20px}
.kicker::before{content:'// '}
.title{font-size:3.4rem;font-weight:700;letter-spacing:-.03em;line-height:1.1;max-width:760px}
.title em{color:#e8873a;font-style:normal}
.subtitle{margin-top:18px;font-family:'JetBrains Mono',monospace;font-size:.9rem;color:#8a8378;letter-spacing:.06em}
.logo{position:absolute;bottom:32px;right:48px;font-family:'JetBrains Mono',monospace;font-size:.9rem;color:#e8873a;letter-spacing:.1em}
.logo::before{content:'// '}
</style>
"""


def _build_fallback_minimal(titulo: str, subtitulo: str, serie: str) -> str:
    title_html = titulo.replace('"', '&quot;')
    sub_html   = subtitulo.replace('"', '&quot;')
    serie_html = serie.replace('"', '&quot;')
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8">{_BASE_CSS}</head>
<body>
<div class="wrap">
  <div class="kicker">{serie_html}</div>
  <h1 class="title">{title_html}</h1>
  <p class="subtitle">{sub_html}</p>
</div>
<div class="logo">éozoré</div>
</body></html>"""


def _build_fallback_provocative(titulo: str, tese: str) -> str:
    # Tenta extrair um número de contraste do título (ex: "70B → 13")
    numbers = re.findall(r"\d+[\w.,]*", titulo)
    contrast = " → ".join(numbers[:2]) if len(numbers) >= 2 else titulo[:30]
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:1200px;height:628px;overflow:hidden;background:radial-gradient(circle at 55% 50%,#1a1106,#0d0f14 70%);font-family:'Space Grotesk',sans-serif;color:#eae4dc;position:relative}}
.wrap{{position:relative;width:100%;height:100%;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:48px}}
.number{{font-size:7.5rem;font-weight:700;letter-spacing:-.04em;color:#e8873a;line-height:1}}
.sub{{margin-top:20px;font-family:'JetBrains Mono',monospace;font-size:1rem;color:#8a8378;letter-spacing:.08em}}
.tese{{margin-top:14px;font-size:1.2rem;color:#eae4dc;max-width:700px;line-height:1.4}}
.logo{{position:absolute;bottom:32px;right:48px;font-family:'JetBrains Mono',monospace;font-size:.9rem;color:#e8873a}}
</style>
</head>
<body>
<div class="wrap">
  <div class="number">{contrast}</div>
  <p class="sub">// {tese}</p>
  <p class="tese">{titulo}</p>
</div>
<div class="logo">// éozoré</div>
</body></html>"""


# ── Helper: extrai JSON da resposta do LLM ────────────────────────────────────

def _extract_thumbnail_json(raw: str, titulo: str, subtitulo: str, tese: str, serie: str) -> dict:
    text = raw.strip()
    text = re.sub(r"<think>[\s\S]*?</think>", "", text)
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```\s*$",       "", text, flags=re.MULTILINE)
    text = text.strip()

    try:
        data = json_loads_safe(text)
        if "option_minimal" in data and "option_provocative" in data:
            return data
    except Exception:
        pass

    logger.warning("[thumbnail] Could not parse LLM JSON — using fallback templates")
    return {
        "option_minimal":     _build_fallback_minimal(titulo, subtitulo, serie),
        "option_provocative": _build_fallback_provocative(titulo, tese),
    }


def json_loads_safe(text: str) -> dict:
    """json.loads com reparação de trailing commas."""
    import json
    try:
        return json.loads(text)
    except Exception:
        repaired = re.sub(r",\s*([}\]])", r"\1", text)
        return json.loads(repaired)


# ── Agent runner ───────────────────────────────────────────────────────────────

async def run_thumbnail(
    pauta: dict,
    system_instruction: Optional[str] = None,
) -> dict:
    """
    Gera 2 opções de thumbnail HTML para o título/tese da pauta aprovada.

    Args:
        pauta: {titulo, subtitulo, tese, publico, duracao_alvo, serie}
        system_instruction: Override opcional

    Returns:
        {"option_minimal": html_str, "option_provocative": html_str}
    """
    titulo    = pauta.get("titulo", "Vídeo Técnico éozoré")
    subtitulo = pauta.get("subtitulo", "")
    tese      = pauta.get("tese", "")
    serie     = pauta.get("serie", "eozore-series")

    models = get_model_config()
    config = LocalAgentConfig(
        system_instructions=system_instruction or THUMBNAIL_INSTRUCTION,
        models=models,
    )

    prompt = (
        f"Crie as 2 opções de thumbnail HTML 1200×628px para o vídeo abaixo.\n\n"
        f"Título completo:  {titulo}\n"
        f"Subtítulo:        {subtitulo}\n"
        f"Tese/Ângulo:      {tese}\n"
        f"Série:            {serie}\n\n"
        f"OPÇÃO MINIMAL: ilustração SVG inline do conceito central '{tese}'.\n"
        f"OPÇÃO PROVOCATIVA: contraste numérico ou dado chocante extraído do título.\n\n"
        f"Retorne SOMENTE o JSON com as 2 chaves."
    )

    try:
        from vertex_generate import generate_text as vertex_generate_text
        raw_text = await vertex_generate_text(
            prompt=prompt,
            system_instruction=system_instruction or THUMBNAIL_INSTRUCTION,
            temperature=0.7,
        )
        logger.info(f"[thumbnail] Raw response: {len(raw_text)} chars")

        result = _extract_thumbnail_json(raw_text, titulo, subtitulo, tese, serie)
        logger.info("[thumbnail] Thumbnails generated OK")
        return result

    except Exception as exc:
        logger.exception("[thumbnail] Agent failed — using fallback templates")
        return {
            "option_minimal":     _build_fallback_minimal(titulo, subtitulo, serie),
            "option_provocative": _build_fallback_provocative(titulo, tese),
        }
