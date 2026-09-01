# -*- coding: utf-8 -*-
"""
social_schemas.py — Contrato do plano de mídias sociais.

A regra que organiza tudo aqui:

    TODO conteúdo social existe para levar a pessoa a ASSISTIR AO VÍDEO
    DO YOUTUBE. Não é distribuição paralela do artigo: é funil.

Isso muda o que cada peça precisa ter. Um post não pode "explicar o assunto
por completo" — se explicar, o leitor fica satisfeito e não clica. Cada peça
entrega UM insight fechado e deixa uma lacuna nomeada que só o vídeo resolve.

O CTA não é um enfeite no fim. Ele é um campo obrigatório e tipado, com o
destino declarado, porque o problema real observado em produção foi copy
saindo com link para o blog quando o assunto era o vídeo — e com o texto
cortado no meio da frase.

Os limites de caracteres são de verdade, validados pelo Pydantic: o modelo
não "tenta" respeitar, ele é rejeitado se não respeitar.
"""

from __future__ import annotations

import re

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class CTATipo(str, Enum):
    """
    O que a peça PEDE ao leitor.

    O objetivo do plano é gerar audiência para o vídeo — mas mandar TODA peça
    para o vídeo cansa o público e desperdiça o que as redes fazem melhor.
    Um "salve este post" não gera view hoje; ele aumenta a entrega do próximo
    post, que gera. É funil indireto, e compõe.

    Por isso o tipo é escolhido pelo agente peça a peça, e a regra de mistura
    é validada no PLANO — não em cada peça isolada.
    """
    ASSISTIR   = "assistir"    # conversão direta: leva ao vídeo agora
    SALVAR     = "salvar"      # sinal forte de algoritmo, entrega futura
    MARCAR     = "marcar"      # traz gente nova ao perfil
    COMENTAR   = "comentar"    # estende alcance, principalmente no LinkedIn
    SEGUIR     = "seguir"      # converte visitante em audiência recorrente
    COMPARTILHAR = "compartilhar"
    LER_ARTIGO = "ler_artigo"  # aprofundamento no blog


# Tipos que levam alguém ao vídeo AGORA. O resto trabalha alcance.
CTA_CONVERSAO_DIRETA = {CTATipo.ASSISTIR}


class Plataforma(str, Enum):
    LINKEDIN   = "linkedin"
    INSTAGRAM  = "instagram"
    THREADS    = "threads"
    YOUTUBE    = "youtube_community"


# Marcadores de link. O publisher os substitui pela URL real na publicação —
# nunca antes, porque a peça é agendada para D+1..D+7 e o vídeo sai em D+0.
LINK_MARCADORES = ("[LINK_CANAL]", "[LINK_ARTIGO]")


class CTA(BaseModel):
    """
    Chamada para ação com destino explícito.

    `texto` é o que aparece no CORPO VISÍVEL do post — nunca contém marcador
    de link. Duas mecânicas de plataforma, ambas medidas em produção:

      LinkedIn:  link no corpo do post reduz o alcance do algoritmo. O link
                 vai em `PostLinkedIn.comentario_fixado`, publicado logo após
                 o post — `texto` só anuncia que ele está lá.
      Instagram: não existe link clicável em legenda nem comentário. O
                 caminho é sempre "link na bio" — `texto` referencia a bio em
                 linguagem natural, nunca um marcador.

    Só o Threads e o YouTube Community aceitam o marcador dentro do próprio
    `texto`, porque lá o link É publicável no post.
    """
    texto:   str = Field(
        min_length=8, max_length=120,
        description="Frase de ação, como aparece no corpo do post.",
    )
    tipo: CTATipo = Field(
        description="O que a peça pede. Escolha o que serve àquela mídia e momento.",
    )
    skill_id: str = Field(
        description="Id da skill de CTA aplicada (ex: 'cta-salvar'). Declare a escolha.",
    )

    @field_validator("texto")
    @classmethod
    def sem_url_literal(cls, v: str) -> str:
        # Uma URL escrita no texto congela o link no momento da GERAÇÃO. Se o
        # vídeo ainda não subiu, ela aponta para lugar nenhum — e foi
        # exatamente assim que posts saíram apontando para o blog.
        if "http://" in v or "https://" in v or "youtu.be" in v:
            raise ValueError("CTA não pode conter URL literal")
        return v.strip()


