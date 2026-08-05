# -*- coding: utf-8 -*-
"""
slide_designer_agent.py — Slide Designer Agent (BUG1 fix)
==========================================================
Gera HTML visual completo para um segmento do manifesto v2 do éozoré.

Cada slide é um documento HTML autossuficiente com:
  - Dimensões fixas (1920×1080 horizontal | 1080×1920 vertical)
  - Design system éozoré: #0d0f14 bg, Space Grotesk + JetBrains Mono, grid laranja
  - Elementos fd1 (visível) + fd2,fd3,fd4 (ocultos, revelados pelas âncoras)
  - Barras b1-b4 para beats comparativos
  - Animação fadeIn CSS
  - Logo éozoré no canto inferior direito

O HTML é gerado via Gemini (vertex_generate.py) com um prompt
template-driven por beat type, garantindo estrutura consistente.
O resultado é validado antes de ser inserido no manifesto.

8 beat types suportados:
  hook          → título grande + número de contraste central
  intro         → problema (esquerda) + solução (direita) com seta
  teoria        → equação central + decomposição revelada progressivamente
  codigo        → frame terminal dark com código fragmentado por âncora
  demo          → barras comparativas (b1-b4) com labels e valores
  comparativo   → tabela 2 colunas antes/depois
  consideracoes → checklist de bullets com ícones
  resumo        → 3 pontos numerados grandes + CTA final
"""

import os
import re
import logging
from typing import Optional

logger = logging.getLogger("cmo_agent.slide_designer_agent")

# ── Design tokens (espelham pacote-finetuning-v2.html) ────────────────────────

_DESIGN_TOKENS = """
Design system éozoré:
  --bg: #0d0f14
  --surface: #151920
  --surface2: #1b202a
  --line: #2a2f3a
  --orange: #e8873a (destaque principal)
  --amber: #f5b56a (destaque secundário)
  --terra: #c65d3b (acento terra)
  --text: #eae4dc (texto principal)
  --muted: #8a8378 (texto secundário)
  --good: #5fce8a (verde sucesso)
  font-display: 'Space Grotesk', sans-serif
  font-mono: 'JetBrains Mono', monospace

Grid de fundo (obrigatório em todos os slides):
  background-image: linear-gradient(rgba(232,135,58,.045) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(232,135,58,.045) 1px, transparent 1px);
  background-size: 44px 44px;

Animação fade (obrigatório para elementos fd*):
  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  .fd { animation: fadeIn 0.4s ease forwards; }

Elementos fd2, fd3, fd4: display:none por padrão — revelados pelo VideoEditor via JS.
Barras b1-b4: height:0 por padrão — animadas via JS na apresentação.
Logo éozoré: posição absoluta, bottom:40px, right:60px.
"""

# ── Prompt templates por beat type ────────────────────────────────────────────

