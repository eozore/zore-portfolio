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

Escala tipográfica — ISTO É VÍDEO, não uma página web:
  eyebrow (mono, caixa alta, letter-spacing .2em)  34px
  subtítulo / apoio                                34px
  texto de corpo e de coluna                       32px
  número ou destaque grande                        72px a 120px
  remate de rodapé                                 38px
  NENHUM texto abaixo de 28px, em nenhuma hipótese.

  O espectador assiste no celular, muitas vezes com o vídeo ocupando metade
  da tela. Tamanho de site (16px a 20px) fica ilegível: num quadro de
  1920x1080, 18px é 1,7% da altura. Prefira MENOS palavras em corpo grande
  a mais palavras em corpo pequeno.

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

    # Dimensão do quadro. Não existe `font_scale` aqui: o design system já
    # fixa a escala tipográfica em px absoluto (ver docstring do módulo), e um
    # clamp com piso de 14px contradiz a própria regra de "nunca abaixo de
    # 28px" — melhor não deixar a variável por perto para alguém reintroduzir
    # o mínimo errado interpolando-a no prompt mais tarde.
    dim_note = f"1920×1080px (horizontal)" if not is_vert else f"1080×1920px (vertical)"

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
13. O "Script falado" acima é a LOCUÇÃO — o que a voz vai dizer por cima deste
    slide. NUNCA reproduza esse texto na tela, nem inteiro nem em trechos, nem
    entre aspas, nem como rodapé ou legenda. Slide que exibe a própria narração
    faz o espectador ler e ouvir a mesma frase ao mesmo tempo, e não sobra
    atenção para nenhuma das duas.
14. O slide MOSTRA o que a fala não consegue: um diagrama, uma comparação, um
    número, uma estrutura. Use o script apenas para saber SOBRE O QUE desenhar.
15. Orçamento de texto por slide: no máximo ~30 palavras somando tudo. Se não
    couber, corte conteúdo — não diminua a fonte.
16. O container do slide leva `data-capitulo="..."` com um título de 3 a 6
    palavras para o trecho — é o que vira capítulo na descrição do YouTube.
    Escreva o ASSUNTO do trecho ("Vazamento temporal na validação"), não o
    rótulo da seção ("Problema") nem a categoria ("Engenharia de IA").

Retorne SOMENTE o HTML. Nenhum texto antes ou depois."""


# ── Validação do HTML gerado ──────────────────────────────────────────────────

# `slide` é a classe que o DECK usa para navegar entre seções. Um container
# com esse nome DENTRO do slide é apagado junto.
_CLASSE_RESERVADA = "slide"


def _renomear_container_slide(html: str) -> str:
    """
    Renomeia qualquer `class="slide"` gerado pelo modelo para `slide-container`.

    Defeito de 29/08: o prompt não reserva nenhum nome de classe, e o modelo
    escolheu `class="slide"` para o container raiz em 4 dos 9 slides. O deck
    navega com `.slide{display:none!important}` + `.slide.active`: a <section>
    ganha `.active` e aparece, o div interno homônimo não ganha nada e some,
    levando o conteúdo inteiro junto. Saíram 115 segundos de tela preta num
    vídeo de 344, sem um único erro em lugar nenhum — nem no job, nem no
    upload, nem no YouTube.

    A regra do deck já foi escopada para `body>.slide`, o que resolve o caso.
    Isto aqui é a segunda tranca: renomear na origem significa que reintroduzir
    o seletor solto lá não volta a apagar slide.
    """
    def troca(m: re.Match) -> str:
        classes = m.group(1).split()
        novas = [
            f"{_CLASSE_RESERVADA}-container" if c == _CLASSE_RESERVADA else c
            for c in classes
        ]
        return f'class="{" ".join(novas)}"'

    novo = re.sub(r'class="([^"]*)"', troca, html)
    if novo != html:
        logger.info("[slide_designer] container `.slide` renomeado para evitar o deck")
    return novo


def _narracao_vazou_para_a_tela(html: str, script: str, minimo: int = 60) -> bool:
    """
    True quando o slide exibe um trecho literal da locução.

    Nasceu do vídeo de 27/08: o slide `yt-02` trazia a narração inteira entre
    aspas num `.footer-script`. O espectador lia e ouvia a mesma frase ao mesmo
    tempo. O prompt agora proíbe, mas proibição em prompt é sugestão — esta
    checagem é o que de fato barra.

    Compara o TEXTO visível (sem tags, sem <style>) contra janelas do script.
    `minimo` em 60 caracteres evita acusar coincidência: um termo técnico
    repetido é esperado e legítimo; uma frase inteira não.
    """
    limpo = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", html, flags=re.IGNORECASE)
    limpo = re.sub(r"<[^>]+>", " ", limpo)
    limpo = re.sub(r"\s+", " ", limpo).lower()

    fala = re.sub(r"\s+", " ", (script or "")).strip().lower()
    if len(fala) < minimo:
        return False

    passo = max(1, minimo // 3)
    for i in range(0, len(fala) - minimo + 1, passo):
        if fala[i:i + minimo] in limpo:
            return True
    return False


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

    # No máximo UM grid de fundo. Dois significa que o modelo concatenou duas
    # composições completas na mesma resposta — aconteceu com o `yt-02` numa
    # regeração de 27/08, e uma composição empurra a outra para fora dos
    # 1080px. O HTML fica válido e passa em todas as outras checagens; só se vê
    # olhando o frame.
    #
    # ZERO não é rejeitado de propósito: slides legítimos desenham a grade com
    # outro nome de classe ou direto no fundo do container, e exigir a classe
    # `bg-grid` reprovaria composições boas — o `yt-07` desta mesma rodada é
    # uma delas.
    if len(re.findall(r'class="[^"]*\bbg-grid\b', html)) > 1:
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

        html = _renomear_container_slide(html)

        if _is_valid_slide_html(html, width, height) and not _narracao_vazou_para_a_tela(
            html, segment.get("script", "")
        ):
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

    # Peça vertical: só os itens do corte que são ilustração. Os itens de
    # avatar do corte reaproveitam o vídeo horizontal recortado, não precisam
    # de slide. A fala é a mesma do segmento de origem — o designer recebe o
    # segmento já com script herdado por _normalize_manifest().
    for item in manifest_dict.get("vertical_cut", {}).get("segments", []):
        if item.get("slide") and (item.get("script") or "").strip():
            tasks.append((item, "vertical", item["slide"]))

    # Compatibilidade com manifestos antigos, que traziam reels independentes
    # com roteiro próprio em vez de um corte do vídeo principal.
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