class PecaBase(BaseModel):
    """Campos que toda peça social carrega."""
    id:     str = Field(description="Identificador curto e único, ex: 'li-01'.")
    copy_skill_id: str = Field(
        description=(
            "Id do método de copy aplicado (ex: 'copy-pas'). O agente escolhe "
            "olhando o conteúdo e a mídia; declarar a escolha é o que permite "
            "auditar o porquê e medir depois qual método rendeu mais."
        ),
    )
    gancho: str = Field(
        min_length=10, max_length=160,
        description="Primeira linha. Para o scroll. Sem saudação, sem emoji.",
    )
    cta:    CTA
    lacuna: str = Field(
        min_length=10, max_length=200,
        description=(
            "O que esta peça deliberadamente NÃO responde, e que o vídeo "
            "responde. É a razão de a pessoa clicar."
        ),
    )
    dia_offset: int = Field(
        ge=0, le=14,
        description="Dias após a publicação do vídeo. 0 = mesmo dia do vídeo.",
    )


class PostLinkedIn(PecaBase):
    corpo: str = Field(
        min_length=200, max_length=1300,
        description=(
            "Post completo. Tom técnico e direto, quebras de linha curtas. "
            "Entrega UM insight fechado e para. Não resume o vídeo inteiro."
        ),
    )
    hashtags: List[str] = Field(
        default_factory=list, max_length=3,
        description="No máximo 3, sem '#' no valor.",
    )
    comentario_fixado: Optional[str] = Field(
        default=None, max_length=200,
        description=(
            "Texto do PRIMEIRO COMENTÁRIO, publicado por você logo após o post. "
            "É AQUI que o link mora — [LINK_CANAL] ou [LINK_ARTIGO]. "
            "Obrigatório quando cta.tipo leva a um link (assistir, ler_artigo); "
            "None quando o CTA é engajamento puro (salvar, marcar, comentar, "
            "seguir), que não precisa de link nenhum."
        ),
    )

    @field_validator("corpo")
    @classmethod
    def sem_link_no_corpo(cls, v: str) -> str:
        # Link no CORPO do post reduz o alcance no algoritmo do LinkedIn —
        # métrica conhecida da plataforma. O link mora no comentário fixado.
        if any(m in v for m in LINK_MARCADORES):
            raise ValueError(
                "corpo do LinkedIn não pode conter link — use comentario_fixado"
            )
        return v

    @field_validator("comentario_fixado")
    @classmethod
    def comentario_leva_link_quando_existe(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not any(m in v for m in LINK_MARCADORES):
            raise ValueError(
                "comentario_fixado existe para carregar o link — sem "
                "[LINK_CANAL]/[LINK_ARTIGO] ele não serve a nenhum propósito"
            )
        return v

    @field_validator("cta")
    @classmethod
    def cta_sem_link_no_corpo_visivel(cls, v: CTA) -> CTA:
        # cta.texto é renderizado junto do post, não do comentário — o mesmo
        # motivo que tira o link do `corpo` vale aqui.
        if any(m in v.texto for m in LINK_MARCADORES):
            raise ValueError("cta.texto do LinkedIn não pode conter link — use comentario_fixado")
        return v


class PostThreads(PecaBase):
    """
    Uma thread é o post raiz (`gancho`) mais SUAS PRÓPRIAS RESPOSTAS a ele,
    publicadas em sequência — é assim que o Threads encadeia visualmente.

    `posts[0]` é a PRIMEIRA RESPOSTA, não o post raiz — o raiz já é o
    `gancho`. Bug observado em produção: o modelo repetia o `gancho` dentro
    de `posts[0]`, publicando a mesma frase duas vezes seguidas. Cada resposta
    tem que ACRESCENTAR uma informação nova que o post anterior não deu —
    é o desenrolar da ideia, não a reafirmação dela.
    """
    posts: List[str] = Field(
        min_length=2, max_length=5,
        description=(
            "As RESPOSTAS ao gancho, em ordem — não repetem o gancho. Cada "
            "uma soma um fato/passo novo. Máximo 500 caracteres cada."
        ),
    )

    @field_validator("posts")
    @classmethod
    def limite_por_post(cls, v: List[str]) -> List[str]:
        for i, post in enumerate(v):
            if len(post) > 500:
                raise ValueError(f"post {i + 1} tem {len(post)} chars (máx 500)")
        return v

    @field_validator("posts")
    @classmethod
    def sem_repeticao_entre_si(cls, v: List[str]) -> List[str]:
        # Compara por conjunto de palavras normalizado: pega paráfrase quase
        # idêntica, não só string igual — foi exatamente isso que vazou (o
        # primeiro comentário repetia a frase principal com uma vírgula
        # diferente).
        def normaliza(t: str) -> set[str]:
            return set(t.lower().split())

        vistos: list[set[str]] = []
        for i, post in enumerate(v):
            palavras = normaliza(post)
            for j, anterior in enumerate(vistos):
                uniao = palavras | anterior
                if not uniao:
                    continue
                sobreposicao = len(palavras & anterior) / len(uniao)
                if sobreposicao > 0.7:
                    raise ValueError(
                        f"post {i + 1} repete o post {j + 1} quase palavra por "
                        f"palavra ({sobreposicao:.0%} de sobreposição) — cada "
                        "resposta precisa dizer algo NOVO"
                    )
            vistos.append(palavras)
        return v

    @field_validator("posts")
    @classmethod
    def primeira_resposta_nao_repete_o_gancho(cls, v: List[str], info) -> List[str]:
        gancho = (info.data or {}).get("gancho", "")
        if not gancho or not v:
            return v
        g = set(gancho.lower().split())
        p0 = set(v[0].lower().split())
        uniao = g | p0
        if uniao and len(g & p0) / len(uniao) > 0.6:
            raise ValueError(
                "posts[0] repete o gancho — é a PRIMEIRA RESPOSTA, tem que "
                "avançar a ideia, não reafirmar a frase de abertura"
            )
        return v


class SlideCarrossel(BaseModel):
    numero:  int = Field(ge=1, le=10)
    titulo:  str = Field(max_length=60, description="Uma linha, legível a 3 metros.")
    corpo:   str = Field(max_length=220, description="2 a 3 linhas no máximo.")


# Mixin para as peças do Instagram: a plataforma NÃO renderiza link nem em
# legenda nem em comentário. O único caminho é o link fixo do perfil — por
# isso nenhum campo aqui pode carregar [LINK_CANAL]/[LINK_ARTIGO], e o CTA
# de conversão referencia a bio em vez de apontar um marcador.
def _validar_sem_link_instagram(campo: str, texto: str) -> str:
    if any(m in texto for m in LINK_MARCADORES):
        raise ValueError(
            f"{campo} do Instagram não pode conter link — a plataforma não "
            "renderiza link em legenda nem comentário. Referencie a bio."
        )
    return texto


class Carrossel(PecaBase):
    """
    Carrossel do Instagram. O último slide é sempre o CTA para o vídeo — é o
    slide de maior retenção e o momento de mandar para a bio.
    """
    slides:  List[SlideCarrossel] = Field(min_length=4, max_length=10)
    legenda: str = Field(max_length=2200, description="Legenda do feed.")

    @field_validator("legenda")
    @classmethod
    def legenda_sem_link(cls, v: str) -> str:
        return _validar_sem_link_instagram("legenda", v)

    @field_validator("cta")
    @classmethod
    def cta_sem_link(cls, v: CTA) -> CTA:
        _validar_sem_link_instagram("cta.texto", v.texto)
        return v


class FrameStory(BaseModel):
    """
    Um frame dentro de uma sequência de stories — o que a pessoa vê ao tocar
    para avançar. 3 a 4 frames formam UMA publicação de stories.
    """
    ordem:      int = Field(ge=1, le=4)
    texto:      str = Field(max_length=140, description="Texto sobreposto. Curto — story se lê em 3s.")
    ilustracao: str = Field(
        min_length=10, max_length=200,
        description=(
            "Descrição da imagem/ilustração de fundo deste frame — o que o "
            "designer desenha. Sem isto o frame vira só texto sobre fundo liso."
        ),
    )
    enquete: Optional[str] = Field(
        default=None, max_length=80,
        description="Pergunta de enquete, só no último frame quando fizer sentido.",
    )


class Story(PecaBase):
    """
    UMA publicação de stories = uma sequência de 3 a 4 frames que a pessoa
    toca para avançar. Não é um frame só — no Instagram real, "postar um
    story" quase sempre significa postar uma sequência.
    """
    frames: List[FrameStory] = Field(min_length=3, max_length=4)

    @field_validator("frames")
    @classmethod
    def sem_link_nos_frames(cls, v: List[FrameStory]) -> List[FrameStory]:
        for f in v:
            _validar_sem_link_instagram(f"frame {f.ordem}", f.texto)
            if f.enquete:
                _validar_sem_link_instagram(f"enquete do frame {f.ordem}", f.enquete)
        return v

    @field_validator("cta")
    @classmethod
    def cta_sem_link(cls, v: CTA) -> CTA:
        _validar_sem_link_instagram("cta.texto", v.texto)
        return v


class PostYouTubeCommunity(PecaBase):
    """
    Post de texto na aba Comunidade do canal. Alcança quem JÁ é inscrito —
    a plateia mais barata de reconquistar, porque está a um toque do vídeo
    novo assim que ele sai. É por isso que faz sentido publicar no D+0,
    junto com o lançamento, e não só depois.
    """
    texto: str = Field(
        min_length=20, max_length=500,
        description="Texto do post. Quem lê já está no canal — sem enrolação.",
    )
    enquete_opcoes: Optional[List[str]] = Field(
        default=None, min_length=2, max_length=4,
        description="Opções de enquete nativa do YouTube, quando fizer sentido.",
    )


# Uma afirmação sobre o vídeo é a interseção de duas coisas: falar DO vídeo e
# dizer que ele DEMONSTRA algo. "Falo sobre isso no vídeo" é promessa de tema e
# é honesta; "no vídeo eu mostro o código medindo" é promessa de conteúdo, e
# essa precisa existir em cena.
MARCADORES_VIDEO = (
    "no vídeo", "no video", "nesse vídeo", "neste vídeo", "no episódio",
    "assista", "no youtube",
)
VERBOS_DE_DEMONSTRACAO = (
    "mostro", "mostramos", "mostra", "demonstro", "demonstramos", "demonstra",
    "meço", "medimos", "mede", "medindo", "implemento", "implementamos",
    "implementa", "rodo", "rodamos", "roda ", "executo", "executamos",
    "comparo", "comparamos", "código", "codigo", "ao vivo", "na tela",
)


def checar_promessas_do_video(plano: "PlanoSocial", roteiro: str) -> List[str]:
    """
    Avisa quando uma peça promete algo que o roteiro do vídeo não sustenta.

    Nasceu de uma publicação de 01/09 que afirmou que "no vídeo fizemos código
    mostrando e medindo a diferença" — o vídeo não media nada, o código estava
    no ARTIGO. O agente recebe as duas peças e conflacionava as duas.

    A checagem é de PALAVRA, não semântica: procura os termos concretos da
    afirmação dentro do roteiro. Erra para o lado de avisar demais, e um aviso
    a mais na revisão custa um segundo — a promessa falsa custa a confiança de
    quem clicou.
    """
    if not roteiro:
        return []
    base = roteiro.lower()
    avisos: List[str] = []
    for peca_id, frase in plano.afirmacoes_sobre_o_video():
        # Palavras "de conteúdo" da frase: as que carregam a promessa.
        termos = [
            t for t in re.findall(r"[a-zà-ú]{5,}", frase.lower())
            if t not in _IGNORADAS
        ]
        if not termos:
            continue
        ausentes = [t for t in termos if t not in base]
        # Metade dos termos fora do roteiro é sinal forte de invenção.
        if len(ausentes) > len(termos) / 2:
            avisos.append(
                f"[{peca_id}] afirma sobre o vídeo algo que o roteiro não "
                f"sustenta: \"{frase[:110]}\" (fora do roteiro: {', '.join(ausentes[:5])})"
            )
    return avisos


_IGNORADAS = frozenset("""
video vídeo episódio youtube assista assistir sobre quando porque assim
completo inteiro mesmo também ainda depois antes muito pouco nesse neste
""".split())


class PlanoSocial(BaseModel):
    """
    O plano completo da semana, todo apontando para o mesmo vídeo.

    A distribuição ao longo dos dias importa: publicar tudo em D+0 compete com
    o próprio vídeo pela atenção. O calendário espalha as peças para manter o
    vídeo sendo redescoberto durante a semana.
    """
    tema:            str
    video_titulo:    str = Field(description="Título do vídeo para o qual tudo aponta.")
    promessa_video:  str = Field(
        min_length=20, max_length=280,
        description="O que a pessoa ganha assistindo. Todas as lacunas apontam para isto.",
    )
    linkedin:  List[PostLinkedIn]         = Field(min_length=1, max_length=4)
    threads:   List[PostThreads]          = Field(min_length=1, max_length=3)
    carrossel: List[Carrossel]            = Field(min_length=1, max_length=2)
    # 2 a 3 publicações de stories POR DIA — cada uma é uma Story (3-4 frames),
    # não um frame solto. Para uma janela de ~7 dias isso é de 10 a 21 posts
    # de stories. Volume alto de propósito: é o formato mais barato de repetir
    # o convite ao vídeo sem cansar quem vê o feed principal.
    stories:   List[Story]                = Field(min_length=10, max_length=21)
    youtube_community: List[PostYouTubeCommunity] = Field(
        default_factory=list, max_length=3,
        description="Posts na aba Comunidade — alcançam quem já é inscrito.",
    )

    def total_pecas(self) -> int:
        return (len(self.linkedin) + len(self.threads) + len(self.carrossel)
                + len(self.stories) + len(self.youtube_community))

    def todas_as_pecas(self) -> List[PecaBase]:
        return [*self.linkedin, *self.threads, *self.carrossel,
                *self.stories, *self.youtube_community]

    def afirmacoes_sobre_o_video(self) -> List[tuple[str, str]]:
        """
        Trechos que afirmam algo sobre o VÍDEO, para conferir contra o roteiro.

        Só detecta a afirmação; quem julga se ela procede é
        `checar_promessas_do_video`, que tem o inventário em mãos. Separar as
        duas coisas é o que permite testar a detecção sem um manifesto.
        """
        achados: List[tuple[str, str]] = []
        for p in self.todas_as_pecas():
            for campo in ("gancho", "corpo", "legenda"):
                texto = getattr(p, campo, None)
                if not isinstance(texto, str):
                    continue
                for frase in re.split(r"(?<=[.!?])\s+", texto):
                    baixo = frase.lower()
                    if any(m in baixo for m in MARCADORES_VIDEO) and any(
                        v in baixo for v in VERBOS_DE_DEMONSTRACAO
                    ):
                        achados.append((getattr(p, "id", "?"), frase.strip()))
        return achados

    def diagnostico(self) -> List[str]:
        """
        Problemas de COMPOSIÇÃO do plano — não de peça isolada.

        A regra do produto não é "todo CTA leva ao vídeo". É que o plano, como
        conjunto, gere audiência para o vídeo: uma parte converte agora, o
        resto trabalha alcance para que a próxima converta mais.

        Retorna avisos legíveis, não exceções: um plano desequilibrado ainda é
        utilizável, mas o desequilíbrio precisa APARECER na revisão em vez de
        passar batido.
        """
        pecas = self.todas_as_pecas()
        if not pecas:
            return ["plano vazio"]

        avisos: List[str] = []

        diretos = [p for p in pecas if p.cta.tipo in CTA_CONVERSAO_DIRETA]
        fatia = len(diretos) / len(pecas)
        if fatia == 0:
            avisos.append("nenhuma peça leva ao vídeo — o plano não converte")
        elif fatia < 0.25:
            avisos.append(
                f"só {fatia:.0%} das peças levam ao vídeo (mínimo saudável: 25%)"
            )
        elif fatia > 0.7:
            avisos.append(
                f"{fatia:.0%} das peças pedem para assistir — repetição cansa o "
                "público e derruba o alcance das próximas"
            )

        metodos = {p.copy_skill_id for p in pecas}
        if len(metodos) < 3 and len(pecas) >= 4:
            avisos.append(
                f"só {len(metodos)} método(s) de copy em {len(pecas)} peças — "
                "todas vão soar iguais"
            )

        tipos_cta = {p.cta.tipo for p in pecas}
        if len(tipos_cta) < 2 and len(pecas) >= 3:
            avisos.append("todos os CTAs são do mesmo tipo")

        if self.stories:
            dias = {s.dia_offset for s in self.stories}
            media_por_dia = len(self.stories) / max(1, len(dias))
            if len(dias) < 4:
                avisos.append(
                    f"stories concentradas em {len(dias)} dia(s) — espalhe ao "
                    "longo da semana em vez de empilhar tudo no mesmo dia"
                )
            if media_por_dia > 4:
                avisos.append(
                    f"média de {media_por_dia:.1f} publicações de stories por "
                    "dia — mais de 3-4 no mesmo dia cansa quem assiste"
                )

        return avisos


# ── Geração por canal ─────────────────────────────────────────────────────────
#
# O Vertex rejeita responseSchema acima de ~60 nós: o PlanoSocial inteiro
# (69 nós) devolvia HTTP 400 "invalid argument", enquanto cada peça isolada
# passava. Medido bissectando campo a campo.
#
# Gerar um canal por chamada resolve isso e é melhor por outros três motivos:
# o modelo se concentra num formato de cada vez, as chamadas rodam em
# paralelo, e uma falha no carrossel não perde o LinkedIn junto.
#
# `stories` tem um SEGUNDO teto, independente da contagem de nós: um
# array-de-array com cardinalidade grande nos dois níveis (pecas × frames)
# recebe 400 mesmo com poucos nós de estrutura. Bissectado por chamada real
# à API contra o `Story` de verdade (que carrega PecaBase — id, cta,
# gancho, lacuna — além de `frames`): outer maxItems=9 passa, =10 já
# falha. Por isso LoteStories cobre só um TERÇO da semana; graph/nodes.py
# soma três lotes em Python, onde o limite de 10-21 do PlanoSocial.stories
# é validado sem tocar o Vertex de novo.

class LoteLinkedIn(BaseModel):
    pecas: List[PostLinkedIn] = Field(min_length=1, max_length=4)

class LoteThreads(BaseModel):
    pecas: List[PostThreads] = Field(min_length=1, max_length=3)

class LoteCarrossel(BaseModel):
    pecas: List[Carrossel] = Field(min_length=1, max_length=2)

class LoteStories(BaseModel):
    """
    Cobre só um TERÇO da semana — ver nota acima sobre o teto de array
    aninhado. min_length=4 é proposital: 3 lotes somados garantem pelo
    menos 12 peças mesmo no pior caso, folga acima do piso de 10 que
    PlanoSocial.stories exige (o pior caso de 3×3=9 ficaria abaixo do piso).
    """
    pecas: List[Story] = Field(min_length=4, max_length=6)

class LoteYouTubeCommunity(BaseModel):
    pecas: List[PostYouTubeCommunity] = Field(min_length=1, max_length=3)


CANAIS = {
    "linkedin":  (LoteLinkedIn,  "posts de LinkedIn"),
    "threads":   (LoteThreads,   "séries para o Threads"),
    "carrossel": (LoteCarrossel, "carrosséis de Instagram"),
    "youtube_community": (LoteYouTubeCommunity, "posts na aba Comunidade do YouTube"),
}
"""Canais gerados um-por-chamada com o mesmo prompt genérico. `stories` fica
de fora: precisa de 2 chamadas com prompts diferentes (metade da semana cada)
por causa do teto de array aninhado — ver `no_social` em graph/nodes.py."""
