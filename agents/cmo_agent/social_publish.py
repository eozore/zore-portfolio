# -*- coding: utf-8 -*-
"""
social_publish.py — Do `plano_social` do grafo para a fila de publicação.

Este é o último elo do funil. Até aqui o nó social produzia um `PlanoSocial`
completo que a tela mostrava com capricho e ninguém publicava: o plano vivia no
checkpoint do grafo, e o `publisher-scheduled` lê `social_queue`. Duas coleções
que nunca se falaram.

O que este módulo faz:

  1. `montar_itens()` — puro: plano + contexto → lista de documentos de fila.
     Sem Firestore, sem Playwright, sem rede. É onde mora a regra (mapeamento
     de canal, agenda, quais peças precisam de imagem) e é o que os testes
     exercitam.
  2. `enfileirar()` — o I/O: renderiza os PNGs que faltam, sobe para o GCS e
     grava os documentos.

O shape do documento é o MESMO que `/api/csm/pipeline-submit` grava — não é
coincidência nem duplicação preguiçosa: é o contrato que o `publisher_job` já
consome, incluindo `article_url`, que é como `[LINK_ARTIGO]` vira link de
verdade na hora de publicar.

Uma peça por documento, com uma exceção deliberada: cada FRAME de story vira
um documento próprio. O Instagram publica story como imagem única
(`_ig_story` usa `asset_urls[0]`), e uma sequência de 4 frames é literalmente
4 uploads consecutivos. Enfileirar os 4 num documento só publicaria o primeiro
e descartaria o resto em silêncio.
"""

from __future__ import annotations

import html as html_escape
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger("cmo_agent.social_publish")

# ── Paleta da marca ───────────────────────────────────────────────────────────
# A mesma de slide_designer_agent, thumbnail_agent e
# agents/pipeline/shared/social_images.py. Se mudar lá, mude aqui.
BG          = "#0d0f14"
BG_ALT      = "#151920"
TEXT        = "#eae4dc"
TEXT_SOFT   = "#8a8378"
ACCENT      = "#e8873a"

CAROUSEL_SIZE = (1080, 1080)
STORY_SIZE    = (1080, 1920)

_FONT_STACK = "'Space Grotesk','Helvetica Neue',Arial,sans-serif"

# Horários de publicação (hora local BRT), espelhando PUBLISH_SLOTS_BRT em
# apps/web/src/lib/contentPlanner.ts.
SLOTS_BRT = (9, 12, 18)
BRT_OFFSET_HOURS = 3

# Frames de um mesmo story saem em sequência, não no mesmo instante: o
# publisher roda de hora em hora, mas o intervalo mantém a ordem legível caso
# duas execuções peguem o mesmo lote.
MINUTOS_ENTRE_FRAMES = 3


# ── Templates de imagem ───────────────────────────────────────────────────────

def _shell(body: str, width: int, height: int, padding: int = 90) -> str:
    """Casca comum: sem JS e sem fonte externa — requisito do renderer."""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{width}px;height:{height}px;background:{BG};color:{TEXT};
font-family:{_FONT_STACK};padding:{padding}px;display:flex;flex-direction:column;
justify-content:center;overflow:hidden}}
.accent{{color:{ACCENT}}}
.soft{{color:{TEXT_SOFT}}}
</style></head><body>{body}</body></html>"""


def carrossel_slide_html(titulo: str, corpo: str, numero: int, total: int, serie: str = "") -> str:
    """
    Um slide de carrossel (1080x1080).

    O contador e a barra existem porque carrossel sem indicação de posição
    perde swipe: o leitor não sabe que há mais adiante.
    """
    t = html_escape.escape(titulo or "")
    c = "<br>".join(
        html_escape.escape(linha) for linha in (corpo or "").split("\n") if linha.strip()
    )
    pct = int(numero / max(total, 1) * 100)
    tag = html_escape.escape(serie.replace("-", " ")) if serie else ""

    return _shell(f"""
<div style="display:flex;flex-direction:column;height:100%;justify-content:space-between">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <span class="soft" style="font-size:26px;letter-spacing:.16em;text-transform:uppercase">{tag}</span>
    <span class="accent" style="font-size:30px;font-weight:700">{numero}/{total}</span>
  </div>
  <div>
    <h1 class="accent" style="font-size:{68 if len(t) < 46 else 54}px;line-height:1.15;font-weight:700;margin-bottom:36px">{t}</h1>
    <p style="font-size:{38 if len(c) < 260 else 32}px;line-height:1.5;color:{TEXT}">{c}</p>
  </div>
  <div style="height:8px;background:{BG_ALT};border-radius:4px">
    <div style="height:100%;width:{pct}%;background:{ACCENT};border-radius:4px"></div>
  </div>
