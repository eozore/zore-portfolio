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

# Zona segura de Story, não estética.
#
# O Instagram desenha por CIMA de qualquer conteúdo: avatar, nome, timestamp
# e a própria barra de progresso ocupam o topo; a caixa de resposta ocupa a
# base. O `padding=100` uniforme que este arquivo usava deixava a NOSSA barra
# de progresso em y≈100 — exatamente onde o Instagram desenha a dele por
# cima, escondendo a nossa e sem nenhum erro visível na imagem sozinha, só no
# app. `captions.py` já resolve o mesmo problema no Reel com margem de 16% da
# altura; aqui é o valor em pixels equivalente, com a base um pouco menor
# porque a caixa de resposta é mais rasa que a faixa de avatar+username.
STORY_SAFE_TOP    = 280
STORY_SAFE_BOTTOM = 260

_FONT_STACK = "'Space Grotesk','Helvetica Neue',Arial,sans-serif"

# Horários de publicação (hora local BRT), espelhando PUBLISH_SLOTS_BRT em
# apps/web/src/lib/contentPlanner.ts.
SLOTS_BRT = (9, 12, 18)

# Degraus extras, usados SÓ quando os três preferidos do dia já estão tomados
# naquela plataforma. Ordenados por qualidade de horário, não por relógio: é
# melhor cair às 10h do que às 21h.
SLOTS_OVERFLOW_BRT = (10, 15, 20, 8, 16, 21)

# Até onde empurrar quando um dia inteiro está lotado. Sete dias cobre uma
# campanha inteira; além disso a peça perde relação com o vídeo que ela
# promove, e é melhor aceitar a coincidência do que publicar fora de contexto.
DIAS_MAX_BUSCA = 7
BRT_OFFSET_HOURS = 3

# Frames de um mesmo story saem em sequência, não no mesmo instante: o
# publisher roda de hora em hora, mas o intervalo mantém a ordem legível caso
# duas execuções peguem o mesmo lote.
MINUTOS_ENTRE_FRAMES = 3


# ── Templates de imagem ───────────────────────────────────────────────────────

def _shell(body: str, width: int, height: int, padding: int = 90,
          padding_top: Optional[int] = None, padding_bottom: Optional[int] = None) -> str:
    """
    Casca comum: sem JS e sem fonte externa — requisito do renderer.

    `padding_top`/`padding_bottom` existem por causa do Story: lá o topo e a
    base precisam de mais respiro que os lados (ver `story_frame_html`).
    Quando ausentes, o padding fica uniforme — o comportamento de sempre para
    carrossel e qualquer chamador que não precise da assimetria.
    """
    pt = padding if padding_top is None else padding_top
    pb = padding if padding_bottom is None else padding_bottom
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{width}px;height:{height}px;background:{BG};color:{TEXT};
font-family:{_FONT_STACK};padding:{pt}px {padding}px {pb}px {padding}px;display:flex;flex-direction:column;
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


