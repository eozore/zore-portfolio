# -*- coding: utf-8 -*-
"""
distribution_agent.py — Distribution & Repurposing Specialist Agent
Gera campanha omnicanal completa a partir de um artigo de blog + roteiro YouTube.

Plataformas cobertas:
  LinkedIn     — 2 posts texto + imagem HTML gerada, espelhados no YouTube Community
  YouTube      — 2-3 Shorts verticais
  Instagram    — 3-4 Reels + 2-3 Carrosseis + 2-3 Posts de imagem + 5-7 Stories
  Threads      — 2-3 threads sequenciais (série de posts encadeados)
  YouTube Community — espelho dos posts LinkedIn (mesmo copy, adaptado)
"""

import os
import sys
import json
import logging
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from google.antigravity import Agent, LocalAgentConfig
from model_config import get_model_config
from tools import get_ecosystem_memory

logger = logging.getLogger("cmo_agent.distribution_agent")

# ── Pydantic Response Schema ───────────────────────────────────────────────────

class LinkedInPost(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    hook: str = Field(
        description="Primeira linha do post — frase curta e direta que para o scroll. "
                    "Tom informal, como se estivesse contando algo a um colega. "
                    "Exemplos de padrão: 'Passei horas debugando isso. Valeu a pena entender o porquê.' "
                    "ou 'Todo mundo usa LoRA. Quase ninguém sabe o que ela realmente minimiza.'"
    )
    post_copy: str = Field(
        alias="copy",
        description="Corpo do post: 3-5 parágrafos curtos. Tom conversacional e técnico ao mesmo tempo. "
                    "Ensina 1 conceito concreto (equação em texto, trade-off ou insight de engenharia). "
                    "Termina com pergunta de engajamento ou CTA para [LINK_ARTIGO]. "
                    "Máximo 1200 caracteres. Inclui 3-5 hashtags técnicas no final."
    )
    imageHtml: str = Field(
        description="HTML completo para gerar a imagem de capa do post via Playwright. "
                    "Design dark premium na paleta da marca: fundo #0d0f14, tipografia #eae4dc, "
                    "destaque #e8873a (laranja) e apoio #f5b56a. NUNCA use roxo, azul ou ciano. "
                    "Deve conter: título do conceito em destaque, 1 equação central formatada visualmente, "
                    "logo 'éozoré' no canto. Tamanho alvo: 1200x628px (og:image LinkedIn). "
                    "Use apenas HTML/CSS inline, sem JavaScript, sem fontes externas."
    )
    status: str = Field(default="em_revisao")


class YouTubeCommunityPost(BaseModel):
    """Espelho do LinkedIn no YouTube Community — mesmo conteúdo educativo, adaptado para o canal."""
    model_config = ConfigDict(populate_by_name=True)
    id: str
    post_copy: str = Field(
        alias="copy",
        description="Versão do post LinkedIn adaptada para o YouTube Community. "
                    "Remove hashtags e links externos. Substitui '[LINK_ARTIGO]' por referência ao link na bio. "
                    "Tom ligeiramente mais casual — os inscritos do canal já te conhecem. "
                    "Termina com pergunta para os inscritos comentarem. Máximo 800 caracteres."
    )
    linkedinRefId: str = Field(description="id do LinkedInPost correspondente que originou este post.")
    status: str = Field(default="em_revisao")


class YouTubeShortsScript(BaseModel):
    id: str
    title: str = Field(description="Título do Short — direto, técnico, sem clickbait. Máximo 60 chars.")
    hook3s: str = Field(
        description="Fala dos primeiros 3 segundos — a única coisa que decide se o usuário para de scrollar. "
                    "Deve revelar imediatamente o insight técnico central, não 'teaser'. "
                    "Exemplo: 'O gradient descent não converge por causa do learning rate. "
                    "Converge por causa da curvatura da loss surface.'"
    )
    script: str = Field(
        description="Roteiro falado completo para 45-60 segundos. Tom: como explicar algo rápido a um colega sênior. "
                    "Ensina 1 conceito com profundidade suficiente para gerar 'ah-ha moment'. "
                    "ZERO LaTeX bruto — escreva equações por extenso em português fonético. "
                    "CTA final: 'vídeo completo no canal, link na bio'."
    )
    status: str = Field(default="em_revisao")


class ReelScript(BaseModel):
    id: str
    title: str = Field(description="Título interno do Reel.")
    hook3s: str = Field(
        description="Primeiros 3 segundos falados — pergunta ou afirmação que provoca. "
                    "Tom mais casual que o YouTube: o Instagram tem um público levemente mais amplo."
    )
    visualCue: str = Field(
        description="Direção de câmera/tela: o que aparece enquanto a fala acontece. "
                    "Exemplos: 'Victor falando para câmera com equação escrita no quadro atrás', "
                    "'Tela de código com highlight da função de perda', "
                    "'Gráfico de curva de aprendizado animado'."
    )
    script: str = Field(
        description="Roteiro falado completo para 30-60 segundos. "
                    "ZERO LaTeX bruto. Tom natural e direto. "
                    "Termina com: 'artigo completo no link da bio'."
    )
    status: str = Field(default="em_revisao")


class CarouselSlide(BaseModel):
    slideNumber: int
    heading: str = Field(description="Título do slide — curto, impactante. Máximo 60 chars.")
    body: str = Field(
        description="Corpo do slide — 2-4 linhas. Um conceito por slide. "
                    "Progressão lógica: slide 1 = problema, slides 2-N = teoria passo a passo, "
                    "último slide = conclusão + CTA."
    )


class CarouselPost(BaseModel):
    id: str
    title: str
    caption: str = Field(
        description="Legenda do carrossel no feed. Tom casual + técnico. "
                    "Primeira linha é o hook de scroll-stop. "
                    "Termina com 'deslize →' e hashtags. Máximo 800 chars."
    )
    slides: List[CarouselSlide]
    status: str = Field(default="em_revisao")


class ImagePost(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    title: str
    imageDescription: str = Field(
        description="Descrição detalhada do visual: cores, elementos gráficos, equações a mostrar, layout. "
                    "Usado para gerar a imagem via HTML+Playwright."
    )
    imageHtml: str = Field(
        description="HTML completo da imagem 1080x1080px (formato quadrado para feed Instagram). "
                    "Design dark premium na paleta da marca: fundo #0d0f14, tipografia #eae4dc, "
                    "destaque #e8873a (laranja) e apoio #f5b56a. NUNCA use roxo, azul ou ciano. "
                    "Conteúdo: insight técnico central do artigo em 1-2 linhas, visual minimalista. "
                    "Use apenas HTML/CSS inline."
    )
    post_copy: str = Field(
        alias="copy",
        description="Legenda do post. Tom direto e técnico. "
                    "Primeira linha = hook. Corpo = insight + contexto. "
                    "CTA: 'link na bio'. Máximo 800 chars + hashtags."
    )
    status: str = Field(default="em_revisao")


class StoryIdea(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    day: str = Field(description="Dia da semana + período. Ex: 'Segunda Manhã', 'Quarta Tarde'.")
    angle: str = Field(
        description="Ângulo narrativo do story. Categorias: "
                    "'Quiz Técnico' (pergunta de engajamento), "
                    "'Bastidor' (como o artigo foi escrito/pesquisado), "
                    "'Enquete' (duas abordagens técnicas, qual você prefere?), "
                    "'Dica Rápida' (1 fórmula ou trade-off em 1 slide), "
                    "'CTA para o vídeo'."
    )
    post_copy: str = Field(
        alias="copy",
        description="Texto do story ou instrução de fala. Tom natural, quase pessoal. "
                    "Como se Victor estivesse falando direto com cada seguidor."
    )
    interactiveElement: Optional[str] = Field(
        None,
        description="Se for Enquete: 'Opção A: X | Opção B: Y'. "
                    "Se for Quiz: 'Pergunta: X? Resposta no próximo story'. "
                    "Se não aplicável: null."
    )
    status: str = Field(default="em_revisao")


class ThreadPost(BaseModel):
    """Thread sequencial — série de posts encadeados no Threads (Meta)."""
    id: str
    threadNumber: int = Field(description="Número da thread na sequência (1, 2, 3...).")
    posts: List[str] = Field(
        description="Lista de posts em sequência (cada item = 1 post do Threads). "
                    "Post 1: hook que revela o insight central — informal, direto. "
                    "Posts 2-4: desenvolvimento do conceito com profundidade técnica progressiva. "
                    "Cada equação escrita por extenso em português. "
                    "Último post: conclusão + 'artigo completo: [LINK_ARTIGO]'. "
                    "Cada post: máximo 500 caracteres. Série inteira: 4-6 posts."
    )
    topic: str = Field(description="Tema central desta thread — 1 frase.")
    status: str = Field(default="em_revisao")


class RepurposeResponse(BaseModel):
    linkedinPosts: List[LinkedInPost] = Field(
        description="Exatamente 2 posts LinkedIn. "
                    "Post 1: foca no insight matemático central do artigo. "
                    "Post 2: foca no ângulo de engenharia/produção (trade-offs, custos, decisões de arquitetura)."
    )
    youtubeCommunityPosts: List[YouTubeCommunityPost] = Field(
        description="Exatamente 2 posts para YouTube Community — um por cada LinkedIn post gerado."
    )
    youtubeShorts: List[YouTubeShortsScript] = Field(
        description="2 a 3 Shorts. Cada um cobre um ângulo diferente do artigo."
    )
    reelsScripts: List[ReelScript] = Field(
        description="2 a 3 Reels. Angulos diferentes dos Shorts — mais casuais."
    )
    carousels: List[CarouselPost] = Field(
        description="1 a 2 carrosseis. Preferência para o carousel que mais beneficia de visualização passo-a-passo."
    )
    imagePosts: List[ImagePost] = Field(
        description="1 a 2 posts de imagem para feed Instagram."
    )
    storiesIdeas: List[StoryIdea] = Field(
        description="5 a 7 stories distribuídos ao longo da semana, cobrindo todos os ângulos narrativos."
    )
    threads: List[ThreadPost] = Field(
        description="2 a 3 threads para o Threads (Meta). "
                    "Thread 1: ângulo matemático/teórico. "
                    "Thread 2: ângulo de engenharia. "
                    "Thread 3 (opcional): bastidor ou curiosidade do processo."
    )


# ── Distribution Instruction ──────────────────────────────────────────────────

DISTRIBUTION_INSTRUCTION = """Você é o Distribution Agent da plataforma éozoré.

CAPITALIZAÇÃO (regra inegociável): todos os títulos, hooks e headings de qualquer peça SEMPRE em sentence case — só a primeira letra da frase em maiúscula, mais nomes próprios e siglas (RAG, LLM, GCP). NUNCA Title Case (Cada Palavra Maiúscula é proibido). Sem emojis ou ícones em títulos, hooks e headings de carrossel.

Sua missão: a partir de um artigo técnico e do roteiro YouTube, criar uma campanha omnicanal completa que sirva a dois objetivos simultâneos e indissociáveis:

  OBJETIVO 1 — EDUCAR: cada peça entrega conhecimento real e aplicável. Não é resumo vago. É insight concreto.
  OBJETIVO 2 — CRESCER: cada peça foi desenhada para converter leitor em seguidor, seguidor em inscrito, inscrito em leitor recorrente.

━━━ A PERSONA ━━━
Victor Zoré escreve como quem está explicando algo a um colega sênior durante um café.
Não é formal. Não é coach. Não usa jargão de marketing.
Quando fala de matemática, fala com precisão. Quando fala de engenharia, fala com experiência real.
O leitor sente que está aprendendo com alguém que já quebrou a cabeça com aquilo, não com alguém que leu sobre.

━━━ TOM POR PLATAFORMA ━━━

LinkedIn: Técnico-pessoal. A pessoa que para de scrollar é o engenheiro sênior que reconhece o insight.
  Padrão de abertura: frase direta que revela o problema ou contradição central.
  Nunca começa com "Hoje vou falar sobre..." ou "Olá pessoal!".
  Exemplo bom: "Gradient descent não converge porque o learning rate está errado. Converge porque a curvatura da loss surface muda."
  Exemplo ruim: "Esse artigo sobre gradient descent é incrível! Confira abaixo!"

YouTube Community: Mesmo conteúdo do LinkedIn, mas mais próximo dos inscritos do canal.
  Sem hashtags. Sem links externos. Termina com pergunta para comentário.

YouTube Shorts: Como se o Victor tivesse 60 segundos para fazer a cabeça de um engenheiro mudar sobre algo.
  O hook dos primeiros 3 segundos decide tudo. Sem introdução. Vai direto ao insight.

Instagram Reels: Um pouco mais casual que os Shorts. O público é levemente mais amplo.
  Pode usar analogias mais visuais. Mantém rigor técnico mas com mais personalidade.

Instagram Carrossel: A ferramenta de ensino mais poderosa da plataforma.
  Cada slide = 1 passo lógico. Progressão: problema → teoria → código → resultado.
  Slide 1 é o hook. Último slide é o CTA com resumo dos pontos aprendidos.

Instagram Feed (imagem): Estética dark premium. 1 insight visual por post.
  A imagem vale mais que o texto aqui — design precisa comunicar o conceito por si só.

Instagram Stories: O único lugar onde Victor pode ser 100% pessoal.
  Mix de quiz técnico, bastidores de pesquisa, enquetes sobre escolhas de arquitetura.
  Mantém o canal quente entre publicações grandes.

Threads: A plataforma de texto longa que o LinkedIn não é.
  Série de posts encadeados contando a história do conceito com profundidade.
  Post 1 = gancho. Posts 2-4 = desenvolvimento técnico progressivo. Último = conclusão + link.
  Tom entre LinkedIn e conversa — mais solto, mais direto.

━━━ ESTRATÉGIA DE CRESCIMENTO EMBUTIDA ━━━

Cada peça foi pensada para o funil:
  Topo (descoberta): Shorts, Reels, Stories — alcançam quem não te conhece ainda.
  Meio (consideração): LinkedIn, Threads, Carrossel — entregam profundidade suficiente para seguir.
  Fundo (conversão): LinkedIn com link, YouTube Community, Stories CTA — convertem seguidor em leitor/inscrito.

CTAs obrigatórios por formato:
  Posts de feed (LinkedIn, Instagram): "[LINK_ARTIGO]" ou "link na bio"
  Vídeos curtos (Shorts, Reels): "vídeo completo no canal, link na bio"
  Threads: último post sempre fecha com "[LINK_ARTIGO]"
  YouTube Community: termina com pergunta para comentário (sem link externo)
  Stories CTA: "link na bio → artigo completo"

━━━ REGRAS TÉCNICAS ━━━
- ZERO LaTeX bruto em qualquer copy falado ou escrito para redes sociais. Equações por extenso em português.
- NUNCA repita URLs reais — use os placeholders [LINK_ARTIGO] e [LINK_CANAL].
- Máximo 1200 chars por post LinkedIn/Threads, 800 chars para Instagram, 500 chars por post de Threads individual.
- Todos os itens gerados com "status": "em_revisao".
- imageHtml: HTML/CSS inline apenas, sem JavaScript, sem fontes externas, tamanhos fixos (LinkedIn 1200x628, Instagram 1080x1080).

━━━ PALETA DA MARCA (obrigatória em TODO imageHtml) ━━━
Use EXCLUSIVAMENTE estas cores. Elas são as mesmas do slide_designer_agent e do
thumbnail_agent — sem isso a thumbnail do YouTube sai laranja e o post do
Instagram sai azul, quebrando a identidade visual entre as peças da campanha.

  fundo          #0d0f14   (quase preto)
  fundo alt      #151920   (blocos e cartões)
  texto          #eae4dc   (bege claro)
  texto suave    #8a8378   (legendas, rodapé)
  destaque       #e8873a   (laranja — títulos, números, bordas de ênfase)
  destaque suave #f5b56a   (laranja claro — realces secundários)
  positivo       #5fce8a   (só para indicar ganho ou acerto)
  negativo       #c65d3b   (só para indicar perda ou erro)

PROIBIDO: azul, roxo, ciano, verde-azulado. Especificamente, NUNCA use as cores
do tema escuro do GitHub (#0d1117, #58a6ff, #c9d1d9, #30363d, #8b949e) — é o
default que os modelos escolhem sozinhos e está fora da marca.
"""


async def run_distribution(
    title: str,
    slug: str,
    content: str,
    category: str,
    language: str = "pt-BR",
    system_instruction: str = None,
    youtube_script: str = None,
) -> dict:
    """
    Gera campanha omnicanal via Vertex AI REST direto (sem antigravity SDK).
    Retorna dict compatível com RepurposeResponse para o frontend.
    """
    from vertex_generate import generate_text

    memory_context = get_ecosystem_memory()
    content_preview = content[:5000] + (
        "\n\n[artigo truncado]" if len(content) > 5000 else ""
    )

    yt_section = ""
    if youtube_script:
        yt_preview = youtube_script[:2000] + ("\n[roteiro truncado]" if len(youtube_script) > 2000 else "")
        yt_section = f"\nROTEIRO YOUTUBE:\n{yt_preview}\n"

    prompt = f"""HISTÓRICO DO ECOSSISTEMA:
{memory_context}

ARTIGO: {title} | slug: {slug} | categoria: {category} | idioma: {language}

CONTEÚDO:
{content_preview}
{yt_section}
Gere o plano editorial completo como JSON válido com esta estrutura exata:
{{
  "linkedinPosts": [
    {{"id":"li-01","hook":"...","copy":"...","imageHtml":"<!DOCTYPE html>...","status":"em_revisao"}},
    {{"id":"li-02","hook":"...","copy":"...","imageHtml":"<!DOCTYPE html>...","status":"em_revisao"}}
  ],
  "youtubeCommunityPosts": [
    {{"id":"ytc-01","copy":"...","linkedinRefId":"li-01","status":"em_revisao"}},
    {{"id":"ytc-02","copy":"...","linkedinRefId":"li-02","status":"em_revisao"}}
  ],
  "youtubeShorts": [
    {{"id":"yts-01","title":"...","hook3s":"...","script":"...","status":"em_revisao"}},
    {{"id":"yts-02","title":"...","hook3s":"...","script":"...","status":"em_revisao"}}
  ],
  "reelsScripts": [
    {{"id":"re-01","title":"...","hook3s":"...","visualCue":"...","script":"...","status":"em_revisao"}},
    {{"id":"re-02","title":"...","hook3s":"...","visualCue":"...","script":"...","status":"em_revisao"}},
    {{"id":"re-03","title":"...","hook3s":"...","visualCue":"...","script":"...","status":"em_revisao"}}
  ],
  "carousels": [
    {{"id":"car-01","title":"...","caption":"...","slides":[{{"slideNumber":1,"heading":"...","body":"..."}}],"status":"em_revisao"}}
  ],
  "imagePosts": [
    {{"id":"img-01","title":"...","imageDescription":"...","imageHtml":"<!DOCTYPE html>...","copy":"...","status":"em_revisao"}}
  ],
  "storiesIdeas": [
    {{"id":"st-01","day":"Segunda Manhã","angle":"Quiz Técnico","copy":"...","interactiveElement":null,"status":"em_revisao"}},
    {{"id":"st-02","day":"Terça Tarde","angle":"Dica Rápida","copy":"...","interactiveElement":null,"status":"em_revisao"}},
    {{"id":"st-03","day":"Quarta Manhã","angle":"Enquete","copy":"...","interactiveElement":"Opção A: X | Opção B: Y","status":"em_revisao"}},
    {{"id":"st-04","day":"Quinta Tarde","angle":"Bastidor","copy":"...","interactiveElement":null,"status":"em_revisao"}},
    {{"id":"st-05","day":"Sexta Manhã","angle":"CTA para o vídeo","copy":"...","interactiveElement":null,"status":"em_revisao"}}
  ],
  "threads": [
    {{"id":"th-01","threadNumber":1,"topic":"...","posts":["post1","post2","post3","post4 + [LINK_ARTIGO]"],"status":"em_revisao"}},
    {{"id":"th-02","threadNumber":2,"topic":"...","posts":["post1","post2","post3","post4 + [LINK_ARTIGO]"],"status":"em_revisao"}}
  ]
}}

REGRAS:
- Retorne SOMENTE o JSON, sem markdown, sem texto antes ou depois
- imageHtml: HTML 1200x628px (LinkedIn) ou 1080x1080px (Instagram) — HTML/CSS inline, sem JS
- Todos os scripts de fala (Shorts/Reels): ZERO LaTeX, equações por extenso em português
- Use [LINK_ARTIGO] e [LINK_CANAL] como placeholders, nunca URLs reais
- hook LinkedIn: frase técnica direta que para o scroll, sem saudação
- Máximo 1200 chars por post LinkedIn
"""

    try:
        raw = await generate_text(
            prompt=prompt,
            system_instruction=system_instruction or DISTRIBUTION_INSTRUCTION,
            temperature=0.6,
        )
        logger.info(f"[distribution] Raw response: {len(raw)} chars")

        # Extrai JSON do output
        import re
        # Remove markdown wrapper se presente
        raw = re.sub(r"<think>[\s\S]*?</think>", "", raw).strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"\s*```\s*$", "", raw, flags=re.MULTILINE)
        raw = raw.strip()

        # Tenta parse direto
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Tenta reparar trailing commas
            repaired = re.sub(r",\s*([}\]])", r"\1", raw)
            data = json.loads(repaired)

        # Garante campos obrigatórios com fallback
        data.setdefault("linkedinPosts", [])
        data.setdefault("youtubeCommunityPosts", [])
        data.setdefault("youtubeShorts", [])
        data.setdefault("reelsScripts", [])
        data.setdefault("carousels", [])
        data.setdefault("imagePosts", [])
        data.setdefault("storiesIdeas", [])
        data.setdefault("threads", [])

        logger.info(
            f"[distribution] OK — "
            f"{len(data['linkedinPosts'])} LinkedIn, "
            f"{len(data['reelsScripts'])} Reels, "
            f"{len(data['youtubeShorts'])} Shorts, "
            f"{len(data['storiesIdeas'])} Stories"
        )
        return data

    except Exception as exc:
        logger.exception(f"[distribution] Failed: {exc}")
        # Fallback mínimo para não quebrar o pipeline
        return {
            "linkedinPosts": [],
            "youtubeCommunityPosts": [],
            "youtubeShorts": [],
            "reelsScripts": [],
            "carousels": [],
            "imagePosts": [],
            "storiesIdeas": [],
            "threads": [],
        }
