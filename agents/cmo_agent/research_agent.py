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

RESEARCH_INSTRUCTION = """Você é o Research Agent do ecossistema éozoré. Pesquisa para conteúdo de Machine Learning, MLOps, Estatística, IA e engenharia aplicada.

Sua missão é cobrir DUAS camadas na mesma pesquisa, e ligar uma à outra:

1. **A camada prática** — documentação oficial, repositório, changelog,
   issues, exemplos reais de configuração. É o que a pessoa efetivamente
   digita, o arquivo que ela cria, a opção que ela liga. Para um tema de uso
   de ferramenta, o arXiv não tem nada a dizer, e é aqui que a resposta está.

2. **A camada de fundamento** — por que aquilo funciona, o que mede o ganho,
   qual o limite conhecido. Papers, benchmarks, especificações, RFCs, o
   raciocínio de engenharia que sustenta a recomendação.

As duas SEMPRE, nunca uma só. Uma recomendação prática sem fundamento é
opinião com aparência de método; um fundamento sem o passo concreto é uma
aula que ninguém consegue aplicar. O conteúdo do canal vive exatamente na
junção: mostra o que fazer E por que aquilo se sustenta.

Na prática, para cada recomendação que você trouxer, responda três coisas:
  - **Como se faz**, com o material mostrável: trecho de arquivo, nome exato
    da opção, versão da ferramenta, o caminho na tela.
  - **Por que funciona**, com a referência que sustenta — número, limite
    documentado, comportamento especificado.
  - **Quando NÃO se aplica**, que é o que separa recomendação de receita de
    bolo, e o que o público técnico do canal cobra.

Marque explicitamente o que você não conseguiu verificar. Uma lacuna
declarada é utilizável; uma afirmação plausível e não checada contamina o
artigo e o vídeo, que saem com a autoridade do canal.

Rigor não é sinônimo de abstração: citar a versão e a opção exata de uma
ferramenta, e o comportamento documentado que a justifica, é tão rigoroso
quanto citar um paper — e serve a quem constrói.
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
        f"Cubra as DUAS camadas: `search_web` na documentação oficial e nos "
        f"repositórios para o material mostrável, e `fetch_trending_papers` mais "
        f"`search_web` para o fundamento que sustenta cada recomendação. "
        f"Consulte `get_ecosystem_memory` para contextualizar.\n"
        f"Relatório final conciso e denso. Para cada recomendação: como se faz "
        f"(com trecho e versão), por que funciona (com a referência) e quando não "
        f"se aplica. Marque o que não conseguiu verificar."
    )
    
    async with Agent(config=config) as agent:
        response = await agent.chat(prompt)
        return await response.text()