def story_frame_html(texto: str, ordem: int, total: int, enquete: Optional[str] = None,
                     cta: str = "", serie: str = "") -> str:
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

    # O CTA entra como BLOCO, não emendado no corpo.
    #
    # Concatenar com "\n\n" não separa nada: o texto vira um `<p>` só e o
    # pedido lê como continuação da frase — "…avaliações semânticas. Veja a
    # arquitetura completa no link da bio" parece uma oração, não um convite.
    # Em cor de acento e em linha própria, ele se lê como o que é.
    c = html_escape.escape((cta or "").strip())
    bloco_cta = (
        f'<p style="margin-top:44px;font-size:40px;line-height:1.3;'
        f'font-weight:700;color:{ACCENT}">{c}</p>'
    ) if c else ""

    # SEM barra de progresso própria.
    #
    # O Instagram desenha a dele no topo de toda sequência de story. A nossa
    # ficava logo abaixo, duplicando a informação e ocupando a área mais
    # nobre do quadro — duas barras dizendo a mesma coisa. Quem indica
    # posição na sequência é o app; a imagem cuida do conteúdo.
    #
    # O grid de fundo é o mesmo dos slides do vídeo (slide_designer_agent).
    # Antes a story era um preto chapado, visualmente à parte do resto da
    # marca; com a textura ela pertence ao mesmo sistema.
    # O destino vai na IMAGEM, não só na legenda.
    #
    # O Instagram não transforma URL em link, então uma story sem destino
    # escrito não aponta para lugar nenhum. As de 31/08 mostravam
    # "eozore.com" no rodapé — o site, não o vídeo —, e ninguém ficou sabendo
    # que havia vídeo no canal. No último frame o selo ganha a cor de acento,
    # porque é ali que o pedido acontece.
    from destino import marca_de_destino
    ultimo = ordem >= total
    selo = html_escape.escape(marca_de_destino("instagram") if ultimo else "eozore.com")

    grid = (
        f"background-image:"
        f"linear-gradient(rgba(232,135,58,.045) 1px, transparent 1px),"
        f"linear-gradient(90deg, rgba(232,135,58,.045) 1px, transparent 1px);"
        f"background-size:44px 44px;"
    )
    serie_tag = html_escape.escape((serie or "").replace("-", " ").upper()) if serie else ""

    return _shell(f"""
<div style="{grid}position:absolute;inset:0"></div>
<div style="position:relative;display:flex;flex-direction:column;height:100%">
  <!-- Topo deliberadamente vazio: é onde o Instagram desenha avatar, nome,
       timestamp e a barra de progresso dele. Competir por esse espaço é
       colocar conteúdo debaixo da interface do app. -->
  <div style="flex:1"></div>
  <div style="padding-bottom:110px">
    {f'<div style="font-family:monospace;font-size:25px;letter-spacing:.2em;color:{TEXT_SOFT}">{serie_tag}</div>' if serie_tag else ''}
    <div style="width:88px;height:5px;background:{ACCENT};margin:20px 0 34px"></div>
    <p style="font-size:{68 if len(t) < 120 else (58 if len(t) < 200 else 48)}px;line-height:1.24;font-weight:700;letter-spacing:-.015em">{t}</p>
    {bloco_cta}
    {bloco}
  </div>
  <div style="display:flex;justify-content:space-between;align-items:baseline">
    <span style="font-size:27px;font-weight:600;letter-spacing:.02em;color:{ACCENT if ultimo else TEXT_SOFT}">{selo}</span>
    <span style="font-family:monospace;font-size:24px;color:{TEXT_SOFT}">{ordem}/{total}</span>
  </div>
</div>""", *STORY_SIZE, padding=100, padding_top=STORY_SAFE_TOP, padding_bottom=STORY_SAFE_BOTTOM)


# ── Agenda ────────────────────────────────────────────────────────────────────

def _quando(base: datetime, dia: int, hora_brt: int, minutos_extra: int = 0) -> str:
    """
    Instante de publicação em ISO 8601 UTC.

    `dia` vem do modelo, que distribui a semana. O piso é D+1, não D+0: o
    vídeo é a âncora e sai primeiro, e toda peça social aponta para ele —
    publicar antes do vídeo existir é mandar gente para um link vazio.
    """
    d = base + timedelta(days=max(1, int(dia or 0)))
    return (
        d.replace(hour=0, minute=0, second=0, microsecond=0)
        + timedelta(hours=hora_brt + BRT_OFFSET_HOURS, minutes=minutos_extra)
    ).isoformat()


def _chave_agenda(platform: str, quando_iso: str) -> tuple[str, str]:
    """
    Identidade de um horário ocupado: plataforma + hora cheia.

    A granularidade é a HORA, não o minuto, porque os frames de uma story
    saem de 3 em 3 minutos (`MINUTOS_ENTRE_FRAMES`) e são uma peça só. Chavear
    por minuto trataria cada frame como uma peça distinta e espalharia a
    sequência por horas diferentes, que é o oposto do que uma story é.
    """
    return (platform, quando_iso[:13])


