# -*- coding: utf-8 -*-
"""
validator_agent.py — Content Quality Validator
=================================================
Agente validador INDEPENDENTE que atua em 2 momentos distintos:

  Modo "artigo":        Valida o artigo de blog gerado pelo writing_agent.
  Modo "pacote":        Valida os conteúdos derivados (roteiro TTS, copies,
                        thumbnails HTML) contra a pauta aprovada.

Princípio de independência:
  Este agente NUNCA é o mesmo que produziu o conteúdo.
  Ele atua como editor-chefe rígido, sem condescendência.
  Se o conteúdo não atende os critérios, retorna approved=False com issues
  detalhados para que o agente produtor regenere com as correções como steering.

Saída:
  {
    "approved":  bool,
    "score":     int (0–100),
    "issues":    [{"field": str, "severity": "blocker"|"warning", "description": str}],
    "summary":   str
  }

Critérios do modo "artigo" (blockers = reprova automaticamente):
  - Tem pelo menos 1 bloco de código Python? (blocker se não)
  - Tem pelo menos 1 diagrama Mermaid? (blocker se não)
  - Tem seção de Fundamentação Matemática com LaTeX? (blocker se não)
  - Tom é informal mas tecnicamente rigoroso? (warning se formal demais)
  - Alinhado com a tese e público da pauta? (blocker se desvio total)
  - Sem palavras da blacklist? (blocker se tiver)
  - Tem seção de Referências? (warning se não)
  - Extensão >= 800 palavras? (blocker se não)

Critérios do modo "pacote" (roteiro + copies + thumbnails):
  - Roteiro TTS: ZERO símbolos LaTeX nos scripts? (blocker)
  - Roteiro TTS: Termos técnicos em inglês com pronúncia fonética? (warning)
  - Roteiro: Tem hook nos primeiros 30s? (blocker)
  - Roteiro: Tem CTA de inscrição no canal? (blocker para YouTube)
  - Copies LinkedIn: Começa com gancho direto (não "Olá pessoal")? (blocker)
  - Copies: Dentro dos limites de caracteres? (blocker se exceder 1300 para LI)
  - Thumbnails HTML: HTML válido (tem DOCTYPE, body, width/height fixos)? (blocker)
  - Alinhamento pauta: título/tese/público refletidos nos conteúdos? (warning)
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

logger = logging.getLogger("cmo_agent.validator_agent")

# ── Blacklist global (compartilhada com prompts.py) ────────────────────────────

BLACKLIST_PHRASES = [
    "no mundo acelerado da ia",
    "mergulhe fundo",
    "revolucionário",
    "desvendando os segredos",
    "em constante evolução",
    "game-changer",
    "aproveite essa oportunidade",
    "transforme seu negócio",
    "na era digital",
]

# ── System Instruction ────────────────────────────────────────────────────────

VALIDATOR_INSTRUCTION = """Você é o Editor-Chefe e Validador de Qualidade da plataforma éozoré.
Você NUNCA produziu o conteúdo que está avaliando. Sua única missão é julgá-lo com rigor absoluto.

━━━ SEU PAPEL ━━━
Você é o guardião da qualidade editorial da plataforma. Não existe "quase bom".
Um conteúdo que falha em qualquer critério blocker é reprovado — sem exceção.
Você não sugere melhorias polidas. Você identifica falhas precisas e retorna JSON estruturado.

━━━ CRITÉRIOS DE VALIDAÇÃO — MODO ARTIGO ━━━

Os critérios B1 e B2 dependem do campo `tipo_artigo` da pauta:
  - "tecnico"     → B1 (código) + B2 (mermaid) + B3 (LaTeX) obrigatórios
  - "conceitual"  → B2 (mermaid) + B3 (LaTeX) obrigatórios. B1 não aplicável.
  - "estrategico" → apenas B3 (LaTeX) obrigatório. B1 e B2 não aplicáveis.

BLOCKERS:
  B1. Ausência de código (só para tipo "tecnico"): O artigo DEVE ter pelo menos 1 bloco ```python.
  B2. Ausência de Mermaid (para "tecnico" e "conceitual"): DEVE ter pelo menos 1 diagrama ```mermaid.
  B3. Ausência de LaTeX (todos os tipos): DEVE ter equações LaTeX ($...$ ou $$...$$).
      Rigor matemático é a identidade da plataforma — inclusive em artigos de estratégia.
  B4. Desvio de pauta: O conteúdo do artigo deve estar alinhado com o título e tese da pauta aprovada.
  B5. Extensão insuficiente: Mínimo de 800 palavras. Artigos rasos não têm lugar aqui.
  B6. Blacklist: Se qualquer frase proibida aparecer no texto, reprova.