</div>""", *CAROUSEL_SIZE)


def story_frame_html(texto: str, ordem: int, total: int, enquete: Optional[str] = None) -> str:
    """
    Um frame de story (1080x1920).

    `enquete` é uma PERGUNTA (ver FrameStory em social_schemas.py), não uma
    lista de opções. Ela entra como dica visual, não como sticker: o sticker
    real só pode ser adicionado à mão no app do Instagram, então a imagem
    precisa fazer sentido sozinha caso ninguém o adicione.

    `ilustracao` do schema não é usada aqui: o frame sai tipográfico, no
    template da marca. Gerar a imagem descrita exigiria um modelo de imagem,
    que não existe em nenhum ponto da pipeline hoje.
    """
    t = html_escape.escape(texto or "")
    q = html_escape.escape((enquete or "").strip())
    bloco = (
        f'<div style="margin-top:50px;background:{BG_ALT};border:2px solid {ACCENT};'
        f'border-radius:18px;padding:34px;font-size:36px;line-height:1.3;color:{TEXT}">'
        f"{q}</div>"
    ) if q else ""

    # 1920px de altura: sem distribuir os blocos o conteúdo empilha no topo e
    # sobra meia tela vazia.
    return _shell(f"""
<div style="display:flex;flex-direction:column;height:100%;justify-content:space-between">
  <div style="display:flex;gap:8px">
    {"".join(
        f'<div style="flex:1;height:6px;border-radius:3px;background:{ACCENT if i < ordem else BG_ALT}"></div>'
        for i in range(total)
    )}
  </div>
  <div style="flex:1;display:flex;flex-direction:column;justify-content:center;padding:40px 0">
    <p style="font-size:{56 if len(t) < 150 else 46}px;line-height:1.35;font-weight:600">{t}</p>
    {bloco}
  </div>
  <div class="soft"><span style="font-size:28px">eozore.com</span></div>