def _reservar(
    agenda: set[tuple[str, str]],
    platform: str,
    base: datetime,
    dia_offset: int,
) -> tuple[int, int]:
    """
    Primeiro (dia, hora) livre para esta plataforma, a partir de `dia_offset`.

    Existe porque o agendamento era cego para o que já estava na fila: `base`
    é sempre "agora", então uma campanha nova começava em D+1 e caía por cima
    da anterior, que ainda tinha peças pendentes. Nada quebrava — o publisher
    publica tudo que está no horário — mas dois vídeos diferentes disputavam
    a mesma janela, com CTAs apontando para links diferentes.

    Reserva ao devolver: o mesmo conjunto acumula o que já estava na fila E o
    que esta montagem acabou de marcar, então as peças da campanha nova também
    não colidem entre si.
    """
    dia = max(1, int(dia_offset or 0))
    for d in range(dia, dia + DIAS_MAX_BUSCA):
        for hora in SLOTS_BRT + SLOTS_OVERFLOW_BRT:
            chave = _chave_agenda(platform, _quando(base, d, hora))
            if chave not in agenda:
                agenda.add(chave)
                return d, hora

    # Uma semana inteira lotada nesta plataforma. Aceita a coincidência em vez
    # de empurrar a peça para longe do vídeo que ela promove.
    logger.warning(
        "[social_publish] agenda de %s lotada a partir de D+%d; aceitando coincidência",
        platform, dia,
    )
    return dia, SLOTS_BRT[0]


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
    agenda_ocupada: Optional[set[tuple[str, str]]] = None,
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
    # Horários já tomados: o que veio da fila (campanhas anteriores ainda
    # pendentes) mais o que esta montagem for marcando. Um conjunto só para as
    # duas coisas — a colisão entre campanhas e a colisão interna são o mesmo
    # problema.
    agenda: set[tuple[str, str]] = set(agenda_ocupada or ())

    def quando(platform: str, dia_offset: int, minutos_extra: int = 0) -> str:
        dia, hora = _reservar(agenda, platform, base, dia_offset)
        return _quando(base, dia, hora, minutos_extra)

    # ── LinkedIn ──────────────────────────────────────────────────────────────
    for p in plano.get("linkedin") or []:
        itens.append(_doc(
            platform="linkedin", format="text",
            title=(p.get("gancho") or "")[:120],
            copy=montar_copy(p.get("gancho"), p.get("corpo"), p.get("cta"), p.get("hashtags")),
            # O link fora do corpo é o que preserva o alcance no LinkedIn; o
            # publisher posta isto como primeiro comentário.
            comentario_fixado=p.get("comentario_fixado") or None,
            scheduled_at=quando("linkedin", p.get("dia_offset", 1)),
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
            scheduled_at=quando("threads", t.get("dia_offset", 1)),
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
            scheduled_at=quando("instagram", c.get("dia_offset", 1)),
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
        # Reserva UMA vez para a sequência inteira: os frames dividem a mesma
        # hora, separados por minutos. Reservar por frame espalharia a story
        # por horas diferentes.
        dia_story, hora_story = _reservar(agenda, "instagram", base, s.get("dia_offset", 1))
        cta_story = ((s.get("cta") or {}).get("texto") or "").strip()
        for i, f in enumerate(frames):
            ultimo = i == len(frames) - 1
            texto = f.get("texto") or ""
            # O CTA fecha a sequência, no ÚLTIMO frame. Repeti-lo em cada
            # frame gastaria o pedido antes de a pessoa ter recebido algo, e
            # story é sequência: quem chega ao fim é quem está disposto.
            cta_frame = (
                cta_story
                if ultimo and cta_story and cta_story.lower() not in texto.lower()
                else ""
            )
            copy_frame = f"{texto}\n\n{cta_frame}".strip() if cta_frame else texto
            itens.append(_doc(
                platform="instagram", format="story",
                title=f"{(s.get('gancho') or 'Story')[:100]} · {i + 1}/{len(frames)}",
                copy=copy_frame,
                scheduled_at=_quando(
                    base, dia_story, hora_story,
                    minutos_extra=i * MINUTOS_ENTRE_FRAMES,
                ),
                _render=[{
                    "html": story_frame_html(
                        texto, i + 1, len(frames), f.get("enquete"), cta_frame,
                        serie=serie,
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
            scheduled_at=quando("youtube_community", p.get("dia_offset", 1)),
            **comum,
        ))

    return itens


# ── Enfileiramento ────────────────────────────────────────────────────────────

def agenda_ocupada(db) -> set[tuple[str, str]]:
    """
    Horários já reservados pelas peças que ainda não publicaram.

    Lê `social_queue` inteira em vez de filtrar por sessão: o conflito que
    importa é com QUALQUER campanha pendente, não só com a atual. Peça já
    publicada não ocupa nada — o horário dela passou.

    Falha ABERTO de propósito: sem esta leitura o agendamento volta a ser o
    de antes (pode coincidir), o que é bem melhor do que recusar a enfileirar
    uma semana de conteúdo por causa de uma consulta que não respondeu.
    """
    import db_paths

    ocupada: set[tuple[str, str]] = set()
    try:
        col = db.collection(db_paths.get_social_queue_path())
        for doc in col.where("status", "==", "planned").stream():
            d = doc.to_dict() or {}
            plataforma = d.get("platform") or ""
            quando_iso = d.get("scheduled_at") or ""
            if plataforma and quando_iso:
                ocupada.add(_chave_agenda(plataforma, quando_iso))
    except Exception:
        logger.exception(
            "[social_publish] não consegui ler a agenda atual; "
            "as peças novas podem coincidir com as pendentes"
        )
        return set()

    logger.info("[social_publish] %d horários já ocupados na fila", len(ocupada))
    return ocupada


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
        agenda_ocupada=agenda_ocupada(db),
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