WARNINGS (não reprova, mas registra como problema):
  W1. Tom muito formal: Se o texto soa como artigo acadêmico sem nenhuma informalidade.
  W2. Ausência de Referências: Deveria ter seção ## Referências e Fontes.
  W3. LaTeX inválido dentro de Mermaid: Fórmulas LaTeX nunca devem estar dentro de blocos mermaid.

━━━ CRITÉRIOS DE VALIDAÇÃO — MODO PACOTE ━━━

BLOCKERS:
  B1. LaTeX no TTS: Qualquer símbolo LaTeX ($, $$, \\, mathbb, nabla, etc.) nos scripts de fala.
      Scripts TTS devem ser 100% fonéticos — zero símbolos matemáticos.
  B2. Hook ausente: O roteiro YouTube deve ter um segmento com beat "hook" nos primeiros segmentos.
  B3. CTA ausente: O roteiro YouTube deve mencionar inscrição no canal em algum segmento.
  B4. Copy LinkedIn sem gancho: Se um post LinkedIn começa com saudação genérica (Olá, Oi pessoal, etc.)
  B5. Copy muito longo: Posts LinkedIn > 1400 caracteres.
  B6. Thumbnail HTML inválido: HTML sem DOCTYPE, sem dimensões fixas (width/height em px).

WARNINGS:
  W1. Fonética ausente: Termos técnicos em inglês sem pronuncia aportuguesada nos scripts TTS.
  W2. Desalinhamento: Título ou tese da pauta não aparece claramente nos conteúdos derivados.

━━━ FORMATO DE SAÍDA OBRIGATÓRIO ━━━
Responda SOMENTE com o JSON abaixo, sem markdown wrapper, sem ```json:

{
  "approved": true,
  "score": 85,
  "issues": [
    {
      "field": "artigo.codigo",
      "severity": "blocker",
      "description": "Nenhum bloco ```python encontrado. O artigo trata de implementação mas não inclui código."
    }
  ],
  "summary": "1 blocker encontrado: ausência de código Python. Regenerar com instrução explícita de incluir implementação."
}

Se aprovado: approved=true, issues pode ter warnings (severity=warning), score >= 70.
Se reprovado: approved=false, pelo menos 1 issue severity=blocker, score < 70.

