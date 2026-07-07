# -*- coding: utf-8 -*-
"""
critic_agent.py — Ecosystem Critic Agent assessing new topics against historical memory
"""

import os
import sys
import logging
from typing import Optional

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from google.antigravity import Agent, LocalAgentConfig
from model_config import get_model_config
from tools import get_ecosystem_memory, db

logger = logging.getLogger("cmo_agent.critic_agent")

CRITIC_INSTRUCTION = """Você é o Ecosystem Critic Agent da plataforma éozoré. 
Sua missão é ler o novo tópico proposto pelo Victor Zore, analisar o histórico recente de artigos publicados e fornecer notas críticas de "Steering" (direcionamento editorial) e continuidade técnica para o redator de artigos.

Seu foco principal:
1. **Evitar redundância:** Avalie se o assunto já foi abordado recentemente de forma idêntica.
2. **Continuidade de Linha Editorial:** Diga como conectar o novo tópico com as conclusões dos artigos anteriores (ex: se o último artigo foi sobre Variáveis Aleatórias, e o novo é sobre Regressão, sugira abordar a distribuição do ruído de forma encadeada).
3. **Profundidade Acadêmica:** Avalie se o foco sugerido respeita a hierarquia didática (explicar o porquê matemático antes do código).
4. **Foco Técnico de IA:** Defina 2 ou 3 conceitos profundos (de preferência estatísticos ou de álgebra linear) que devem ser explicitamente desenvolvidos no corpo do novo texto para dar robustez.

Emita suas notas de direcionamento em um formato Markdown limpo e objetivo, prefixado com "NOTAS DE DIRECIONAMENTO EDITORIAL (STEERING):".
"""

async def run_critic(topic: str, context: str = "", system_instruction: str = None) -> str:
    """
    Executa a análise crítica comparando o novo tópico com o histórico do blog.
    """
    models = get_model_config()
    
    # 1. Recupera o histórico do ecossistema em formato de string legível
    history_text = get_ecosystem_memory()

    config = LocalAgentConfig(
        system_instructions=system_instruction or CRITIC_INSTRUCTION,
        models=models
    )

    prompt = (
        f"Analise o novo tópico proposto abaixo:\n\n"
        f"NOVO TÓPICO PROPOSTO: {topic}\n"
        f"CONTEXTO DO AUTOR: {context}\n\n"
        f"HISTÓRICO RECENTE DE PUBLICAÇÕES DO BLOG:\n"
        f"{history_text}\n\n"
        f"Gere o relatório de steering com foco na continuidade editorial e profundidade teórica."
    )

    logger.info(f"Running Critic Agent for topic: {topic}")
    async with Agent(config=config) as agent:
        response = await agent.chat(prompt)
        return await response.text()
