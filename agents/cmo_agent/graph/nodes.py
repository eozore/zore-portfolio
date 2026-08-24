# -*- coding: utf-8 -*-
"""
nodes.py — Os agentes do time de marketing, como nós do grafo.

Cada nó ENVOLVE um agente especialista que já existe (research, writing,
scriptwriter, slide_designer, distribution). O grafo não reescreve nenhum
deles: ele dá ordem, estado tipado, tratamento de falha e rastro.

Regra de falha, uniforme em todos os nós: uma exceção vira um `Erro` no
estado, não uma explosão. `fatal=True` interrompe o funil; `fatal=False`
deixa seguir sem aquela peça. Antes, tudo virava uma string numa lista de
`partial_errors` que ninguém conseguia inspecionar nem agir sobre.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Literal

from observability import set_attributes, span
from graph.knowledge import montar_contexto, registrar_decisao
from skills.registry import montar_instrucao
from graph.state import EstadoMarketing

logger = logging.getLogger("cmo_agent.graph.nodes")


def _erro(no: str, exc: Exception, fatal: bool) -> dict:
    logger.exception("[grafo/%s] %s", no, exc)
    return {
        "erros": [{"no": no, "mensagem": str(exc)[:500], "fatal": fatal}],
        "trilha": [f"{no}: ERRO ({str(exc)[:80]})"],
    }


def _db():
    from tools import db
    return db


# ── 1. Planejamento ───────────────────────────────────────────────────────────

async def no_planejamento(estado: EstadoMarketing) -> dict:
    """
    Fecha a pauta a partir do tema, com a memória de marca e o histórico do
    que já foi publicado no contexto.
    """
    with span("no.planejamento", tenant=estado.get("tenant_id"), tema=estado.get("tema")):
        try:
            from pydantic import BaseModel, Field
            from structured import generate_structured

            class Pauta(BaseModel):
                titulo:    str = Field(max_length=120)
                subtitulo: str = Field(max_length=200)
                tese:      str = Field(min_length=40, max_length=500)
                publico:   str
                objetivo_aprendizado: str
                hardskills: list[str] = Field(min_length=2, max_length=6)
                duracao_alvo: str = Field(description="ex: '8 min'")
                serie:     str = Field(description="slug da série no blog")
                # O blog só aceita estas três categorias (types/article.ts).
                # Quem decide é o CMO, aqui: sem o campo, a publicação do
                # artigo no gate não passa na validação e o fluxo trava numa
                # etapa que não tem nada a ver com o conteúdo.
                categoria: Literal["estatistica", "ml", "ia"] = Field(
                    description=(
                        "Bloco do blog: 'estatistica' para fundamentos matemáticos, "
                        "'ml' para modelos e treinamento, 'ia' para sistemas e agentes."
                    ),
                )
                angulo_video: str = Field(
                    min_length=30, max_length=300,
                    description="O que SÓ o vídeo entrega. É a promessa do funil social.",
                )

            contexto_kb = montar_contexto(_db(), estado.get("tenant_id"))
            pauta = await generate_structured(
                Pauta,
                prompt=(
                    f"Tema: {estado['tema']}\n"
                    f"Contexto do usuário: {estado.get('contexto', '(nenhum)')}\n\n"
                    f"Feche a pauta. O 'angulo_video' é o que só o vídeo entrega — "
                    f"todo o conteúdo social vai apontar para ele."
                ),
                system_instruction=(
                    f"Você é o CMO do canal éozoré, fechando a pauta da semana.\n\n"
                    f"{contexto_kb}"
                ),
            )
            set_attributes(pauta_titulo=pauta.titulo)
            return {
                "pauta": pauta.model_dump(),
                "fase": "artigo",
                "trilha": [f"planejamento: pauta '{pauta.titulo}'"],
            }
        except Exception as exc:
            return {**_erro("planejamento", exc, fatal=True), "fase": "erro"}


# ── 2. Artigo ─────────────────────────────────────────────────────────────────

async def no_artigo(estado: EstadoMarketing) -> dict:
    """Escreve o artigo técnico. Reusa research_agent + writing_agent."""
    with span("no.artigo", tenant=estado.get("tenant_id")):
        inicio = time.time()
        try:
            from research_agent import run_research
            from writing_agent import stream_writing

            pauta = estado.get("pauta") or {}
            titulo = pauta.get("titulo", estado["tema"])

            pesquisa = ""
            try:
                pesquisa = await run_research(titulo)
            except Exception as exc:
                # Pesquisa é enriquecimento, não pré-requisito: sem ela o
                # artigo sai baseado só no conhecimento do modelo.
                logger.warning("[grafo/artigo] research falhou, seguindo: %s", exc)

            # A assinatura real é (topic, context, research_notes,
            # system_instruction) — sem categoria nem idioma. Ambos vêm do
            # `context`, que é o campo livre que o prompt do redator consome.
            contexto = (
                f"Série: {pauta.get('serie', 'ia')}\n"
                f"Tese: {pauta.get('tese', '')}\n"
                f"Público: {pauta.get('publico', '')}\n"
                f"Objetivo: {pauta.get('objetivo_aprendizado', '')}\n"
                f"Idioma: {estado.get('idioma', 'pt-BR')}"
            )
            instrucao = montar_instrucao(_db(), estado.get("tenant_id"), "redator")

            # `stream_writing` devolve (gerador, agente) — não é ele próprio
            # o iterável. E o agente PRECISA ser fechado no finally: sem isso
            # a conexão do SDK vaza a cada artigo, e num Cloud Run que atende
            # vários ciclos isso vira esgotamento de socket.
            partes: list[str] = []
            gerador, agente = await stream_writing(
                titulo, contexto[:3000], pesquisa[:3000], instrucao,
            )
            try:
                async for chunk in gerador:
                    partes.append(chunk)
            except Exception as stream_exc:
                # Texto parcial vale mais que nada: o humano revisa no gate e
                # decide se pede para refazer.
                logger.warning("[grafo/artigo] stream interrompido: %s", stream_exc)
            finally:
                if agente is not None:
                    await agente.__aexit__(None, None, None)

            bruto = "".join(partes).strip()

            # Separa metadado de corpo. O redator emite frontmatter YAML no
            # topo e às vezes um bloco META no fim — guardar tudo num campo só
            # fazia a tela de revisão renderizar "série: ... título: ... slug:"
            # como um parágrafo, com os nomes dos campos embolados na prosa.
            from graph.artigo_parser import separar
            texto, meta = separar(bruto)

            if len(texto) < 500:
                raise RuntimeError(f"artigo curto demais ({len(texto)} chars)")

            set_attributes(artigo_chars=len(texto), latencia_s=round(time.time() - inicio, 1))
            return {
                "artigo_markdown": texto,
                # O título do frontmatter é o que o redator escolheu depois de
                # ver o artigo pronto; o da pauta foi decidido antes de existir
                # uma linha de texto.
                "artigo_titulo": meta.get("titulo") or meta.get("title") or titulo,
                "artigo_slug":   meta.get("slug", ""),
                "artigo_resumo": meta.get("descricao") or meta.get("description", ""),
                "fase": "aguardando_aprovacao_artigo",
                "trilha": [f"artigo: {len(texto)} chars em {time.time() - inicio:.0f}s"],
            }
        except Exception as exc:
            return {**_erro("artigo", exc, fatal=True), "fase": "erro"}


# ── 3. Gate do artigo ─────────────────────────────────────────────────────────

async def no_gate_artigo(estado: EstadoMarketing) -> dict:
    """
    Ponto de interrupção. O grafo PARA aqui até o humano decidir.

    Não há espera ativa: o LangGraph persiste o checkpoint e a execução
    termina. Quando a aprovação chega pela API, o grafo é retomado do mesmo
    ponto — horas ou dias depois, em outra instância de Cloud Run.
    """
    aprov = estado.get("aprovacao_artigo") or {}
    decisao = aprov.get("decisao")

    if decisao:
        registrar_decisao(
            _db(), estado.get("tenant_id"),
            gate="artigo", decisao=decisao,
            comentario=aprov.get("comentario", ""),
            tema=estado.get("tema", ""),
        )
    return {"trilha": [f"gate_artigo: {decisao or 'aguardando'}"]}


def rota_gate_artigo(estado: EstadoMarketing) -> str:
    decisao = (estado.get("aprovacao_artigo") or {}).get("decisao")
    if decisao == "aprovado":
        return "video"
    if decisao == "ajustar":
        return "artigo"
    return "fim"


# ── 4. Vídeo: roteiro + slides ────────────────────────────────────────────────

VIDEO_MAX_TENTATIVAS = 3  # 1 original + 2 retries corretivos antes de falhar fatal


def _nota_corretiva(violacoes: list[str], stats: dict) -> str:
    """
    Traduz uma rejeição de validate_manifest numa instrução acionável para o
    scriptwriter — o mesmo padrão de steering usado em research_agent
    (critic_notes): não basta dizer "errou", tem que dizer o número medido e
    o que fazer com ele.
    """
    share_pct = stats.get("avatar_share", 0.0) * 100
    linhas = [f"- {v}" for v in violacoes]
    if stats.get("avatar_share", 0.0) > 0.40:
        linhas.append(
            f"Sua última tentativa saiu com {share_pct:.0f}% de avatar; o teto "
            f"é 40% e o alvo é 20%. Reduza o número e/ou a duração dos "
            f"segmentos kind=\"avatar\" (12-25s cada) e/ou aumente a duração "
            f"dos segmentos kind=\"slide\" (25-45s cada, 60-105 palavras) até "
            f"o avatar cair para perto de 20% do total."
        )
    elif stats.get("avatar_share", 0.0) and stats["avatar_share"] < 0.10:
        linhas.append(
            f"Sua última tentativa saiu com {share_pct:.0f}% de avatar; o piso "
            f"é 10%. Adicione avatar nas reentradas do meio do vídeo."
        )
    return "\n".join(linhas)


async def no_video(estado: EstadoMarketing) -> dict:
    """
    Produz o manifesto v2 (roteiro segmentado 80/20) e desenha os slides.

    Não dispara HeyGen nem ElevenLabs: isso é a pipeline, acionada depois da
    aprovação. Aqui só nasce o que o humano precisa revisar.
    """
    with span("no.video", tenant=estado.get("tenant_id")):
        try:
            from scriptwriter_agent import run_scriptwriter
            from slide_designer_agent import design_all_slides
            from manifest_builder import validate_manifest

            pauta = estado.get("pauta") or {}

            retry_note = ""
            manifesto: dict = {}
            violacoes: list[str] = []
            stats: dict = {}
            for tentativa in range(1, VIDEO_MAX_TENTATIVAS + 1):
                manifesto = await run_scriptwriter(
                    pauta, estado.get("artigo_markdown", ""), retry_note=retry_note,
                )
                violacoes, stats = validate_manifest(manifesto)
                if not violacoes:
                    break
                if tentativa < VIDEO_MAX_TENTATIVAS:
                    logger.warning(
                        "[grafo/video] manifesto rejeitado na tentativa %d/%d "
                        "(%.0f%% avatar) — reenviando com correção: %s",
                        tentativa, VIDEO_MAX_TENTATIVAS,
                        stats.get("avatar_share", 0.0) * 100, "; ".join(violacoes),
                    )
                    retry_note = _nota_corretiva(violacoes, stats)

            if violacoes:
                # Falhar aqui custa zero; falhar depois custa HeyGen. Já
                # tentamos a correção automática — sobrou pro humano.
                raise RuntimeError(
                    f"manifesto viola a regra do produto após "
                    f"{VIDEO_MAX_TENTATIVAS} tentativas: " + "; ".join(violacoes)
                )

            slides: dict[str, str] = {}
            try:
                slides = await design_all_slides(manifesto, pauta)
            except Exception as exc:
                logger.warning("[grafo/video] slide_designer falhou: %s", exc)

            set_attributes(
                segmentos=stats["segment_count"],
                avatar_share=stats["avatar_share"],
                slides=len(slides),
            )
            return {
                "manifesto": manifesto,
                "slide_htmls": slides,
                "video_titulo": manifesto.get("title", ""),
                "fase": "aguardando_aprovacao_video",
                "trilha": [
                    f"video: {stats['segment_count']} segmentos, "
                    f"{stats['avatar_share'] * 100:.0f}% avatar, {len(slides)} slides"
                ],
            }
        except Exception as exc:
            return {**_erro("video", exc, fatal=True), "fase": "erro"}


async def no_gate_video(estado: EstadoMarketing) -> dict:
    aprov = estado.get("aprovacao_video") or {}
    decisao = aprov.get("decisao")
    if decisao:
        registrar_decisao(
            _db(), estado.get("tenant_id"),
            gate="video", decisao=decisao,
            comentario=aprov.get("comentario", ""),
            tema=estado.get("tema", ""),
        )
    return {"trilha": [f"gate_video: {decisao or 'aguardando'}"]}


def rota_gate_video(estado: EstadoMarketing) -> str:
    decisao = (estado.get("aprovacao_video") or {}).get("decisao")
    if decisao == "aprovado":
        return "social"
    if decisao == "ajustar":
        return "video"
    return "fim"


# ── 5. Social: o funil para o vídeo ───────────────────────────────────────────

async def no_social(estado: EstadoMarketing) -> dict:
    """
    Monta o plano social — um especialista por canal, em paralelo.

    O fan-out não é enfeite arquitetural: o `responseSchema` do Vertex rejeita
    schemas acima de ~60 nós, e o PlanoSocial inteiro tem 69. Gerar canal a
    canal mantém cada schema em ~18 nós, deixa o modelo focado num formato de
    cada vez, e faz uma falha no carrossel não levar o LinkedIn junto.

    Roda depois do gate do vídeo porque cada peça precisa saber o que o vídeo
    entrega — é essa lacuna que faz alguém clicar.
    """
    with span("no.social", tenant=estado.get("tenant_id")):
        from skills.registry import montar_instrucao
        from social_schemas import CANAIS, LoteStories, PlanoSocial
        from structured import generate_structured

        pauta     = estado.get("pauta") or {}
        manifesto = estado.get("manifesto") or {}
        promessa  = pauta.get("angulo_video") or pauta.get("tese", "")
        titulo    = estado.get("video_titulo") or pauta.get("titulo", "")
        segmentos = manifesto.get("youtube", {}).get("segments", [])
        roteiro   = "\n".join(s.get("script", "") for s in segmentos)[:5000]

        instrucao = montar_instrucao(
            _db(), estado.get("tenant_id"), "distribuidor",
            contexto_extra=montar_contexto(_db(), estado.get("tenant_id")),
        )
        base = (
            f"Vídeo: {titulo}\n"
            f"Promessa do vídeo: {promessa}\n\n"
            f"=== ROTEIRO ===\n{roteiro}\n\n"
            f"=== ARTIGO ===\n{(estado.get('artigo_markdown') or '')[:4000]}\n\n"
        )

        # Mecânica de cada plataforma — o que muda o formato, não o conteúdo.
        # Cada uma foi corrigida a partir de um erro visto na revisão real:
        # link no corpo do LinkedIn, link em legenda do Instagram, primeira
        # resposta do Threads repetindo o gancho, stories esparsas.
        REGRAS_POR_CANAL = {
            "linkedin": (
                "Link no CORPO do post reduz o alcance no LinkedIn — é métrica "
                "conhecida da plataforma. Quando o CTA leva a um link "
                "(assistir/ler_artigo), NÃO ponha [LINK_CANAL]/[LINK_ARTIGO] no "
                "`corpo` nem no `cta.texto` — o `corpo` só anuncia que o link está "
                "no comentário ('o link está no primeiro comentário', "
                "'deixei o link fixado aqui embaixo'), e o marcador vai em "
                "`comentario_fixado`. CTAs de engajamento puro (salvar, marcar, "
                "comentar) não precisam de comentario_fixado — deixe None."
            ),
            "carrossel": (
                "O Instagram NÃO renderiza link clicável em legenda nem em "
                "comentário. Nunca use [LINK_CANAL]/[LINK_ARTIGO] em nenhum campo. "
                "Quando o CTA levar ao vídeo, referencie a BIO em linguagem "
                "natural: 'o vídeo completo está no link da bio', 'link na bio "
                "pra assistir'. O último slide do carrossel é o CTA."
            ),
            "stories": (
                "Gere de 2 a 3 PUBLICAÇÕES de stories por dia, espalhadas ao "
                "longo da semana (varie dia_offset, não empilhe tudo num dia só). "
                "CADA publicação (`Story`) tem de 3 a 4 FRAMES que a pessoa toca "
                "para avançar — não é um frame solto, é uma sequência com começo, "
                "meio e o CTA no fim. Todo frame leva uma `ilustracao`: descreva a "
                "imagem de fundo, porque texto sozinho sobre nada não segura "
                "atenção em story. Mesma regra de link do carrossel: nunca "
                "[LINK_CANAL]/[LINK_ARTIGO] — referencie a bio."
            ),
            "threads": (
                "`gancho` é o post RAIZ. `posts` são as respostas que você "
                "mesmo posta em seguida, encadeadas — cada uma acrescenta um "
                "fato, passo ou número que a anterior ainda não deu. NUNCA "
                "reformule o gancho como primeira resposta: se posts[0] disser a "
                "mesma coisa que o gancho com outras palavras, a thread falha."
            ),
            "youtube_community": (
                "Quem lê já está inscrito no canal — não precisa vender a "
                "inscrição, precisa dar um motivo para abrir o vídeo AGORA. "
                "Enquete nativa (`enquete_opcoes`) funciona bem quando há uma "
                "escolha real ligada ao tema do vídeo."
            ),
        }

        async def um_canal(canal: str, modelo, descricao: str):
            return canal, await generate_structured(
                modelo,
                prompt=(
                    f"{base}"
                    f"Gere os {descricao} do plano da semana. Escolha o método de "
                    f"copy e o tipo de CTA que MELHOR servem a este canal — e "
                    f"declare os ids escolhidos. Distribua em dia_offset de 0 a 7.\n\n"
                    f"━━━ REGRAS DESTE CANAL ━━━\n{REGRAS_POR_CANAL.get(canal, '')}"
                ),
                system_instruction=instrucao,
                temperature=0.6,
            )

        async def stories_terco(rotulo: str, offset_min: int, offset_max: int):
            # LoteStories cobre só um terço da semana — ver o comentário em
            # social_schemas.py sobre o teto de array aninhado do Vertex.
            return "stories", await generate_structured(
                LoteStories,
                prompt=(
                    f"{base}"
                    f"Gere as publicações de stories da {rotulo} da semana "
                    f"(dia_offset de {offset_min} a {offset_max}). De 2 a 3 "
                    f"publicações por dia, cada uma com 3 a 4 frames.\n\n"
                    f"━━━ REGRAS DESTE CANAL ━━━\n{REGRAS_POR_CANAL.get('stories', '')}"
                ),
                system_instruction=instrucao,
                temperature=0.6,
            )

        resultados = await asyncio.gather(
            *[um_canal(c, m, d) for c, (m, d) in CANAIS.items()],
            stories_terco("primeira parte", 0, 2),
            stories_terco("segunda parte", 3, 5),
            stories_terco("terceira parte", 6, 7),
            return_exceptions=True,
        )

        lotes: dict[str, list] = {c: [] for c in {*CANAIS, "stories"}}
        falhas: list[dict] = []
        for r in resultados:
            if isinstance(r, Exception):
                falhas.append({"no": "social", "mensagem": str(r)[:300], "fatal": False})
                continue
            canal, lote = r
            lotes[canal] = lotes[canal] + lote.pecas

        # stories vem de 3 chamadas independentes (teto de array aninhado —
        # ver social_schemas.py); cada uma numera 'id' do zero, então
        # "st-01" de um terço colide com "st-01" de outro. Renumerar aqui
        # garante unicidade sem depender do modelo coordenar entre chamadas
        # que nem se veem.
        lotes["stories"] = [
            s.model_copy(update={"id": f"st-{i+1:02d}"})
            for i, s in enumerate(lotes["stories"])
        ]

        if not any(lotes.values()):
            return {**_erro("social", RuntimeError("nenhum canal gerou peças"), False),
                    "fase": "concluido"}

        plano = PlanoSocial(
            tema=estado.get("tema", ""),
            video_titulo=titulo,
            promessa_video=promessa[:280] or titulo,
            linkedin=lotes["linkedin"], threads=lotes["threads"],
            carrossel=lotes["carrossel"], stories=lotes["stories"],
            youtube_community=lotes["youtube_community"],
        )

        avisos  = plano.diagnostico()
        metodos = {p.copy_skill_id for p in plano.todas_as_pecas()}
        set_attributes(pecas=plano.total_pecas(), metodos_distintos=len(metodos),
                       canais_com_falha=len(falhas))
        trilha = [f"social: {plano.total_pecas()} peças, {len(metodos)} métodos de copy"]
        trilha += [f"social: {a}" for a in avisos]
        trilha += [f"social: canal falhou — {f['mensagem'][:60]}" for f in falhas]

        return {
            "plano_social": plano.model_dump(mode="json"),
            "fase": "concluido",
            "trilha": trilha,
            "erros": falhas,
        }
