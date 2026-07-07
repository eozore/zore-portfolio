# -*- coding: utf-8 -*-
"""
speak_extractor_agent.py — Agente especializado em extrair texto limpo para TTS (HeyGen)
Recebe um roteiro completo (com blocos de cena, LaTeX, etc.) e devolve
SOMENTE as falas do apresentador em português fonético, prontas para síntese de voz.
"""

import os
import sys
import re
import logging

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from google.antigravity import Agent, LocalAgentConfig
from model_config import get_model_config

logger = logging.getLogger("cmo_agent.speak_extractor")

SPEAK_EXTRACTOR_INSTRUCTION = """Você é um Especialista em TTS (Text-to-Speech) para o avatar digital Victor Zore no HeyGen.

Sua ÚNICA missão é receber um roteiro completo e extrair apenas o texto que será FALADO pelo avatar.

## REGRAS ABSOLUTAS DE LIMPEZA:

### O que REMOVER completamente (zero tolerância):
1. Todos os blocos de indicação de tela: > [TELA: ...], > [CENA: ...], > [CORTE: ...], > [B-ROLL: ...], qualquer linha que começa com >
2. Todos os cabeçalhos markdown: #, ##, ###, ####
3. Todas as fórmulas LaTeX: $...$, $$...$$, qualquer sequência com backslash
4. Todos os blocos de código: triple-backticks de qualquer linguagem
5. Linhas de separação: ---, ***, ===
6. Listas com marcadores — converta para prosa falada fluida se necessário
7. Emojis e caracteres especiais: 🚀, ⚠️, 💡, ★, ✓, →, ←, ≤, ≥, ∑, ∏, ∞
8. Indicações de formatação markdown: **texto**, *texto*, _texto_, `código`
9. URLs e links: [texto](url), https://...
10. Qualquer palavra ou símbolo em LaTeX ou notação matemática formal

### O que REESCREVER de forma fonética em PT-BR:
- "LLM" → "éle-éle-êmi"
- "API" → "éi-pi-ái"
- "GPU" → "gê-pê-u"
- "CPU" → "cê-pê-u"
- "ML" → "êmi-éle"
- "AI" → "éi-ái"
- "framework" → "frêim-uórc"
- "tokens" → "tóquens"
- "embedding" → "êmbedin"
- "fine-tuning" → "fáin-tiúning"
- "prompt" → "prómt"
- "dataset" → "dêita-set"
- "pipeline" → "páip-lain"
- "benchmark" → "bênch-marque"
- "overfitting" → "óver-fiting"
- "dropout" → "dróp-aut"
- "softmax" → "sóft-máxi"
- "attention" → "atêntion"
- "transformer" → "trânsfórmê"

### Tom e estilo de fala:
- Conversacional, direto, como uma conversa entre engenheiros
- Sem formalidades excessivas
- Frases curtas e naturais (máx. 2 linhas por parágrafo de fala)
- Use pausas naturais com vírgulas e pontos
- Mantenha o entusiasmo técnico mas sem exagero

### Estrutura de saída:
- Texto corrido, sem nenhuma formatação markdown
- Parágrafos separados por linha em branco
- Nenhum símbolo especial
- APENAS português fonético brasileiro

### CRÍTICO:
- Se uma linha inteira for instrução de câmera/tela, APAGUE ela completamente
- NÃO adicione frases introdutórias suas como "Aqui está o texto extraído:"
- Comece DIRETAMENTE com o texto falado
- Termine DIRETAMENTE com a última fala (sem marcadores de fim)
"""

async def extract_spoken_text(full_script: str) -> str:
    """
    Recebe o roteiro completo (markdown com blocos de cena + fala)
    e retorna APENAS o texto limpo para TTS, em português fonético.
    """
    models = get_model_config()
    config = LocalAgentConfig(
        system_instructions=SPEAK_EXTRACTOR_INSTRUCTION,
        models=models
    )

    prompt = (
        "Extraia APENAS o texto falado do roteiro abaixo. "
        "Remova completamente todos os blocos de tela, cena, LaTeX, markdown e código. "
        "Converta siglas e termos técnicos para forma fonética em português. "
        "Retorne SOMENTE o texto limpo que o avatar deve falar, sem nenhuma formatação.\n\n"
        f"ROTEIRO COMPLETO:\n{full_script}"
    )

    async with Agent(config=config) as agent:
        response = await agent.chat(prompt)
        raw = await response.text()

    # Fallback safety: strip any remaining markdown headers or blockquotes
    lines = raw.split('\n')
    clean_lines = []
    in_code_block = False
    for line in lines:
        stripped = line.strip()
        # Handle code blocks
        if stripped.startswith('```'):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        # Skip blockquote lines, headers, separator lines
        if stripped.startswith('>'):
            continue
        if stripped.startswith('#'):
            continue
        if stripped in ('---', '***', '==='):
            continue
        # Remove inline markdown bold/italic
        stripped = re.sub(r'\*\*(.+?)\*\*', r'\1', stripped)
        stripped = re.sub(r'\*(.+?)\*', r'\1', stripped)
        stripped = re.sub(r'_(.+?)_', r'\1', stripped)
        stripped = re.sub(r'`(.+?)`', r'\1', stripped)
        # Remove LaTeX inline
        stripped = re.sub(r'\$[^$]+\$', '', stripped)
        stripped = re.sub(r'\$\$[^$]+\$\$', '', stripped)
        stripped = re.sub(r'\\[a-zA-Z]+\{[^}]*\}', '', stripped)
        stripped = re.sub(r'\\[a-zA-Z]+', '', stripped)
        # Remove URLs
        stripped = re.sub(r'https?://\S+', '', stripped)
        stripped = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', stripped)
        stripped = stripped.strip()
        if stripped:
            clean_lines.append(stripped)

    return '\n\n'.join(clean_lines)