def _build_prompt(
    segment: dict,
    pauta: dict,
    width: int,
    height: int,
) -> str:
    beat      = (segment.get("beat") or "teoria").lower().strip()
    script    = segment.get("script", "")[:600]  # primeiros 600 chars do script
    seg_id    = segment.get("id", "seg-01")
    anchors   = segment.get("anchors", [])
    titulo    = pauta.get("titulo", "éozoré")
    serie     = pauta.get("serie", "ia-para-lideres")
    is_vert   = height > width

    # Elementos revelados pelas âncoras (fd2, fd3, fd4, b1-b4)
    reveal_elements = [a.get("element") for a in anchors if a.get("element")]
    fd_elements     = [e for e in reveal_elements if e and e.startswith("fd")]
    bar_elements    = [e for e in reveal_elements if e and e.startswith("b")]

    # Dimensões e escala de fonte
    dim_note = f"1920×1080px (horizontal)" if not is_vert else f"1080×1920px (vertical)"
    font_scale = "clamp(14px, 1.5vw, 28px)" if not is_vert else "clamp(14px, 2.5vw, 32px)"

    # Template base de instrução por beat
    beat_instructions = {
        "hook": f"""
Beat: HOOK — Slide de abertura que para o scroll.
Crie um slide com:
  - Fundo escuro {dim_note}
  - Um número ou porcentagem grande e impactante em destaque (ex: "1%", "70B", "5x") — fonte 8-12rem, cor #e8873a
  - Uma linha de contexto abaixo do número — fonte 1.6rem, cor #eae4dc
  - O título "{titulo}" em fonte menor, canto superior esquerdo com border-left laranja
  - Não use mais de 2 linhas de texto além do número
  - Sem tabelas ou listas
  - fd1 = número + contexto (visível)
""",
        "intro": f"""
Beat: INTRO — Problema vs Solução com seta conectando.
Crie um slide com layout de 2 colunas lado a lado:
  - Coluna esquerda (problema): fundo levemente avermelhado (#c65d3b 10% opacidade), texto descrevendo o problema central do segmento
  - Seta → no centro (grande, laranja)
  - Coluna direita (solução): fundo levemente verde (#5fce8a 8% opacidade), texto descrevendo a solução
  - fd1 = coluna problema (visível)
  - fd2 = seta + coluna solução (oculto, revelado pela 1ª âncora)
  - Texto do segmento: "{script[:200]}"
""",
        "teoria": f"""
Beat: TEORIA — Equação/conceito central com decomposição progressiva.
Crie um slide com:
  - fd1 (visível): equação ou fórmula central em fonte monospace grande (2-3rem), centralizada, formatada visualmente
    Ex: "W = W₀ + ΔW" ou "ΔW = A × B" — use Unicode para símbolos matemáticos (não LaTeX)
  - fd2 (oculto): explicação da primeira parte da equação — revelado pela 1ª âncora
  - fd3 (oculto): explicação da segunda parte — revelado pela 2ª âncora
  - fd4 (oculto, se existir): insight ou consequência — revelado pela 3ª âncora
  - Kicker no topo: "{serie}" em font-mono, cor muted
  - Extraia a equação ou conceito matemático do script: "{script[:300]}"
  - Elementos revelados pelas âncoras: {fd_elements}
""",
        "codigo": f"""
Beat: CÓDIGO — Frame estilo terminal/editor com código fragmentado.
Crie um slide com:
  - Frame que imita um terminal: fundo #0f1117, borda #2a2f3a, header com 3 dots (●●●) em vermelho/amarelo/verde
  - fd1 (visível): primeira parte do código — as linhas iniciais
  - fd2 (oculto): linhas seguintes do código — reveladas pela 1ª âncora
  - fd3 (oculto, se existir): output ou resultado — revelado pela 2ª âncora
  - Fonte: JetBrains Mono, 1-1.2rem, cor #e8873a para palavras-chave
  - Extraia os trechos de código relevantes do script: "{script[:300]}"
  - Sem bordas excessivas — clean e legível
""",
        "demo": f"""
Beat: DEMO — Barras comparativas com labels e valores.
Crie um slide com gráfico de barras horizontal:
  - b1, b2, b3, b4: barras com widths diferentes (ex: 100%, 60%, 30%, 5%)
  - Cada barra tem: label à esquerda (nome da técnica/método), barra colorida, valor à direita
  - b1 (visível): barra mais larga — cor #e8873a
  - b2, b3, b4 (ocultos): revelados progressivamente
  - Use os valores/comparações do script: "{script[:300]}"
  - Layout: padding lateral generoso, barras com border-radius 4px, animação width de 0 para valor final via CSS transition
""",
        "comparativo": f"""
Beat: COMPARATIVO — Tabela 2 colunas antes/depois ou opção A vs opção B.
Crie um slide com:
  - Cabeçalho de 2 colunas: coluna A (negativa, border-top #c65d3b) e coluna B (positiva, border-top #5fce8a)
  - fd1 (visível): título das colunas
  - fd2 (oculto): primeira linha de comparação
  - fd3 (oculto): segunda linha de comparação
  - fd4 (oculto): terceira linha + conclusão
  - Extraia os 2 lados do comparativo do script: "{script[:300]}"
""",
        "consideracoes": f"""
Beat: CONSIDERAÇÕES — Checklist de bullets com ícones.
Crie um slide com lista de considerações/critérios:
  - fd1 (visível): título "Considerações" + primeiro bullet com ✓ ou → laranja
  - fd2 (oculto): segundo bullet — revelado pela 1ª âncora
  - fd3 (oculto): terceiro bullet — revelado pela 2ª âncora
  - fd4 (oculto, se existir): quarto bullet ou conclusão
  - Bullets extraídos do script: "{script[:300]}"
  - Ícones Unicode (✓ ✗ → ⚠ ★) — não SVG ou emoji externos
""",
        "resumo": f"""
Beat: RESUMO — 3 pontos numerados grandes + CTA.
Crie um slide com:
  - fd1 (visível): "3 pontos" em destaque + ponto 1 numerado grande (fonte 1.4rem)
  - fd2 (oculto): ponto 2 — revelado pela 1ª âncora
  - fd3 (oculto): ponto 3 — revelado pela 2ª âncora
  - CTA final (visible from start, small): "↗ inscreva-se no canal" ou similar em cor muted
  - Extraia os 3 pontos do script: "{script[:400]}"
""",
    }

    # Fallback para beats não mapeados
    beat_instruction = beat_instructions.get(beat, beat_instructions["teoria"])

    return f"""Você é o Slide Designer da plataforma éozoré. Gere o HTML completo de 1 slide para o segmento abaixo.

{_DESIGN_TOKENS}

SEGMENTO:
  ID: {seg_id}
  Beat: {beat}
  Dimensões: {dim_note} (width:{width}px, height:{height}px)
  Script falado: "{script}"
  Âncoras: {anchors}

INSTRUÇÃO DO BEAT:
{beat_instruction}

REGRAS OBRIGATÓRIAS:
1. Retorne APENAS o HTML completo, começando com <!DOCTYPE html> e terminando com </html>
2. HTML autossuficiente — sem dependências externas exceto Google Fonts CDN
3. Dimensões fixas no html e body: width:{width}px; height:{height}px; overflow:hidden
4. Google Fonts import obrigatório: Space Grotesk + JetBrains Mono
5. Grid de fundo obrigatório (veja design tokens acima)
6. Animação @keyframes fadeIn obrigatória no <style>
7. fd1 sempre visível. fd2, fd3, fd4 com display:none (classe "fd-hidden")
8. Logo éozoré: position:absolute; bottom:40px; right:60px; font-family monospace; cor rgba(234,228,220,0.25); font-size:1.1rem; letter-spacing:3px
9. IDs dos elementos fd1, fd2, fd3, fd4 e b1, b2, b3, b4 exatamente assim (para o VideoEditorJob revelar via JS)
10. Sem JavaScript no HTML — as âncoras são disparadas externamente pelo Playwright
11. Zero LaTeX (\\, $, mathbb) — use Unicode para símbolos matemáticos (₀ ₁ ² ∆ × → ≈ etc.)
12. Conteúdo em português brasileiro

Retorne SOMENTE o HTML. Nenhum texto antes ou depois."""


