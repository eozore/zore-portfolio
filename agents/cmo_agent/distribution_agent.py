# -*- coding: utf-8 -*-
"""
distribution_agent.py — Distribution & Repurposing Specialist Agent using google-antigravity SDK
"""

import os
import sys
import asyncio
import logging
from pydantic import BaseModel, Field
from pydantic import ConfigDict
from typing import List, Optional

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from google.antigravity import Agent, LocalAgentConfig
from model_config import get_model_config
from tools import get_ecosystem_memory

logger = logging.getLogger("cmo_agent.distribution_agent")

# ── Pydantic Response Schema Definitions ──────────────────────────────────────

class LinkedInPost(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    hook: str = Field(description="Gancho inicial provocativo e curto focado em divulgar o novo artigo publicado.")
    copy: str = Field(alias="copy", description="Corpo completo do post de divulgação com link do artigo e hashtags.")
    status: str = Field(default="em_revisao")


class YouTubeShortsScript(BaseModel):
    id: str
    title: str = Field(description="Título curto e instigante para Shorts do YouTube.")
    hook3s: str = Field(description="Falas impactantes e rápidas dos primeiros 3 segundos para reter atenção.")
    script: str = Field(description="Roteiro falado completo para 30 a 60 segundos.")
    status: str = Field(default="em_revisao")

class ReelScript(BaseModel):
    id: str
    title: str = Field(description="Título do Reels do Instagram.")
    hook3s: str = Field(description="Os primeiros 3 segundos falados, extremamente chamativos.")
    visualCue: str = Field(description="O que deve ser mostrado na tela nesse trecho (cenas, gravação, gestos).")
    script: str = Field(description="Roteiro falado completo para 30 a 60 segundos de Reels.")
    status: str = Field(default="em_revisao")

class CarouselSlide(BaseModel):
    slideNumber: int
    heading: str
    body: str

class CarouselPost(BaseModel):
    id: str
    title: str
    caption: str = Field(description="Legenda para acompanhar o post de carrossel no feed do Instagram.")
    slides: List[CarouselSlide] = Field(description="Os slides do carrossel em ordem sequencial.")
    status: str = Field(default="em_revisao")

class ImagePost(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    title: str = Field(description="Assunto ou título interno do post de imagem do feed.")
    imageDescription: str = Field(description="Descrição extremamente detalhada do design da imagem de acompanhamento (ex: cores sugeridas, gráficos, equações ilustradas, layout de design e elementos visuais).")
    copy: str = Field(alias="copy", description="Legenda ou texto completo do post que acompanha a imagem no feed.")
    status: str = Field(default="em_revisao")

class StoryIdea(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    day: str = Field(description="Dia da semana e período, ex: Segunda Manhã, Quarta Tarde")
    angle: str = Field(description="Ângulo do story (ex: Bastidores, Desafio, Pergunta)")
    copy: str = Field(alias="copy", description="Texto sugerido para o story ou instrução de fala.")
    interactiveElement: Optional[str] = Field(None, description="Enquete com opções ou caixa de perguntas.")
    status: str = Field(default="em_revisao")

class RepurposeResponse(BaseModel):
    linkedinPosts: List[LinkedInPost] = Field(description="Exatamente 2 posts de LinkedIn focados em divulgar o artigo do blog e puxar tráfego para o vídeo do YouTube.")
    youtubeShorts: List[YouTubeShortsScript] = Field(description="2 a 3 roteiros rápidos para YouTube Shorts chamando para o vídeo longo do canal.")
    reelsScripts: List[ReelScript] = Field(description="3 a 4 roteiros curtos de Reels com hooks fortes direcionando para o canal.")
    carousels: List[CarouselPost] = Field(description="Exatamente 1 a 2 carrosseis slide-a-slide formatados para Instagram.")
    imagePosts: List[ImagePost] = Field(description="Exatamente 1 a 2 posts de Texto + Imagem para feeds sociais.")
    storiesIdeas: List[StoryIdea] = Field(description="Exatamente 5 a 6 ideias de stories (uma por dia da semana).")

# ── Distribution Agent Runner ──────────────────────────────────────────────────

DISTRIBUTION_INSTRUCTION = """Você é o Distribution Agent do ecossistema éozoré. Sua missão é ler o artigo técnico do blog e o roteiro do YouTube (passados como base) e orquestrar a derivação omnicanal completa de toda a campanha de marketing das redes sociais.
Sua persona e tom devem refletir Victor Zore: técnico, rigoroso, focado em explicar o PORQUÊ (a matemática e a lógica) e avesso a clichês ou jargões vazios de coaching de negócios.

DIRETRIZES CRÍTICAS DE CONTEÚDO E ENGAJAMENTO (Multi-Step Marketing):
1. GERAR VALOR REAL: Cada postagem deve entregar conhecimento prático e real para o leitor.
2. PLACEHOLDERS DE LINKS: NUNCA repita a URL completa do canal do YouTube ou do blog em cada item (isso dispara filtros de repetição/loop). Use SEMPRE os placeholders genéricos `[LINK_CANAL]` ou `[LINK_ARTIGO]` nas chamadas.
3. CONCISÃO E PREVENÇÃO DE TIMEOUT: Todos os copys, descrições e slides de carrossel devem ser sintéticos e focados, com no máximo 800 caracteres por postagem, mantendo o payload otimizado.

Gere as peças de conteúdo estritamente respeitando as quantidades e o formato do response_schema:
1. linkedinPosts: Exatamente 2 posts focados em divulgar e linkar para o novo artigo publicado no blog.
2. youtubeShorts: Exatamente 2 roteiros rápidos verticais para Shorts de YouTube.
3. reelsScripts: Exatamente 2 roteiros verticais para Reels do Instagram.
4. carousels: Exatamente 1 ou 2 posts de carrossel com cabeçalho e corpo detalhado slide-a-slide.
5. imagePosts: Exatamente 1 ou 2 posts contendo legendas e descrições detalhadas do design gráfico sugerido.
6. storiesIdeas: Exatamente 5 ou 6 ideias de stories (enquetes, bastidores, quizzes matemáticos) para manter o engajamento diário durante a semana.

Todas as peças geradas devem possuir a propriedade inicial "status": "em_revisao".
"""

async def run_distribution(title: str, slug: str, content: str, category: str, language: str = "pt-BR", system_instruction: str = None, youtube_script: str = None) -> dict:
    models = get_model_config()
    
    config = LocalAgentConfig(
        system_instructions=system_instruction or DISTRIBUTION_INSTRUCTION,
        response_schema=RepurposeResponse,
        models=models
    )
    
    # 1. Fetch memory historical state
    memory_context = get_ecosystem_memory()
    
    # Truncate content to prevent model looping on very long articles
    content_preview = content[:6000] + ("\n\n[...artigo truncado para processamento...]" if len(content) > 6000 else "")
    
    prompt = (
        f"HISTORICO DO ECOSSISTEMA EOZORE:\n{memory_context}\n\n"
        f"ARTIGO DE ORIGEM PARA A CAMPANHA:\n"
        f"TITULO: {title}\n"
        f"SLUG: {slug}\n"
        f"CATEGORIA: {category}\n"
        f"IDIOMA: {language}\n\n"
        f"CONTEUDO DO ARTIGO (resumo para derivacao):\n{content_preview}\n\n"
    )
    if youtube_script:
        yt_preview = youtube_script[:3000] + ("\n\n[...roteiro truncado...]" if len(youtube_script) > 3000 else "")
        prompt += f"ROTEIRO DE VIDEO DO YOUTUBE APROVADO (CTA focado neste video):\n{yt_preview}\n\n"
    prompt += (
        "INSTRUCAO FINAL: Gere EXATAMENTE o plano editorial conforme o response_schema. "
        "Nao repita o artigo. Seja conciso em cada copy (max 600 chars por postagem). "
        "Use apenas os placeholders [LINK_CANAL] e [LINK_ARTIGO]. Nao escreva links reais repetidamente. "
        "Foque apenas nas pecas de midia social solicitadas."
    )
    
    async with Agent(config=config) as agent:
        response = await agent.chat(prompt)
        structured_data = await response.structured_output()
        return structured_data