REGRA ABSOLUTA: JSON válido, sem trailing commas, sem comentários.
"""

# ── Deterministic pre-checks (sem LLM) ───────────────────────────────────────

def _check_article_deterministic(
    article_text: str,
    pauta: dict,
) -> list[dict]:
    """Verificações rápidas e determinísticas antes de chamar o LLM.

    Os blockers B1 (código) e B2 (mermaid) são condicionais ao tipo_artigo:
      - "tecnico"     → B1 + B2 + B3 (LaTeX) aplicados
      - "conceitual"  → apenas B2 + B3 aplicados (sem exigência de código Python)
      - "estrategico" → apenas B3 (LaTeX) aplicado (sem código nem mermaid)

    Isso evita que artigos de liderança, negócio e estratégia sejam reprovados
    injustamente por critérios criados para conteúdo técnico de engenharia (BUG6).
    """
    issues: list[dict] = []
    text_lower = article_text.lower()

    # Lê o tipo de artigo da pauta — default "tecnico" para retrocompatibilidade
    tipo = pauta.get("tipo_artigo", "tecnico") or "tecnico"
    tipo = tipo.lower().strip()

    # B1: código Python — obrigatório apenas para artigos técnicos
    if tipo == "tecnico":
        if "```python" not in article_text and "```py\n" not in article_text:
            issues.append({
                "field": "artigo.codigo_python",
                "severity": "blocker",
                "description": "Nenhum bloco ```python encontrado. Artigo técnico sem código é incompleto.",
            })

    # B2: Mermaid — obrigatório para técnico e conceitual, não para estratégico
    if tipo in ("tecnico", "conceitual"):
        if "```mermaid" not in article_text:
            issues.append({
                "field": "artigo.mermaid",
                "severity": "blocker",
                "description": (
                    "Nenhum diagrama ```mermaid encontrado. "
                    f"Artigos {tipo}s exigem ao menos uma visualização."
                ),
            })

    # B3: LaTeX — obrigatório para todos os tipos (identidade matemática da plataforma)
    has_latex = bool(re.search(r"\$[^$]+\$", article_text))
    if not has_latex:
        issues.append({
            "field": "artigo.latex",
            "severity": "blocker",
            "description": "Nenhuma fórmula LaTeX encontrada. Rigor matemático é a identidade da plataforma.",
        })

    # B5: extensão
    word_count = len(article_text.split())
    if word_count < 800:
        issues.append({
            "field": "artigo.extensao",
            "severity": "blocker",
            "description": f"Artigo com apenas {word_count} palavras. Mínimo obrigatório: 800.",
        })

    # B6: blacklist
    for phrase in BLACKLIST_PHRASES:
        if phrase in text_lower:
            issues.append({
                "field": "artigo.blacklist",
                "severity": "blocker",
                "description": f"Frase proibida encontrada: \"{phrase}\". Remover e regenerar.",
            })
            break  # um blocker por frase já é suficiente

    # W3: LaTeX dentro de Mermaid
    mermaid_blocks = re.findall(r"```mermaid([\s\S]*?)```", article_text)
    for block in mermaid_blocks:
        if "$" in block or "\\" in block:
            issues.append({
                "field": "artigo.mermaid_latex",
                "severity": "warning",
                "description": "Símbolos LaTeX detectados dentro de bloco mermaid. Isso causa crash no renderizador.",
            })
            break

    return issues


def _check_package_deterministic(
    manifest: dict,
    copies: dict,
    thumbnails: dict,
) -> list[dict]:
    """Verificações rápidas do pacote de conteúdos derivados."""
    issues: list[dict] = []

    # B1: LaTeX nos scripts TTS
    latex_pattern = re.compile(r"(\$[^$]+\$|\$\$[^$]+\$\$|\\[a-zA-Z]+|mathbb|nabla|frac\{)")
    segments = manifest.get("youtube", {}).get("segments", [])
    for seg in segments:
        script = seg.get("script", "")
        if latex_pattern.search(script):
            issues.append({
                "field": f"roteiro.tts.{seg.get('id', '?')}",
                "severity": "blocker",
                "description": f"Símbolos LaTeX detectados no script TTS do segmento {seg.get('id')}. "
                               f"Scripts de fala devem ser 100% fonéticos.",
            })
            break  # um exemplo já basta para sinalizar

    # B2: Hook presente
    beats = [s.get("beat", "").lower() for s in segments]
    if not any("hook" in b or "gancho" in b for b in beats):
        issues.append({
            "field": "roteiro.hook",
            "severity": "blocker",
            "description": "Nenhum segmento com beat 'hook' encontrado no roteiro YouTube.",
        })

    # B3: CTA de inscrição
    all_scripts = " ".join(s.get("script", "") for s in segments).lower()
    cta_words = ["inscreva", "inscrev", "assina", "subscribe", "canal", "clique no sino"]
    if not any(w in all_scripts for w in cta_words):
        issues.append({
            "field": "roteiro.cta_inscricao",
            "severity": "blocker",
            "description": "Nenhum CTA de inscrição no canal detectado no roteiro YouTube.",
        })

    # B4: Copy LinkedIn sem saudação genérica
    li_posts = copies.get("linkedin_posts", [])
    bad_starts = ["olá", "oi pessoal", "olá pessoal", "hey ", "hey,", "bom dia", "boa tarde"]
    for post in li_posts:
        hook = post.get("hook", "").lower().strip()
        copy = post.get("copy", "").lower().strip()
        text_start = (hook or copy)[:40]
        if any(text_start.startswith(bad) for bad in bad_starts):
            issues.append({
                "field": f"copies.linkedin.{post.get('id', '?')}.gancho",
                "severity": "blocker",
                "description": f"Post LinkedIn {post.get('id')} começa com saudação genérica. "
                               f"Deve começar com contradição técnica ou dado concreto.",
            })

    # B5: Comprimento dos posts
    for post in li_posts:
        copy_full = f"{post.get('hook', '')}\n\n{post.get('copy', '')}"
        if len(copy_full) > 1400:
            issues.append({
                "field": f"copies.linkedin.{post.get('id', '?')}.tamanho",
                "severity": "blocker",
                "description": f"Post LinkedIn {post.get('id')} tem {len(copy_full)} chars. Máximo: 1400.",
            })

    # B6: Thumbnails HTML
    for key in ("option_minimal", "option_provocative"):
        html = thumbnails.get(key, "")
        if html and "<!DOCTYPE" not in html[:50].upper():
            issues.append({
                "field": f"thumbnails.{key}.doctype",
                "severity": "blocker",
                "description": f"Thumbnail {key}: HTML sem DOCTYPE. Playwright pode falhar ao renderizar.",
            })
        if html and not re.search(r"width:\s*\d+px", html):
            issues.append({
                "field": f"thumbnails.{key}.dimensoes",
                "severity": "blocker",
                "description": f"Thumbnail {key}: dimensões em px não encontradas. Use width/height absolutos.",
            })

    return issues


def _extract_validation_json(raw: str) -> dict:
    """Extrai JSON do output do LLM."""
    text = re.sub(r"<think>[\s\S]*?</think>", "", raw.strip())
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```\s*$", "", text, flags=re.MULTILINE)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        repaired = re.sub(r",\s*([}\]])", r"\1", text)
        return json.loads(repaired)


# ── Agent runners ──────────────────────────────────────────────────────────────

async def validate_article(
    article_text: str,
    pauta: dict,
    system_instruction: Optional[str] = None,
) -> dict:
    """
    Valida o artigo gerado pelo writing_agent.

    Fluxo:
      1. Verificações determinísticas rápidas (sem LLM)
      2. Se blockers determinísticos → retorna imediatamente (evita custo LLM)
      3. Caso contrário → LLM faz análise qualitativa completa
      4. Merge dos issues

    Returns:
        {"approved": bool, "score": int, "issues": [...], "summary": str}
    """
    determ_issues = _check_article_deterministic(article_text, pauta)
    has_blockers = any(i["severity"] == "blocker" for i in determ_issues)

    if has_blockers:
        # Falhou em critérios básicos — não precisamos nem chamar o LLM
        logger.info(
            "[validator] Artigo REPROVADO por %d blocker(s) determinísticos.",
            sum(1 for i in determ_issues if i["severity"] == "blocker"),
        )
        return {
            "approved": False,
            "score": 20,
            "issues": determ_issues,
            "summary": (
                f"{sum(1 for i in determ_issues if i['severity'] == 'blocker')} blocker(s) "
                f"detectados: {', '.join(i['field'] for i in determ_issues if i['severity'] == 'blocker')}. "
                "Regenerar com as correções como steering."
            ),
        }

    # LLM para análise qualitativa (tom, alinhamento, profundidade)
    titulo = pauta.get("titulo", "")
    tese   = pauta.get("tese", "")
    publico = pauta.get("publico", "")
    hardskills = ", ".join(pauta.get("hardskills", []))
    tipo_artigo = pauta.get("tipo_artigo", "tecnico") or "tecnico"

    models = get_model_config()
    config = LocalAgentConfig(
        system_instructions=system_instruction or VALIDATOR_INSTRUCTION,
        models=models,
    )

    prompt = (
        f"Valide o artigo abaixo no MODO ARTIGO.\n\n"
        f"PAUTA APROVADA:\n"
        f"  Título:       {titulo}\n"
        f"  Tese:         {tese}\n"
        f"  Público:      {publico}\n"
        f"  Hardskills:   {hardskills}\n"
        f"  Tipo artigo:  {tipo_artigo}\n\n"
        f"CRITÉRIOS APLICÁVEIS:\n"
        f"  {'B1 (código Python): SIM' if tipo_artigo == 'tecnico' else 'B1 (código Python): NÃO APLICÁVEL'}\n"
        f"  {'B2 (mermaid): SIM' if tipo_artigo in ('tecnico', 'conceitual') else 'B2 (mermaid): NÃO APLICÁVEL'}\n"
        f"  B3 (LaTeX): SEMPRE OBRIGATÓRIO\n\n"
        f"ARTIGO (primeiros 8000 chars):\n"
        f"{article_text[:8000]}\n\n"
        f"Retorne o JSON de validação. Seja rigoroso — não condescendente."
    )

    try:
        from vertex_generate import generate_text as _vertex_gen
        raw = await _vertex_gen(
            prompt=prompt,
            system_instruction=system_instruction or VALIDATOR_INSTRUCTION,
            temperature=0.3,
        )

        result = _extract_validation_json(raw)

        # Merge com issues determinísticos (warnings que passaram)
        existing_fields = {i["field"] for i in result.get("issues", [])}
        for di in determ_issues:
            if di["field"] not in existing_fields:
                result.setdefault("issues", []).append(di)

        logger.info(
            "[validator] Artigo %s score=%d issues=%d",
            "APROVADO" if result.get("approved") else "REPROVADO",
            result.get("score", 0),
            len(result.get("issues", [])),
        )
        return result

    except Exception as exc:
        logger.exception("[validator] LLM validation failed — returning partial result")
        return {
            "approved": len(determ_issues) == 0,
            "score": 60 if not determ_issues else 30,
            "issues": determ_issues,
            "summary": f"Validação LLM falhou ({exc}). Critérios determinísticos aplicados.",
        }


async def validate_package(
    manifest: dict,
    copies: dict,
    thumbnails: dict,
    pauta: dict,
    system_instruction: Optional[str] = None,
) -> dict:
    """
    Valida o pacote completo (roteiro TTS + copies + thumbnails).

    Returns:
        {"approved": bool, "score": int, "issues": [...], "summary": str}
    """
    determ_issues = _check_package_deterministic(manifest, copies, thumbnails)
    has_blockers = any(i["severity"] == "blocker" for i in determ_issues)

    if has_blockers:
        logger.info(
            "[validator] Pacote REPROVADO por %d blocker(s) determinísticos.",
            sum(1 for i in determ_issues if i["severity"] == "blocker"),
        )
        return {
            "approved": False,
            "score": 25,
            "issues": determ_issues,
            "summary": (
                f"{sum(1 for i in determ_issues if i['severity'] == 'blocker')} blocker(s): "
                f"{', '.join(i['field'] for i in determ_issues if i['severity'] == 'blocker')}."
            ),
        }

    # LLM para análise qualitativa do alinhamento
    titulo   = pauta.get("titulo", "")
    publico  = pauta.get("publico", "")
    obj      = pauta.get("objetivo_aprendizado", "")
    segments_sample = manifest.get("youtube", {}).get("segments", [])[:3]
    li_posts_sample = copies.get("linkedin_posts", [])[:1]

    models = get_model_config()
    config = LocalAgentConfig(
        system_instructions=system_instruction or VALIDATOR_INSTRUCTION,
        models=models,
    )

    prompt = (
        f"Valide o PACOTE DE CONTEÚDOS no MODO PACOTE.\n\n"
        f"PAUTA APROVADA:\n"
        f"  Título:   {titulo}\n"
        f"  Público:  {publico}\n"
        f"  Objetivo: {obj}\n\n"
        f"AMOSTRA DO ROTEIRO (3 segmentos):\n"
        f"{json.dumps(segments_sample, ensure_ascii=False, indent=2)}\n\n"
        f"AMOSTRA DOS COPIES LINKEDIN (1 post):\n"
        f"{json.dumps(li_posts_sample, ensure_ascii=False, indent=2)}\n\n"
        f"Verifique alinhamento, fonética TTS, CTAs e qualidade editorial. Retorne JSON."
    )

    try:
        from vertex_generate import generate_text as _vertex_gen
        raw = await _vertex_gen(
            prompt=prompt,
            system_instruction=system_instruction or VALIDATOR_INSTRUCTION,
            temperature=0.3,
        )
        result = _extract_validation_json(raw)
        existing_fields = {i["field"] for i in result.get("issues", [])}
        for di in determ_issues:
            if di["field"] not in existing_fields:
                result.setdefault("issues", []).append(di)

        logger.info(
            "[validator] Pacote %s score=%d issues=%d",
            "APROVADO" if result.get("approved") else "REPROVADO",
            result.get("score", 0),
            len(result.get("issues", [])),
        )
        return result

    except Exception as exc:
        logger.exception("[validator] LLM package validation failed")
        return {
            "approved": len(determ_issues) == 0,
            "score": 65 if not determ_issues else 30,
            "issues": determ_issues,
            "summary": f"Validação LLM falhou ({exc}). Critérios determinísticos aplicados.",
        }
