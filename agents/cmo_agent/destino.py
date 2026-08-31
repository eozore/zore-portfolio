# -*- coding: utf-8 -*-
"""
destino.py — Para onde cada peça manda a pessoa, e com que hashtags.

Duas regras que valiam para o canal e não existiam em lugar nenhum do código.

**Toda peça aponta para algum lugar.** As stories publicadas até 31/08 não
diziam que havia vídeo no YouTube: o rodapé mostrava "eozore.com" (o site, não
o vídeo) e o CTA vinha do modelo com frases vagas do tipo "veja a arquitetura
completa". Quem assistiu não ficou sabendo que existia um vídeo, que é o
objetivo do funil inteiro. O Instagram não transforma URL em link — nem em
legenda nem em comentário —, então lá o destino precisa estar ESCRITO, na
imagem e no texto, ou não existe.

**As hashtags são fixas por série.** Antes eram três genéricas coladas no
código (`#Shorts #IA #MachineLearning`), iguais para todo vídeo. Fixas por
série é decisão de descoberta: quem achar um conteúdo por uma hashtag encontra
o resto da série pela mesma, o que não acontece quando cada peça inventa as
suas.
"""

from __future__ import annotations

from typing import Optional

# Onde o conteúdo longo vive. É o destino padrão de toda peça social: o vídeo
# é a âncora do funil, e tudo aponta para ele.
CANAL_YOUTUBE = "youtube.com/@eozore"

# Hashtags por série. Máximo 4: acima disso o alcance não melhora e a legenda
# fica com cara de spam. A primeira é sempre a da série — é ela que agrega o
# catálogo quando alguém chega por uma peça solta.
HASHTAGS_POR_SERIE: dict[str, list[str]] = {
    "engenharia-de-ia":              ["engenhariadeia", "llm", "mlops", "devbr"],
    "engenharia-de-software-com-ia": ["engenhariadeia", "vibecoding", "devbr", "ia"],
    "ia-para-lideres":               ["iaparalideres", "lideranca", "tecnologia", "gestao"],
    "estatistica":                   ["estatistica", "datascience", "analisededados"],
    "ml":                            ["machinelearning", "mlops", "datascience"],
}

# Usadas quando a série não está no mapa. Não invente por tema: a graça de
# hashtag fixa é a repetição, e uma tag nova a cada post não agrega nada.
HASHTAGS_PADRAO = ["engenhariadeia", "ia", "devbr"]


def hashtags_da_serie(serie: Optional[str], limite: int = 4) -> list[str]:
    """As hashtags da série, sem '#', já limitadas."""
    chave = (serie or "").strip().lower()
    return (HASHTAGS_POR_SERIE.get(chave) or HASHTAGS_PADRAO)[:limite]


def formatar_hashtags(serie: Optional[str], extras: Optional[list[str]] = None,
                      limite: int = 4) -> str:
    """`#tag #tag` pronto para colar no fim de uma legenda."""
    tags = list(hashtags_da_serie(serie, limite))
    for e in extras or []:
        t = e.lstrip("#").strip()
        if t and t.lower() not in {x.lower() for x in tags}:
            tags.append(t)
    return " ".join(f"#{t}" for t in tags[:limite + len(extras or [])])


# ── Destino por plataforma ────────────────────────────────────────────────────

def destino_da_peca(platform: str, video_url: str = "", artigo_url: str = "") -> str:
    """
    A frase que diz para onde ir, escrita para AQUELA plataforma.

    A diferença não é estética, é de mecânica: LinkedIn, Threads e a comunidade
    do YouTube renderizam URL, então lá o destino é o link. O Instagram não
    renderiza nada — a URL vira texto morto —, então lá o destino tem que ser
    uma instrução ("no YouTube", "link na bio") que a pessoa consiga seguir à
    mão.
    """
    alvo = video_url or artigo_url
    if platform == "instagram":
        # Nomear o YouTube é o ponto. "Veja mais no link da bio" não informa
        # que existe vídeo — foi exatamente o que faltou nas stories de 31/08.
        return "Vídeo completo no YouTube — link na bio"
    if alvo:
        return f"Vídeo completo: {alvo}" if video_url else f"Artigo completo: {alvo}"
    return f"Vídeo completo no canal: {CANAL_YOUTUBE}"


def marca_de_destino(platform: str) -> str:
    """
    Selo curto para queimar na IMAGEM, onde não cabe uma frase inteira.

    Existe porque no Instagram a legenda não leva link: se a imagem não disser
    para onde ir, a peça não aponta para lugar nenhum.
    """
    return "▶ YouTube /@eozore" if platform == "instagram" else "eozore.com"