# ── Validação do HTML gerado ──────────────────────────────────────────────────

def _is_valid_slide_html(html: str, width: int, height: int) -> bool:
    """Verifica se o HTML gerado tem a estrutura mínima necessária."""
    if not html or len(html) < 200:
        return False
    if "<!DOCTYPE" not in html[:20].upper():
        return False
    if "</html>" not in html[-50:].lower():
        return False
    # Verificações de dimensões
    if str(width) not in html or str(height) not in html:
        return False
    # Deve ter pelo menos fd1
    if 'id="fd1"' not in html and "id='fd1'" not in html:
        return False
    return True


# ── Runner principal ──────────────────────────────────────────────────────────

async def run_slide_designer(
    segment: dict,
    pauta: dict,
    target: str = "horizontal",
) -> str:
    """
    Gera o HTML completo de um slide para o segmento dado.

    Args:
        segment: dict de um segmento do manifesto (id, beat, script, anchors...)
        pauta:   dict da pauta (titulo, serie, tese...)
        target:  "horizontal" (1920×1080) ou "vertical" (1080×1920)

    Returns:
        HTML string do slide, ou string vazia se falhar (fallback no caller).
    """
    from vertex_generate import generate_text

    width, height = (1920, 1080) if target == "horizontal" else (1080, 1920)
    seg_id = segment.get("id", "?")
    beat   = segment.get("beat", "teoria")

    # Segmentos sem slide não precisam de designer
    if not segment.get("slide"):
        logger.debug("[slide_designer] Segmento %s sem slide — pulando.", seg_id)
        return ""

    prompt = _build_prompt(segment, pauta, width, height)

    try:
        raw = await generate_text(
            prompt=prompt,
            system_instruction=(
                "Você é um designer front-end especializado em slides para vídeo. "
                "Gere HTML/CSS preciso, autossuficiente e visualmente impactante. "
                "Siga todas as regras do prompt à risca. Retorne apenas HTML."
            ),
            temperature=0.4,  # baixo para estrutura consistente
        )

        # Remove possíveis markdown wrappers
        html = re.sub(r"<think>[\s\S]*?</think>", "", raw).strip()
        html = re.sub(r"^```(?:html)?\s*", "", html, flags=re.MULTILINE)
        html = re.sub(r"\s*```\s*$", "", html, flags=re.MULTILINE)
        html = html.strip()

        if _is_valid_slide_html(html, width, height):
            logger.info(
                "[slide_designer] Slide OK: id=%s beat=%s target=%s (%d chars)",
                seg_id, beat, target, len(html),
            )
            return html
        else:
            logger.warning(
                "[slide_designer] HTML inválido para %s (beat=%s). "
                "Mantendo placeholder. html[:200]=%s",
                seg_id, beat, html[:200],
            )
            return ""

    except Exception as exc:
        logger.error("[slide_designer] Falha ao gerar slide %s: %s", seg_id, exc)
        return ""


