# -*- coding: utf-8 -*-
"""
research_agent.py — Research Specialist Agent using google-antigravity SDK
"""

import os
import sys
import asyncio
import logging

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from google.antigravity import Agent, LocalAgentConfig
from model_config import get_model_config
from tools import fetch_trending_papers, search_web, get_ecosystem_memory, get_article_by_slug

logger = logging.getLogger("cmo_agent.research_agent")

RESEARCH_INSTRUCTION = """Você é o Research Agent do ecossistema éozoré, um pesquisador científico de ponta em Machine Learning, MLOps, Estatística e IA.
Sua missão é realizar pesquisas profundas e coletar dados quantitativos, papers no arXiv ou tendências gerais da web para fundamentar as ideias propostas pelo CEO (Victor Zore).
Evite resumos superficiais ou conceitos básicos de tutorial. Foque em trazer rigor conceitual e referências reais.
"""

async def run_research(topic: str, context: str = "", critic_notes: str = "", system_instruction: str = None) -> str:
    models = get_model_config()
    config = LocalAgentConfig(
        system_instructions=system_instruction or RESEARCH_INSTRUCTION,
        tools=[fetch_trending_papers, search_web, get_ecosystem_memory, get_article_by_slug],
        models=models
    )
    
    prompt = (
        f"Realize uma pesquisa aprofundada para embasar o seguinte tópico de artigo:\n"
        f"TÓPICO: {topic}\n"
        f"CONTEXTO ADICIONAL: {context}\n\n"
        f"ORIENTAÇÃO CRÍTICA DO EDITOR (STEERING):\n{critic_notes}\n\n"
        f"Use `fetch_trending_papers` para buscar papers recentes no arXiv e `search_web` se necessário para ver implementações e tendências de mercado. "
        f"Consulte a memória do ecossistema com `get_ecosystem_memory` para contextualizar. "
        f"Forneça um relatório final conciso, mas denso, com referências, equações conceituais e os principais insights técnicos encontrados."
    )
    
    async with Agent(config=config) as agent:
        response = await agent.chat(prompt)
        return await response.text()