</div>""", *STORY_SIZE, padding=100)


# ── Agenda ────────────────────────────────────────────────────────────────────

def _quando(base: datetime, dia_offset: int, indice_no_dia: int, minutos_extra: int = 0) -> str:
    """
    Instante de publicação em ISO 8601 UTC.

    `dia_offset` vem do modelo, que distribui a semana. O piso é D+1, não D+0:
    o vídeo é a âncora e sai primeiro, e toda peça social aponta para ele —
    publicar antes do vídeo existir é mandar gente para um link vazio.
    """
    dia  = max(1, int(dia_offset or 0))
    hora = SLOTS_BRT[indice_no_dia % len(SLOTS_BRT)]
    d = base + timedelta(days=dia)
    return (
        d.replace(hour=0, minute=0, second=0, microsecond=0)
        + timedelta(hours=hora + BRT_OFFSET_HOURS, minutes=minutos_extra)
    ).isoformat()


# ── Montagem dos itens ────────────────────────────────────────────────────────

def montar_copy(
    gancho: str | None,
    corpo: str | None,
    cta: dict | None = None,
    hashtags: list[str] | None = None,
) -> str:
    """
    Junta as partes de uma peça sem repetir o gancho e SEM perder o CTA.

    Dois defeitos que as 51 peças de 27/08 carregaram:

    1. **O CTA sumia.** O agente escolhe o tipo por peça, o schema valida a
       mistura no plano — e o `cta.texto` nunca entrava na copy. 48 das 51
       peças foram publicadas sem pedir nada a ninguém.
    2. **O gancho aparecia duas vezes.** O modelo devolve `corpo` já começando
       pelo gancho, e o código o prefixava de novo. O post do LinkedIn abria
       repetindo a mesma frase.
    """
    partes: list[str] = []
    g = (gancho or "").strip()
    c = (corpo or "").strip()

    if g:
        partes.append(g)
    if c:
        # Só prefixa o gancho quando o corpo não começa por ele.
        inicio = c[: len(g)].strip().lower() if g else ""
        if g and inicio == g.lower():
            partes = [c]
        else:
            partes.append(c)

    texto_cta = ((cta or {}).get("texto") or "").strip()
    if texto_cta and texto_cta.lower() not in " ".join(partes).lower():
        partes.append(texto_cta)

    tags = " ".join(f"#{t.lstrip('#')}" for t in (hashtags or []))
    if tags:
        partes.append(tags)

    return "\n\n".join(partes)


def _doc(**campos: Any) -> dict:
    """Documento de fila com os campos que o publisher_job sempre lê."""
    agora = datetime.now(timezone.utc).isoformat()
    base = {
        "status":           "planned",
        "thread_posts":     None,
        "image_url":        None,
        "video_url":        None,
        "asset_urls":       [],
        "comentario_fixado": None,
        "retry_count":      0,
        "error_message":    None,
        "published_at":     None,
        "platform_post_id": None,
        "created_at":       agora,
        "updated_at":       agora,
    }
    base.update(campos)
    return base


def montar_itens(
    plano: dict,
    *,
    artigo_slug: str = "",
    artigo_titulo: str = "",
    artigo_url: str = "",
    idioma: str = "pt-BR",
    serie: str = "",
    session_id: str = "",
    base: Optional[datetime] = None,
) -> list[dict]:
    """
    `PlanoSocial` (já como dict) → documentos de `social_queue`.

    Função pura: o campo `_render` diz QUE imagem cada item precisa, e quem
    resolve isso é `enfileirar()`. Separar assim é o que permite testar o
    mapeamento de canal e a agenda sem subir Chromium.
    """
    base = base or datetime.now(timezone.utc)
    comum = {
        "article_slug":  artigo_slug,
        "article_title": artigo_titulo,
        "article_url":   artigo_url,
        "language":      idioma,
        "session_id":    session_id or None,
    }
    itens: list[dict] = []
    # Contador por dia, para espalhar as peças do mesmo dia pelos slots de
    # horário em vez de empilhar todas às 9h.
    ocupacao: dict[int, int] = {}

    def slot(dia_offset: int) -> int:
        dia = max(1, int(dia_offset or 0))
        i = ocupacao.get(dia, 0)
        ocupacao[dia] = i + 1
        return i

    # ── LinkedIn ──────────────────────────────────────────────────────────────
    for p in plano.get("linkedin") or []:
        itens.append(_doc(
            platform="linkedin", format="text",
            title=(p.get("gancho") or "")[:120],
            copy=montar_copy(p.get("gancho"), p.get("corpo"), p.get("cta"), p.get("hashtags")),
            # O link fora do corpo é o que preserva o alcance no LinkedIn; o
            # publisher posta isto como primeiro comentário.
            comentario_fixado=p.get("comentario_fixado") or None,
            scheduled_at=_quando(base, p.get("dia_offset", 1), slot(p.get("dia_offset", 1))),
            **comum,
        ))

    # ── Threads ───────────────────────────────────────────────────────────────
    for t in plano.get("threads") or []:
        itens.append(_doc(
            platform="threads", format="thread",
            title=(t.get("gancho") or "")[:120],
            copy=t.get("gancho") or "",
            # O gancho é o post RAIZ; `posts` são as respostas encadeadas. O
            # publisher espera a thread inteira, raiz inclusa, nesta lista.
            # O CTA fecha a sequência: pedir no meio de uma thread interrompe
            # a leitura, e no fim é onde quem chegou até ali está disposto.
            thread_posts=[
                x for x in [
                    t.get("gancho") or "",
                    *(t.get("posts") or []),
                    ((t.get("cta") or {}).get("texto") or "").strip() or None,
                ] if x
            ],
            scheduled_at=_quando(base, t.get("dia_offset", 1), slot(t.get("dia_offset", 1))),
            **comum,
        ))

    # ── Carrossel ─────────────────────────────────────────────────────────────
    for c in plano.get("carrossel") or []:
        slides = sorted(c.get("slides") or [], key=lambda s: s.get("numero", 0))
        if not slides:
            continue
        itens.append(_doc(
            platform="instagram", format="carousel",
            title=(c.get("gancho") or "")[:120],
            copy=montar_copy(None, c.get("legenda"), c.get("cta"), c.get("hashtags")),
            scheduled_at=_quando(base, c.get("dia_offset", 1), slot(c.get("dia_offset", 1))),
            _render=[
                {
                    "html":  carrossel_slide_html(
                        s.get("titulo", ""), s.get("corpo", ""),
                        i + 1, len(slides), serie,
                    ),
                    "size":  CAROUSEL_SIZE,
                    "nome":  f"carrossel_{c.get('id', 'ca')}_{i + 1}",
                }
                for i, s in enumerate(slides)
            ],
            **comum,
        ))

    # ── Stories: um documento por FRAME ───────────────────────────────────────
    for s in plano.get("stories") or []:
        frames = sorted(s.get("frames") or [], key=lambda f: f.get("ordem", 0))
        if not frames:
            continue
        indice = slot(s.get("dia_offset", 1))
        cta_story = ((s.get("cta") or {}).get("texto") or "").strip()
        for i, f in enumerate(frames):
            ultimo = i == len(frames) - 1
            texto = f.get("texto") or ""
            # O CTA fecha a sequência, no ÚLTIMO frame. Repeti-lo em cada
            # frame gastaria o pedido antes de a pessoa ter recebido algo, e
            # story é sequência: quem chega ao fim é quem está disposto.
            copy_frame = (
                f"{texto}\n\n{cta_story}".strip()
                if ultimo and cta_story and cta_story.lower() not in texto.lower()
                else texto
            )
            itens.append(_doc(
                platform="instagram", format="story",
                title=f"{(s.get('gancho') or 'Story')[:100]} · {i + 1}/{len(frames)}",
                copy=copy_frame,
                scheduled_at=_quando(
                    base, s.get("dia_offset", 1), indice,
                    minutos_extra=i * MINUTOS_ENTRE_FRAMES,
                ),
                _render=[{
                    "html": story_frame_html(
                        copy_frame, i + 1, len(frames), f.get("enquete"),
                    ),
                    "size": STORY_SIZE,
                    "nome": f"story_{s.get('id', 'st')}_{i + 1}",
                }],
                **comum,
            ))

    # ── Comunidade do YouTube ─────────────────────────────────────────────────
    for p in plano.get("youtube_community") or []:
        corpo = p.get("texto") or ""
        opcoes = p.get("enquete_opcoes") or []
        if opcoes:
            corpo = corpo + "\n\n" + "\n".join(f"• {o}" for o in opcoes)
        itens.append(_doc(
            platform="youtube_community", format="text",
            title=(p.get("gancho") or "")[:120],
            copy=montar_copy(None, corpo, p.get("cta"), p.get("hashtags")),
            scheduled_at=_quando(base, p.get("dia_offset", 1), slot(p.get("dia_offset", 1))),
            **comum,
        ))

    return itens


# ── Enfileiramento ────────────────────────────────────────────────────────────

async def enfileirar(
    db,
    plano: dict,
    *,
    artigo_slug: str = "",
    artigo_titulo: str = "",
    artigo_url: str = "",
    idioma: str = "pt-BR",
    serie: str = "",
    session_id: str = "",
) -> dict:
    """
    Renderiza as imagens que faltam e grava tudo em `social_queue`.

    Falha de imagem NÃO derruba o lote: o item que não conseguiu render é
    reportado e os outros vão para a fila. Perder a semana inteira porque um
    slide de carrossel não renderizou seria pior do que publicar oito peças e
    refazer uma.
    """
    import db_paths

    itens = montar_itens(
        plano,
        artigo_slug=artigo_slug, artigo_titulo=artigo_titulo, artigo_url=artigo_url,
        idioma=idioma, serie=serie, session_id=session_id,
    )

    enfileirados = 0
    falhas: list[str] = []
    colecao = db.collection(db_paths.get_social_queue_path())

    for item in itens:
        render = item.pop("_render", None)
        rotulo = f"{item['platform']}/{item['format']}"

        if render:
            try:
                urls = await _renderizar(render, session_id)
                if not urls:
                    raise RuntimeError("nenhuma imagem foi gerada")
                item["asset_urls"] = urls
                item["image_url"]  = urls[0]
            except Exception as exc:
                logger.exception("[social_publish] imagem de %s falhou", rotulo)
                falhas.append(f"{rotulo}: {str(exc)[:160]}")
                continue

        try:
            colecao.add(item)
            enfileirados += 1
        except Exception as exc:
            logger.exception("[social_publish] gravação de %s falhou", rotulo)
            falhas.append(f"{rotulo}: {str(exc)[:160]}")

    return {
        "enfileirados": enfileirados,
        "total":        len(itens),
        "falhas":       falhas,
    }


async def _renderizar(pedidos: list[dict], session_id: str) -> list[str]:
    """HTML → PNG → GCS. Devolve as URLs na ordem dos pedidos."""
    import asyncio
    import os
    import tempfile

    # Import tardio de propósito: `agent` importa este módulo, e no topo isto
    # seria ciclo. Na hora da chamada o módulo já está carregado e o custo é o
    # de um lookup no cache do interpretador.
    from agent import upload_to_storage_if_cloud
    from html_image_renderer import render_html_image

    urls: list[str] = []
    for pedido in pedidos:
        largura, altura = pedido["size"]
        # `render_html_image` é síncrono e sobe um Chromium: fora da thread do
        # event loop, senão o /graph/state de outra aba fica esperando o
        # carrossel inteiro renderizar.
        png = await asyncio.to_thread(
            render_html_image, pedido["html"], largura, altura, "éozoré", "",
        )
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
            tf.write(png)
            caminho = tf.name
        try:
            url = upload_to_storage_if_cloud(caminho, f"{session_id}/social/{pedido['nome']}.png")
            if not url:
                raise RuntimeError(
                    "upload para o GCS indisponível — a publicação precisa de URL pública"
                )
            urls.append(url)
        finally:
            try:
                os.unlink(caminho)
            except OSError:
                pass
    return urls