# ── Geração em lote (todos os segmentos com slide de um manifesto) ────────────

async def design_all_slides(
    manifest_dict: dict,
    pauta: dict,
) -> dict[str, str]:
    """
    Gera HTMLs para todos os segmentos com slide != null no manifesto.
    Processa horizontal e vertical em paralelo por target.

    Args:
        manifest_dict: dict retornado por run_scriptwriter()
        pauta:         dict da pauta

    Returns:
        dict mapeando slide_id → html_string (apenas slides gerados com sucesso)
        Ex: {"yt-02": "<html>...", "yt-03": "<html>...", "r1-01": "<html>..."}
    """
    import asyncio

    # Coleta todos os pares (segment, target) que precisam de slide
    tasks: list[tuple[dict, str, str]] = []  # (segment, target, slide_id)

    for seg in manifest_dict.get("youtube", {}).get("segments", []):
        if seg.get("slide") and seg.get("script", "").strip():
            tasks.append((seg, "horizontal", seg["slide"]))

    for reel in manifest_dict.get("reels", []):
        for seg in reel.get("segments", []):
            if seg.get("slide") and seg.get("script", "").strip():
                tasks.append((seg, "vertical", seg["slide"]))

    if not tasks:
        logger.info("[slide_designer] Nenhum segmento com slide encontrado no manifesto.")
        return {}

    logger.info("[slide_designer] Gerando %d slides...", len(tasks))

    # Processa em paralelo com limite de concorrência (evitar rate limit do Vertex)
    semaphore = asyncio.Semaphore(3)  # máximo 3 chamadas simultâneas

    async def _generate_one(seg: dict, target: str, slide_id: str) -> tuple[str, str]:
        async with semaphore:
            html = await run_slide_designer(seg, pauta, target)
            return slide_id, html

    results = await asyncio.gather(
        *[_generate_one(seg, target, sid) for seg, target, sid in tasks],
        return_exceptions=True,
    )

    slides: dict[str, str] = {}
    for result in results:
        if isinstance(result, Exception):
            logger.warning("[slide_designer] Tarefa falhou: %s", result)
            continue
        slide_id, html = result
        if html:
            slides[slide_id] = html

    logger.info(
        "[slide_designer] Concluído: %d/%d slides gerados com sucesso.",
        len(slides), len(tasks),
    )
    return slides
