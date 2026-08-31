# -*- coding: utf-8 -*-
"""
publisher_job/job.py
=====================
Dispatcher central de publicação omnicanal do éozoré.

Fluxo:
  1. Lê itens da coleção Firestore `publish_queue` com status == 'pending'
     e scheduled_at <= agora (ou execução imediata via VideoReadyMsg).
  2. Despacha para o cliente correto por plataforma.
  3. Atualiza status no Firestore (published / failed) com post_id ou erro.
  4. Para vídeos (YouTube/Shorts/Reels): faz download do GCS e upload direto.
  5. Para Instagram Reel/Story com URL GCS privada: gera Signed URL automática.

Plataformas suportadas:
  linkedin          → LinkedInClient  (perfil pessoal Victor Zoré)
  youtube           → YouTubeClient   (upload vídeo longo)
  youtube_shorts    → YouTubeClient   (upload Short)
  youtube_community → YouTubeClient   (community post — pending_manual)
  instagram         → MetaClient      (foto, reel, story, carousel)
  facebook          → MetaClient      (foto, texto)
  threads           → MetaClient      (texto, série encadeada)
"""

import datetime as dt
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

from google.cloud import firestore, secretmanager

from shared.models import VideoReadyMsg

logger = logging.getLogger("publisher_job")

COLLECTION_QUEUE = "social_queue"   # fila de publicação agendada (status = planned)

# ── Placeholders de link ──────────────────────────────────────────────────────
# Os prompts de copy_agent e distribution_agent instruem os modelos a emitir
# estes marcadores em vez de URLs reais ("NUNCA repita URLs reais"). A etapa de
# substituição, porém, nunca existiu: 9 ocorrências de [LINK_ARTIGO] saíam
# LITERALMENTE nos posts de Threads e no carrossel.
#
# A substituição acontece na PUBLICAÇÃO, não na geração, porque é só aí que a
# URL do vídeo existe: o contentPlanner agenda o social para D+1..D+7 e o vídeo
# sai em D+0, então quando o publisher pega um item da fila o vídeo já subiu.
ARTICLE_PLACEHOLDER = "[LINK_ARTIGO]"
CHANNEL_PLACEHOLDER = "[LINK_CANAL]"

BLOG_BASE_URL       = os.environ.get("BLOG_BASE_URL", "https://eozore.com").rstrip("/")
# Fallback quando o vídeo específico ainda não existe (upload falhou, ou o item
# foi publicado antes do vídeo): o canal é sempre um link válido. Publicar um
# link quebrado é pior do que publicar um link mais genérico.
YOUTUBE_CHANNEL_URL = os.environ.get(
    "YOUTUBE_CHANNEL_URL", "https://www.youtube.com/@victorzore"
).rstrip("/")


def _article_url_from(data: dict[str, Any]) -> str:
    """URL do artigo a partir do item da fila, com degradação graciosa."""
    direct = data.get("article_url") or data.get("articleUrl")
    if direct:
        return str(direct)
    slug = data.get("article_slug") or data.get("articleSlug")
    lang = data.get("language") or "pt-BR"
    return f"{BLOG_BASE_URL}/{lang}/blog/{slug}" if slug else f"{BLOG_BASE_URL}/pt-BR/blog"

# Visibilidade do upload no YouTube: 'public' | 'unlisted' | 'private'.
#
# Default 'private': o vídeo sobe fechado, o dono do canal assiste no Studio e
# só ele decide quando abrir. É o passo 6 do fluxo — tornar público é uma ação
# manual, e é ela que libera a geração do pacote de conteúdos derivados.
#
# A assimetria de risco manda aqui: um vídeo privado por engano custa um
# clique; um vídeo público por engano já foi visto, indexado e notificado aos
# inscritos. 'private' em vez de 'unlisted' porque um link não listado ainda
# circula se vazar, e a peça só existe para revisão até ser aprovada.
YOUTUBE_UPLOAD_PRIVACY = os.environ.get("YOUTUBE_UPLOAD_PRIVACY", "private").strip().lower()
if YOUTUBE_UPLOAD_PRIVACY not in ("public", "unlisted", "private"):
    logger.warning(
        "YOUTUBE_UPLOAD_PRIVACY=%r inválido, usando 'public'.", YOUTUBE_UPLOAD_PRIVACY
    )
    YOUTUBE_UPLOAD_PRIVACY = "public"
# Hashtags por série, espelhando `agents/cmo_agent/destino.py`. Duplicado de
# propósito: a pipeline não importa do cmo_agent (imagens separadas), e uma
# tag errada num post é menos grave do que um import que quebra o publisher.
HASHTAGS_POR_SERIE: dict[str, str] = {
    "engenharia-de-ia":              "#engenhariadeia #llm #mlops #devbr",
    "engenharia-de-software-com-ia": "#engenhariadeia #vibecoding #devbr #ia",
    "ia-para-lideres":               "#iaparalideres #lideranca #tecnologia",
    "estatistica":                   "#estatistica #datascience #analisededados",
    "ml":                            "#machinelearning #mlops #datascience",
}
HASHTAGS_PADRAO = "#engenhariadeia #ia #devbr"


def _hashtags_da_serie(serie: object) -> str:
    return HASHTAGS_POR_SERIE.get(str(serie or "").strip().lower(), HASHTAGS_PADRAO)


MAX_RETRIES      = 3

# Vazão por rodada. O agendador roda de hora em hora, então este é o teto de
# quantas peças saem de uma vez — não de quantas o job ENXERGA, que era o
# defeito anterior.
MAX_PUBLICACOES_POR_RODADA = 25
PAGINA_FILA       = 100
MAX_FILA_VARRIDA  = 1000
ERROR_CODE_MAP   = {
    "token":       "TOKEN_EXPIRED",
    "401":         "UNAUTHORIZED",
    "403":         "UNAUTHORIZED",
    "rate":        "RATE_LIMIT",
    "429":         "RATE_LIMIT",
    "quota":       "QUOTA_EXCEEDED",
    "network":     "NETWORK_ERROR",
    "timeout":     "NETWORK_ERROR",
    "duplicate":   "DUPLICATE_CONTENT",
}


def _summarize(text: str, limit: int) -> str:
    """
    Encurta em fronteira de frase, não no meio de uma palavra.

    O corte anterior era `description[:300] + "..."` — cego. Os posts saíam
    truncados no meio da frase, às vezes no meio de um termo técnico, e o
    "..." final virava parte do texto publicado.
    """
    text = (text or "").strip()
    if len(text) <= limit:
        return text

    window = text[: limit + 1]
    for mark in (". ", "! ", "? ", ".\n", "\n\n"):
        cut = window.rfind(mark)
        if cut > limit * 0.5:
            return text[: cut + 1].strip()

    space = window.rfind(" ")
    return (text[:space] if space > 0 else text[:limit]).rstrip(",;:-") + "…"


def _classify_error(msg: str) -> str:
    lower = msg.lower()
    for keyword, code in ERROR_CODE_MAP.items():
        if keyword in lower:
            return code
    return "UNKNOWN_ERROR"


def _gcs_to_signed_url(gcs_url: str, expiration_minutes: int = 60) -> str:
    """
    Converte uma URL gs:// ou https://storage.googleapis.com/ em Signed URL
    válida por `expiration_minutes` minutos.

    Necessário para Instagram/Facebook que precisam baixar o vídeo diretamente.
    O bucket do pipeline usa uniform bucket-level access (sem ACLs por objeto),
    então objetos privados precisam de Signed URL para acesso externo.

    No Cloud Run, usa as credenciais da service account pipeline-jobs-sa
    via google.auth. Localmente usa ADC.
    """
    import re
    from google.cloud import storage
    import google.auth

    # Extrai bucket e blob de qualquer formato de URL GCS
    if gcs_url.startswith("gs://"):
        parts = gcs_url[5:].split("/", 1)
        bucket_name, blob_name = parts[0], parts[1] if len(parts) > 1 else ""
    elif "storage.googleapis.com/" in gcs_url:
        m = re.match(r"https://storage\.googleapis\.com/([^/]+)/(.+)", gcs_url)
        if not m:
            return gcs_url  # não é GCS — retorna como está
        bucket_name, blob_name = m.group(1), m.group(2)
    else:
        return gcs_url  # URL externa — retorna como está

    try:
        # cloud-platform, não só devstorage.read_only: o passo abaixo assina a
        # URL chamando a API remota do IAM (signBlob), que exige escopo IAM no
        # token — devstorage.read_only só cobre LER o bucket, não assinar.
        # Erro real visto em produção: "ACCESS_TOKEN_SCOPE_INSUFFICIENT" ao
        # chamar iamcredentials.googleapis.com, que derrubava a assinatura,
        # caía no fallback de gs:// cru, e quebrava Instagram (não consegue
        # buscar gs://) e a thumbnail customizada do YouTube (mesmo motivo).
        credentials, project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        # Força renovação para ter token fresco
        from google.auth.transport.requests import Request as GoogleAuthRequest
        credentials.refresh(GoogleAuthRequest())

        client = storage.Client(credentials=credentials)
        bucket = client.bucket(bucket_name)
        blob   = bucket.blob(blob_name)

        # blob.generate_signed_url() sem service_account_email/access_token
        # tenta assinar LOCALMENTE, o que exige uma chave privada de arquivo
        # JSON — a identidade anexada do Cloud Run (Compute Engine credentials)
        # nunca tem uma. Isso derrubava toda publicação no Instagram/Facebook:
        # caía no except, devolvia a gs:// URL original, e o Meta não consegue
        # buscar um objeto de bucket privado. Passando service_account_email +
        # access_token, a assinatura acontece via API remota do IAM
        # (signBlob) em vez de local — funciona com identidade anexada, desde
        # que a SA tenha roles/iam.serviceAccountTokenCreator sobre si mesma.
        signed_url = blob.generate_signed_url(
            expiration=dt.timedelta(minutes=expiration_minutes),
            method="GET",
            version="v4",
            service_account_email=credentials.service_account_email,
            access_token=credentials.token,
        )
        logger.debug(f"Signed URL gerada para {blob_name} ({expiration_minutes}min)")
        return signed_url
    except Exception as e:
        logger.warning(f"Signed URL generation failed for {gcs_url}: {e} — usando URL original")
        return gcs_url


def _is_gcs_url(url: str) -> bool:
    """Retorna True se a URL aponta para Google Cloud Storage."""
    return url.startswith("gs://") or "storage.googleapis.com" in url


def _prepare_media_url(url: str | None) -> str | None:
    """
    Prepara URL de mídia para publicação externa.
    Se for GCS privado, gera Signed URL. Caso contrário, retorna como está.
    """
    if not url:
        return url
    if _is_gcs_url(url):
        return _gcs_to_signed_url(url)
    return url


def _get_secret(project_id: str, secret_id: str) -> str:
    """Lê secret do Secret Manager. Em ambiente local usa gcloud CLI como fallback."""
    # Tenta Secret Manager via SDK primeiro (funciona no Cloud Run)
    try:
        client = secretmanager.SecretManagerServiceClient()
        name   = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
        resp   = client.access_secret_version(request={"name": name})
        return resp.payload.data.decode("UTF-8")
    except Exception as sdk_err:
        # Fallback para gcloud CLI em desenvolvimento local
        logger.debug(f"Secret Manager SDK falhou ({sdk_err}), tentando gcloud CLI...")
        import subprocess
        r = subprocess.run(
            ["gcloud", "secrets", "versions", "access", "latest",
             f"--secret={secret_id}", f"--project={project_id}"],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
        raise RuntimeError(
            f"Não foi possível ler o secret '{secret_id}' via SDK nem via gcloud CLI: {sdk_err}"
        )


def _get_secret_json(project_id: str, secret_id: str) -> dict:
    return json.loads(_get_secret(project_id, secret_id))


# ── Capítulos do YouTube ──────────────────────────────────────────────────────

MARCADOR_CAPITULOS = "<!--CAPITULOS-->"

# Rótulo de fallback por beat, para o segmento de avatar (que não tem slide de
# onde tirar um título) e para quando o HTML não expõe cabeçalho legível.
_ROTULO_POR_BEAT = {
    "hook":        "O problema",
    "intro":       "Do que se trata",
    "teoria":      "Como funciona",
    "codigo":      "Na prática",
    "demo":        "Demonstração",
    "comparativo": "Comparando as opções",
    "resumo":      "O que levar",
    "cta":         "Próximo passo",
    "cta_meio":    "Uma pausa",
    "cta_artigo":  "Onde aprofundar",
}


def _titulo_do_slide(manifest_html: str, slide_id: str) -> str:
    """Cabeçalho visível do slide, extraído do deck já montado."""
    import re as _re

    m = _re.search(
        r'<section[^>]*id="' + _re.escape(slide_id) + r'"[\s\S]*?</section>',
        manifest_html, _re.IGNORECASE,
    )
    if not m:
        return ""
    bloco = m.group(0)

    # O slide DECLARA o próprio capítulo. Adivinhar por nome de classe é
    # frágil: o slide_designer varia a marcação a cada geração, e a lista de
    # capítulos degradava toda para o rótulo genérico do beat.
    declarado = _re.search(r'data-capitulo="([^"]{4,80})"', bloco, _re.IGNORECASE)
    if declarado:
        return _normalizar_titulo(declarado.group(1))

    # Fallback para decks gerados antes da regra existir. Só classes de TÍTULO. `badge-tag`, `badge-label` e `eyebrow` carregam o
    # rótulo da categoria ("ENGENHARIA DE IA MODERNA"), que se repete slide a
    # slide e não diz nada sobre o trecho — vira capítulo inútil.
    candidatos: list[str] = []
    for classe in ("main-title", "slide-title", "titulo"):
        achado = _re.search(
            r'class="[^"]*\b' + classe + r'\b[^"]*"[^>]*>([^<]{4,80})<', bloco, _re.IGNORECASE
        )
        if achado:
            candidatos.append(achado.group(1))
    for achado in _re.finditer(r"<h[12][^>]*>([^<]{4,80})<", bloco, _re.IGNORECASE):
        candidatos.append(achado.group(1))

    for bruto in candidatos:
        titulo = _normalizar_titulo(bruto)
        # Uma palavra só quase sempre é rótulo ("PROBLEMA", "SOLUÇÃO"), não
        # assunto. Capítulo precisa de frase.
        if titulo and " " in titulo:
            return titulo
    return ""


def _normalizar_titulo(bruto: str) -> str:
    """
    Limpa o texto do slide para virar capítulo.

    O `//` vem do `content` do CSS do eyebrow e às vezes aparece no HTML; e
    títulos escritos em caixa alta ficam gritando no meio de uma lista de
    capítulos em caixa normal.
    """
    import re as _re

    t = _re.sub(r"\s+", " ", bruto).strip()
    t = _re.sub(r"^[/·•\-–—\s]+", "", t).strip()
    letras = [c for c in t if c.isalpha()]
    if letras and all(c.isupper() for c in letras):
        t = t.capitalize()
    return t


def montar_capitulos(timeline: list[dict], manifest_html: str = "") -> str:
    """
    Capítulos no formato que o YouTube reconhece.

    O YouTube só cria capítulos se o PRIMEIRO for `00:00` e houver ao menos
    três — por isso a função devolve string vazia abaixo disso, em vez de uma
    lista pela metade que não vira nada e só ocupa a descrição.

    Os tempos vêm do `timeline.json`, que o video_editor grava com a duração
    MEDIDA de cada clipe. Estimar pelo manifesto daria capítulos deslocados,
    e capítulo deslocado é pior que capítulo nenhum.
    """
    if len(timeline) < 3:
        return ""

    linhas: list[str] = []
    usados: set[str] = set()
    for item in timeline:
        inicio = float(item.get("start_s") or 0)
        slide  = item.get("slide")
        titulo = _titulo_do_slide(manifest_html, slide) if slide and manifest_html else ""
        if not titulo:
            titulo = _ROTULO_POR_BEAT.get(str(item.get("beat") or "").lower(), "")
        # Sem título e sem beat conhecido, o segmento fica de fora: "Continuação"
        # não ajuda ninguém a navegar e só ocupa linha.
        if not titulo:
            continue
        # Dois segmentos seguidos com o mesmo rótulo viram um capítulo só: uma
        # lista com "Como funciona" três vezes não ajuda ninguém a navegar.
        chave = titulo.lower()
        if chave in usados:
            continue
        usados.add(chave)
        linhas.append(f"{int(inicio // 60):02d}:{int(inicio % 60):02d} — {titulo}")

    if len(linhas) < 3:
        return ""
    # O YouTube exige que o primeiro capítulo seja 00:00.
    if not linhas[0].startswith("00:00"):
        linhas[0] = "00:00 — " + linhas[0].split(" — ", 1)[-1]
    return "📌 O que você verá neste episódio:\n\n" + "\n".join(linhas)


class PublisherJob:
    """
    Dispatcher de publicação. Lê a fila do Firestore e publica em cada plataforma.

    Uso:
        job = PublisherJob(gcp_project_id="vazfy-417019")
        job.run()                          # processa fila agendada
        job.publish_video_ready(msg)       # publicação imediata pós-vídeo
        job.publish_single(item)           # publica um item específico
    """

    def __init__(self, gcp_project_id: str) -> None:
        self._project_id = gcp_project_id
        self._db         = firestore.Client(project=gcp_project_id)

        # Clientes lazy-initialized (evita carregar secrets desnecessariamente)
        self._linkedin: Any = None
        self._meta:     Any = None
        self._youtube:  Any = None

        # Uma execução da fila publica vários itens da MESMA sessão; sem cache
        # cada item faria a mesma query em content_projects.
        self._video_url_cache: dict[str, str | None] = {}

    # ── Resolução de links ────────────────────────────────────────────────────

    def _video_url_for(self, session_id: str | None, article_slug: str | None) -> str | None:
        """
        URL do vídeo publicado desta campanha, ou None se ainda não existe.

        Procura o content_project da sessão e lê o id do vídeo gravado por
        publish_video_ready em publish_results.youtube.
        """
        key = session_id or article_slug or ""
        if not key:
            return None
        if key in self._video_url_cache:
            return self._video_url_cache[key]

        video_url: str | None = None
        try:
            field, value = ("session_id", session_id) if session_id else ("article_slug", article_slug)
            docs = list(
                self._db.collection("content_projects")
                .where(field, "==", value)
                .limit(10)
                .get()
            )
            # O mais recente que já tenha vídeo publicado
            for doc in sorted(docs, key=lambda d: str(d.to_dict().get("created_at", "")), reverse=True):
                results = doc.to_dict().get("publish_results") or {}
                vid = results.get("youtube")
                if vid:
                    video_url = f"https://youtu.be/{vid}"
                    break
        except Exception as exc:
            logger.warning("[publisher] falha ao resolver URL do vídeo (%s=%s): %s",
                           "session_id" if session_id else "article_slug", key, exc)

        self._video_url_cache[key] = video_url
        return video_url

    def _resolve_placeholders(self, text: str | None, data: dict[str, Any]) -> str:
        """
        Troca [LINK_ARTIGO] e [LINK_CANAL] pelas URLs reais.

        Sem isto o texto ia LITERAL para a rede social. O fallback do canal
        garante que nunca publicamos um link quebrado, mesmo se o upload do
        vídeo tiver falhado.
        """
        if not text:
            return text or ""
        if ARTICLE_PLACEHOLDER not in text and CHANNEL_PLACEHOLDER not in text:
            return text

        resolved = text.replace(ARTICLE_PLACEHOLDER, _article_url_from(data))
        if CHANNEL_PLACEHOLDER in resolved:
            video_url = self._video_url_for(
                data.get("session_id") or data.get("sessionId"),
                data.get("article_slug") or data.get("articleSlug"),
            )
            resolved = resolved.replace(CHANNEL_PLACEHOLDER, video_url or YOUTUBE_CHANNEL_URL)
        return resolved

    # ── Artigo ────────────────────────────────────────────────────────────────

    MARCA_VIDEO = "<!--VIDEO-DO-ARTIGO-->"

    def _anexar_video_ao_artigo(self, article_slug: str | None, video_url: str) -> None:
        """
        Acrescenta o vídeo ao fim do artigo, depois que ele existe.

        A ordem do ciclo é artigo primeiro, vídeo depois — às vezes dias
        depois. Quando o artigo é publicado o vídeo ainda não existe, então
        não há link para pôr; e nada voltava para pôr depois. O leitor do
        artigo nunca descobria que havia um vídeo do mesmo assunto.

        Idempotente pelo marcador HTML: republicar não empilha seções.
        Best-effort — o artigo já está no ar e vale por si, e falhar aqui não
        pode derrubar a publicação do vídeo.
        """
        if not article_slug or not video_url:
            return
        try:
            col = self._db.collection("articles")
            docs = list(col.where("slug", "==", article_slug).limit(1).get())
            if not docs:
                logger.info("[publisher] artigo %s não encontrado para anexar o vídeo.", article_slug)
                return
            ref = docs[0].reference
            corpo = (docs[0].to_dict() or {}).get("content") or ""
            if self.MARCA_VIDEO in corpo:
                logger.info("[publisher] artigo %s já tem o vídeo anexado.", article_slug)
                return
            bloco = (
                f"\n\n{self.MARCA_VIDEO}\n\n---\n\n"
                f"## Veja em vídeo\n\n"
                f"Se preferir assistir, gravei este mesmo assunto em vídeo — "
                f"com a demonstração rodando:\n\n{video_url}\n"
            )
            ref.update({"content": corpo + bloco})
            logger.info("[publisher] vídeo anexado ao artigo %s.", article_slug)
        except Exception as exc:                                # noqa: BLE001
            logger.warning("[publisher] falha ao anexar vídeo ao artigo: %s", exc)

    # ── Link nas peças sociais ────────────────────────────────────────────────

    def _link_da_campanha(self, data: dict[str, Any]) -> str:
        """
        O melhor link disponível NO MOMENTO da publicação, nesta ordem:
        vídeo → artigo → canal.

        A ordem existe porque o vídeo é o item mais demorado do ciclo: o plano
        social é enfileirado logo depois do gate, e o vídeo só fica pronto
        (e às vezes só é publicado à mão) horas ou dias depois. Resolver o link
        no enfileiramento congelaria `video_url: None` para sempre — foi o que
        aconteceu com as 51 peças de 27/08.
        """
        video = self._video_url_for(
            data.get("session_id") or data.get("sessionId"),
            data.get("article_slug") or data.get("articleSlug"),
        )
        return video or _article_url_from(data) or YOUTUBE_CHANNEL_URL

    @staticmethod
    def _tem_link(texto: str | None) -> bool:
        return bool(texto) and ("http://" in texto or "https://" in texto)

    def _garantir_link(self, data: dict[str, Any], platform: str) -> dict[str, Any]:
        """
        Põe o link na peça quando a plataforma sabe renderizá-lo.

        `_resolve_placeholders` só age se o marcador estiver no texto, e o
        modelo emitiu marcador em UMA das 51 peças do ciclo de 27/08 — as
        outras 50 foram para a fila sem link nenhum, nem do vídeo nem do
        artigo. Pedir o marcador ao modelo é sugestão; isto é garantia.

        O Instagram fica DE FORA de propósito: ele não renderiza link em
        legenda nem em comentário, e enfiar uma URL ali só suja o texto. Lá o
        caminho é a bio, e disso cuida a regra de copy.
        """
        link = self._link_da_campanha(data)

        if platform == "linkedin":
            # No corpo o link derruba o alcance; o lugar dele é o primeiro
            # comentário, que é o que `comentario_fixado` publica.
            atual = data.get("comentario_fixado") or data.get("firstComment")
            if not self._tem_link(atual):
                data["comentario_fixado"] = (
                    f"{atual.strip()}\n\n{link}" if isinstance(atual, str) and atual.strip()
                    else f"Vídeo completo: {link}"
                )
            return data

        if platform == "threads":
            posts = data.get("thread_posts") or data.get("threadPosts")
            if isinstance(posts, list) and posts:
                if not any(self._tem_link(p) for p in posts):
                    posts[-1] = f"{str(posts[-1]).rstrip()}\n\n{link}"
                    data["thread_posts"] = posts
            elif not self._tem_link(data.get("copy")):
                data["copy"] = f"{str(data.get('copy') or '').rstrip()}\n\n{link}"
            return data

        if platform in ("youtube_community", "facebook"):
            if not self._tem_link(data.get("copy")):
                data["copy"] = f"{str(data.get('copy') or '').rstrip()}\n\n{link}"
            return data

        return data

    # ── Clientes (lazy) ────────────────────────────────────────────────────────

    def _get_linkedin(self):
        if self._linkedin is None:
            from publisher_job.linkedin_client import LinkedInClient
            creds = _get_secret_json(self._project_id, "linkedin-tokens")
            self._linkedin = LinkedInClient(
                access_token=creds["access_token"],
                person_id=creds.get("person_id", "ArvptA8OhR"),
            )
        return self._linkedin

    def _get_meta(self):
        if self._meta is None:
            from publisher_job.meta_client import MetaClient
            creds = _get_secret_json(self._project_id, "meta-credentials")
            self._meta = MetaClient(
                instagram_token=creds["instagram_token"],
                threads_token=creds["threads_token"],
                instagram_user_id=creds["instagram_user_id"],
                facebook_page_id=creds["facebook_page_id"],
                threads_user_id=creds["threads_user_id"],
            )
        return self._meta

    def _get_youtube(self):
        if self._youtube is None:
            from publisher_job.youtube_client import YouTubeClient
            self._youtube = YouTubeClient(
                client_id=_get_secret(self._project_id, "youtube-oauth-client-id"),
                client_secret=_get_secret(self._project_id, "youtube-oauth-client-secret"),
                refresh_token=_get_secret(self._project_id, "youtube-oauth-refresh-token"),
            )
        return self._youtube

    # ── Processamento da fila ──────────────────────────────────────────────────

    def _pendentes_por_vencimento(self) -> list:
        """
        TODAS as peças `planned`, da mais vencida para a mais recente.

        A versão anterior era `.where(status==planned).limit(50)`, sem
        ordenação. Com mais de 50 pendentes o Firestore devolve 50 QUAISQUER,
        e as que ficam de fora não são vistas — nem nesta rodada nem nas
        seguintes, porque a janela não anda. Em 31/08 havia 71 pendentes: 21
        eram invisíveis, e entre elas um post do Threads vencido havia mais de
        um dia. Nada acusava erro, porque do ponto de vista do job aqueles
        documentos não existiam.

        Pagina em vez de subir o limite: assim a correção não depende de
        alguém adivinhar um teto novo quando a fila crescer. A ordenação é
        feita aqui, em Python, porque `where` + `order_by` em campos
        diferentes exigiria um índice composto — e um índice ausente falha em
        produção, não no teste.
        """
        col = self._db.collection(COLLECTION_QUEUE).where("status", "==", "planned")
        todos: list = []
        ultimo = None
        while len(todos) < MAX_FILA_VARRIDA:
            q = col.limit(PAGINA_FILA)
            if ultimo is not None:
                q = q.start_after(ultimo)
            pagina = list(q.get())
            if not pagina:
                break
            todos.extend(pagina)
            ultimo = pagina[-1]
            if len(pagina) < PAGINA_FILA:
                break

        if len(todos) >= MAX_FILA_VARRIDA:
            logger.warning(
                "[publisher] fila com %d+ pendentes; varrendo só os primeiros. "
                "Algo está enfileirando mais do que publicando.", MAX_FILA_VARRIDA,
            )

        def quando(doc) -> str:
            d = doc.to_dict() or {}
            return str(d.get("scheduledAt") or d.get("scheduled_at") or "")

        todos.sort(key=quando)
        return todos

    def run(self) -> dict[str, int]:
        """
        Processa todos os itens pending com scheduled_at <= agora.

        Returns:
            dict com contagens: published, failed, skipped.
        """
        now = datetime.now(timezone.utc)
        results = {"published": 0, "failed": 0, "skipped": 0}

        docs = self._pendentes_por_vencimento()

        publicados_nesta_rodada = 0
        for doc in docs:
            data = doc.to_dict()
            scheduled_at = data.get("scheduledAt") or data.get("scheduled_at")

            # Converte scheduled_at para datetime aware se necessário
            if isinstance(scheduled_at, str):
                try:
                    scheduled_at = datetime.fromisoformat(
                        scheduled_at.replace("Z", "+00:00")
                    )
                except Exception:
                    scheduled_at = None

            if scheduled_at and scheduled_at.tzinfo is None:
                scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)

            if scheduled_at and scheduled_at > now:
                results["skipped"] += 1
                continue

            # Idempotência: não republica se já tem post_id
            if data.get("platform_post_id"):
                results["skipped"] += 1
                continue

            retry_count = data.get("attempts", data.get("retry_count", 0))
            if retry_count >= MAX_RETRIES:
                if data.get("status") != "failed":
                    doc.reference.update({
                        "status": "failed",
                        "error": data.get("error") or "Max retries exceeded",
                        "errorCode": "MAX_RETRIES",
                        "updatedAt": now.isoformat(),
                    })
                results["failed"] += 1
                continue

            if publicados_nesta_rodada >= MAX_PUBLICACOES_POR_RODADA:
                # Teto de vazão, não de visibilidade: o que sobra é o mais
                # recente, e a próxima rodada (de hora em hora) o pega — agora
                # em ordem, porque a lista vem ordenada por vencimento.
                logger.info(
                    "[publisher] teto de %d publicações nesta rodada; o resto sai na próxima.",
                    MAX_PUBLICACOES_POR_RODADA,
                )
                break

            logger.info(f"Publishing [{data.get('platform')}] {data.get('title', '')[:50]}")
            try:
                post_id = self.publish_single(data)
                doc.reference.update({
                    "status":          "published",
                    "platform_post_id": post_id,
                    "publishedAt":     now.isoformat(),
                    "updatedAt":       now.isoformat(),
                    "error":           None,
                    "errorCode":       None,
                })
                logger.info(f"  ✅ {data.get('platform')}: {post_id}")
                results["published"] += 1
                publicados_nesta_rodada += 1

            except Exception as exc:
                err_msg  = str(exc)[:500]
                err_code = _classify_error(err_msg)
                new_retry = retry_count + 1
                update = {
                    "attempts":   new_retry,
                    "error":      err_msg,
                    "errorCode":  err_code,
                    "updatedAt":  now.isoformat(),
                }
                if new_retry >= MAX_RETRIES:
                    update["status"] = "failed"
                doc.reference.update(update)
                logger.error(f"  ❌ {data.get('platform')}: {err_msg}")
                results["failed"] += 1

        logger.info(f"Publisher run complete: {results}")
        return results

    # ── Publicação imediata pós-vídeo ──────────────────────────────────────────

    def _ler_timeline(self, project_id: str) -> list[dict]:
        """`timeline.json` do editor: início e fim medidos de cada segmento."""
        from google.cloud import storage as _gcs
        blob = (_gcs.Client(project=self._project_id)
                .bucket(f"{self._project_id}-pipeline-media")
                .blob(f"projects/{project_id}/timeline.json"))
        dados = json.loads(blob.download_as_text())
        if isinstance(dados, list):
            return dados
        return dados.get("segments") or dados.get("timeline") or []

    def _ler_manifest_html(self, project_id: str) -> str:
        """Deck montado — é dele que sai o título visível de cada slide."""
        from google.cloud import storage as _gcs
        return (_gcs.Client(project=self._project_id)
                .bucket(f"{self._project_id}-pipeline-media")
                .blob(f"projects/{project_id}/manifest.html")
                .download_as_text())

    def publish_video_ready(self, msg: VideoReadyMsg) -> dict[str, str]:
        """
        Publicação imediata quando um vídeo finalizado chega do video-editor-job.

        Publica:
          - YouTube: vídeo horizontal (longo) + Short vertical (com thumbnail)
          - Instagram: Reel vertical
          - LinkedIn, Threads: post de texto com link

        Idempotência por plataforma: cada content_projects/{id} é uma jornada de
        produção; cada publicação por plataforma é um asset independente. Se este
        método já rodou antes e algumas plataformas tiveram sucesso (post_id
        gravado em stages.publisher.platforms), elas são PULADAS numa nova
        execução — evita duplicar uploads/posts ao reprocessar o stage "publisher"
        (via /api/csm/calendar/retry) depois de uma falha parcial.

        Args:
            msg: VideoReadyMsg com URLs do GCS.

        Returns:
            dict plataforma → post_id (ou "*_error" → mensagem).
        """
        results: dict[str, str] = {}
        project_id = msg.project_id
        project_ref = self._db.collection("content_projects").document(project_id)

        # Lê metadados do projeto no Firestore
        proj_doc = project_ref.get()
        meta: dict[str, Any] = proj_doc.to_dict() if proj_doc.exists else {}

        # Publicações já bem-sucedidas em uma tentativa anterior (retry parcial)
        already_ok: dict[str, str] = (
            meta.get("stages", {}).get("publisher", {}).get("platforms", {})
        )
        started_at = int(time.time())
        title       = meta.get("title", f"Conteúdo éozoré — {project_id}")
        description = meta.get("description", "")
        tags        = meta.get("tags", ["ia", "machinelearning", "eozore"])
        article_url = meta.get("article_url", "https://eozore.com/pt-BR/blog")
        subtitle    = meta.get("subtitle", description[:80] if description else "Canal Victor Zoré")
        # A capa NÃO usa o título. Com os 63 caracteres do vídeo de 27/08 ela
        # saiu com sete linhas de texto — ilegível em miniatura. Cai no título
        # só quando a frase não foi gerada, que é o comportamento anterior.
        thumb_frase = (meta.get("thumb_frase") or "").strip() or title
        thumb_apoio = (meta.get("thumb_apoio") or "").strip() or subtitle
        category    = meta.get("category", "ia")

        # URL do vídeo longo, quando ele já subiu numa execução anterior. É o
        # link certo para acompanhar a peça vertical — o artigo é outro
        # destino. Os posts saíam apontando para o blog mesmo quando o assunto
        # era o vídeo.
        youtube_id  = (meta.get("publish_results") or {}).get("youtube") or already_ok.get("youtube")
        youtube_url = f"https://youtu.be/{youtube_id}" if youtube_id else YOUTUBE_CHANNEL_URL

        # Capítulos entram no marcador que a descrição já reserva. Ficam aqui
        # e não em quem monta a descrição porque dependem da duração MEDIDA de
        # cada clipe, que só existe depois da edição.
        capitulos = ""
        try:
            capitulos = montar_capitulos(
                self._ler_timeline(project_id),
                self._ler_manifest_html(project_id),
            )
        except Exception as exc:                       # noqa: BLE001
            logger.warning("[publisher] capítulos indisponíveis: %s", exc)

        corpo = description or ""
        if MARCADOR_CAPITULOS in corpo:
            # Sem capítulos, o marcador some junto com a linha em branco que o
            # cercava — em vez de deixar um buraco no meio da descrição.
            corpo = (corpo.replace(f"\n\n{MARCADOR_CAPITULOS}", f"\n\n{capitulos}")
                     if capitulos else corpo.replace(f"\n\n{MARCADOR_CAPITULOS}", ""))
        elif capitulos:
            corpo = f"{corpo}\n\n{capitulos}" if corpo else capitulos

        copy_long = (
            f"{corpo}\n\n"
            f"📖 Artigo completo: {article_url}"
        ).strip()
        # ── Copy do curto: própria, não herdada do vídeo longo ───────────────
        #
        # Antes era `f"{title} #Shorts"` e `f"{title}\n\n#Shorts #IA
        # #MachineLearning"` — o título de um vídeo de seis minutos colado num
        # curto de cinquenta segundos, com três hashtags fixas iguais para
        # todo tema. Um Short vive da retenção nos dois primeiros segundos; a
        # legenda dele precisa do próprio gancho, do trecho que ele mostra.
        #
        # O roteirista JÁ escreve esse gancho em `vertical_cut.title` e nada o
        # lia. As hashtags passam a ser as da série: quem chega por uma peça
        # solta encontra o catálogo pela mesma tag, o que não acontece quando
        # cada post inventa as suas.
        short_frase = (meta.get("short_frase") or "").strip()
        tags_serie  = _hashtags_da_serie(meta.get("serie"))
        gancho_curto = short_frase or title

        # "#Shorts" no título é o que o YouTube usa como dica de formato.
        short_title = f"{gancho_curto[:90]} #Shorts"
        copy_short  = (
            f"{gancho_curto}\n\n"
            f"▶️ Versão completa: {youtube_url}\n\n"
            f"#Shorts {tags_serie}"
        ).strip()
        copy_social = (
            f"{_summarize(description, 400)}\n\n"
            f"▶️ Vídeo completo: {youtube_url}\n"
            f"📖 Artigo: {article_url}"
        )

        # ── Gera thumbnails via Playwright (não bloqueia se falhar) ───────────
        thumbnail_youtube_url: str | None = None
        thumbnail_reel_url:    str | None = None

        # Só gera a thumbnail do formato cuja mídia existe nesta execução: a do
        # vídeo longo quando o horizontal chega, a do Reel quando o corte
        # vertical chega. Gerar a partir de uma string vazia só produzia uma
        # exceção silenciosa e um upload sem thumbnail.
        try:
            from publisher_job.thumbnail_generator import generate_thumbnail
            import tempfile, os

            from google.cloud import storage as gcs_storage
            gcs         = gcs_storage.Client(project=self._project_id)
            bucket_name = f"{self._project_id}-pipeline-media"
            bucket      = gcs.bucket(bucket_name)
            tmp_files: list[str] = []

            for fmt, source, key in (
                ("youtube", msg.horizontal_final, "thumbnail_youtube"),
                ("reel",    msg.vertical_final,   "thumbnail_reel"),
            ):
                if not source:
                    continue
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
                    path = tf.name
                tmp_files.append(path)
                generate_thumbnail(
                    video_path  = source,
                    title       = thumb_frase,
                    subtitle    = thumb_apoio,
                    format      = fmt,
                    category    = category,
                    output_path = path,
                )
                # Caminho alinhado ao resto do projeto: tudo vive sob
                # projects/{project_id}/. Sem o prefixo, as thumbnails caíam
                # soltas na raiz do bucket e escapavam do lifecycle_job.
                blob_path = f"projects/{project_id}/{key}.png"
                bucket.blob(blob_path).upload_from_filename(path, content_type="image/png")
                signed = _gcs_to_signed_url(f"gs://{bucket_name}/{blob_path}", 120)
                if fmt == "youtube":
                    thumbnail_youtube_url = signed
                else:
                    thumbnail_reel_url = signed
                results[key] = f"gs://{bucket_name}/{blob_path}"
                logger.info("Thumbnail %s gerada para %s", fmt, project_id)

            for p in tmp_files:
                try: os.unlink(p)
                except Exception: pass

        except Exception as e:
            logger.warning(f"Thumbnail generation failed (non-fatal): {e}")

        # Cada plataforma abaixo checa `already_ok` antes de publicar — se uma
        # tentativa anterior deste projeto já teve sucesso nela, reaproveita o
        # post_id em vez de publicar de novo (evita vídeo/post duplicado num retry).
        # Cada entrada declara de qual arquivo depende. Uma execução vinda do
        # video-editor traz só o horizontal; a do corte vertical, só o
        # vertical. Sem esta checagem, o canal sem mídia tentava subir uma
        # string vazia e falhava com um erro que não dizia nada.
        platform_attempts: list[tuple[str, str, Any]] = [
            ("youtube", msg.horizontal_final, lambda: self._get_youtube().upload_video(
                video_source=msg.horizontal_final, title=title, description=copy_long,
                tags=tags, category_id="27", privacy=YOUTUBE_UPLOAD_PRIVACY, is_short=False,
                thumbnail_url=thumbnail_youtube_url,
            )),
            ("youtube_short", msg.vertical_final, lambda: self._get_youtube().upload_video(
                video_source=msg.vertical_final, title=short_title, description=copy_short,
                tags=tags + ["Shorts"], category_id="27", privacy=YOUTUBE_UPLOAD_PRIVACY, is_short=True,
                thumbnail_url=thumbnail_reel_url,
            )),
            ("instagram_reel", msg.vertical_final, lambda: self._get_meta().publish_instagram({
                "format": "reel", "asset_urls": [_prepare_media_url(msg.vertical_final)], "copy": copy_social,
            })),
            ("linkedin", "-", lambda: self._get_linkedin().publish({"copy": copy_social, "format": "text"})),
            ("threads", "-", lambda: self._get_meta().publish_threads({"copy": copy_social})),
        ]
        no_media = [p for p, source, _ in platform_attempts if not source]
        if no_media:
            logger.info(
                "[publisher] %s: sem mídia para %s nesta execução — pulando.",
                project_id, ", ".join(no_media),
            )
        platform_attempts = [(p, s, a) for p, s, a in platform_attempts if s]

        # Só publica nos canais aprovados para ESTE projeto. Sem este filtro,
        # todo projeto publicava nos 5 canais — então cada Reel de ~22s também
        # virava um vídeo longo no canal do YouTube. Um ciclo com 1 vídeo + 3
        # Reels gerava 4 vídeos indevidos no canal, e o vídeo principal (que é
        # o único que deveria estar lá) nem chegava a subir.
        #
        # A lista vem do doc do projeto porque se perde na cadeia Pub/Sub: o
        # pipeline-submit a define corretamente na PackageApprovedMsg, mas
        # tts-job → avatar-job → video-editor-job não a propagam adiante.
        #
        # Lista vazia = projeto antigo, anterior a este campo: mantém o
        # comportamento de publicar em tudo para não quebrar retry de projeto
        # já em andamento.
        approved = set(meta.get("channels_approved") or [])
        # O corte vertical declara seus próprios canais no momento em que é
        # solicitado; eles se somam aos do projeto (que, para o vídeo longo,
        # é só 'youtube').
        approved |= set(
            (meta.get("stages", {}).get("vertical_cut", {}) or {}).get("channels") or []
        )
        if approved:
            skipped = [p for p, _, _ in platform_attempts if p not in approved]
            if skipped:
                logger.info(
                    "[publisher] %s: canais fora de channels_approved, pulando: %s",
                    project_id, ", ".join(skipped),
                )
            platform_attempts = [(p, s, a) for p, s, a in platform_attempts if p in approved]
        else:
            # Lista vazia NÃO é mais "publica em tudo". Esse fallback foi o que
            # transformou 2 Reels em 4 vídeos indevidos no canal: os projetos
            # tinham sido criados antes do campo existir, caíam aqui, e cada
            # peça curta virava também um vídeo longo no YouTube.
            logger.error(
                "[publisher] %s sem channels_approved — nada será publicado. "
                "Defina os canais no projeto antes de republicar.", project_id,
            )
            platform_attempts = []

        platforms_status: dict[str, str] = dict(already_ok)  # preserva sucessos anteriores
        for platform, _source, attempt in platform_attempts:
            if already_ok.get(platform):
                post_id = already_ok[platform]
                # No YouTube, "já publicado" não significa "nada a fazer":
                # descrição e capa podem ter sido regeradas. Atualizar no lugar
                # é o que evita um segundo vídeo do mesmo tema no canal — em
                # 27/08, republicar deixou três.
                if platform == "youtube":
                    try:
                        self._get_youtube().update_video_metadata(
                            video_id=post_id, title=title, description=copy_long,
                            tags=tags, category_id="27",
                            thumbnail_url=thumbnail_youtube_url,
                        )
                        logger.info("[publisher] youtube %s atualizado no lugar.", post_id)
                    except Exception as exc:                     # noqa: BLE001
                        # Não sobe: um vídeo com descrição velha continua no ar
                        # e visível. Falhar aqui e reenviar criaria o duplicado
                        # que este caminho existe para evitar.
                        logger.warning("[publisher] update do youtube falhou (%s).", exc)
                results[platform] = post_id
                if platform != "youtube":
                    logger.info(f"[publisher] {platform} já publicado (post_id={post_id}) — pulando.")
                continue
            try:
                post_id = attempt()
                results[platform] = post_id
                platforms_status[platform] = post_id
            except Exception as e:
                logger.error(f"{platform} failed: {e}")
                results[f"{platform}_error"] = str(e)[:200]
                platforms_status[platform] = ""  # marca tentativa feita, sem sucesso — não vira "já ok"

        # O artigo foi publicado ANTES do vídeo existir — às vezes dias antes.
        # Este é o único momento em que se sabe o id do YouTube, então é aqui
        # que o link volta para o artigo.
        id_youtube = results.get("youtube")
        if id_youtube and not str(id_youtube).startswith("pending"):
            self._anexar_video_ao_artigo(
                meta.get("article_slug"), f"https://youtu.be/{id_youtube}",
            )

        # YouTube Community Post: não tem API pública — salva para publicação manual
        results["youtube_community"] = "pending_manual — publicar manualmente no YouTube Studio"

        # Sucesso = todas as plataformas com API real tiveram post_id não-vazio
        tracked_platforms = [p for p, _, _ in platform_attempts]
        # `all([])` é True: sem nenhuma tentativa, o projeto era marcado como
        # "published" tendo publicado nada.
        all_ok = bool(tracked_platforms) and all(
            platforms_status.get(p) for p in tracked_platforms
        )
        failed_platforms = [p for p in tracked_platforms if not platforms_status.get(p)]

        now_ts = int(time.time())
        try:
            project_ref.update({
                "status":                    "published" if all_ok else "published_partial",
                "publish_results":           results,
                "published_at":              datetime.now(timezone.utc).isoformat(),
                "stages.publisher.status":       "completed" if all_ok else "error",
                "stages.publisher.platforms":    platforms_status,
                "stages.publisher.started_at":   started_at,
                "stages.publisher.completed_at": now_ts,
                "stages.publisher.error_message": (
                    None if all_ok else f"Falha em: {', '.join(failed_platforms)}. Use retry para reprocessar só essas plataformas."
                ),
            })
        except Exception as e:
            logger.warning(f"Firestore project update failed: {e}")

        return results

    # ── Publicação de item individual ──────────────────────────────────────────

    def publish_single(self, data: dict[str, Any]) -> str:
        """
        Publica um item da fila em sua plataforma de destino.

        Args:
            data: documento da coleção publish_queue.

        Returns:
            post_id (str).

        Raises:
            RuntimeError: falha irrecuperável na API.
            ValueError:   plataforma desconhecida.
        """
        platform = data.get("platform", "")
        fmt      = data.get("format", "")

        # Resolve [LINK_ARTIGO] / [LINK_CANAL] ANTES de qualquer publicação.
        # Precisa cobrir tanto o copy quanto os posts de thread — o último post
        # de toda thread termina em "Artigo completo: [LINK_ARTIGO]".
        data = dict(data)  # não muta o documento original do chamador
        data["copy"] = self._resolve_placeholders(data.get("copy"), data)
        for key in ("thread_posts", "threadPosts"):
            posts = data.get(key)
            if isinstance(posts, list):
                data[key] = [self._resolve_placeholders(p, data) for p in posts]
        if isinstance(data.get("title"), str):
            data["title"] = self._resolve_placeholders(data["title"], data)
        # comentario_fixado (LinkedIn): o link mora aqui, não no corpo do
        # post — link no corpo mede pior no alcance do algoritmo do LinkedIn.
        for key in ("comentario_fixado", "firstComment"):
            if isinstance(data.get(key), str):
                data[key] = self._resolve_placeholders(data[key], data)

        # Marcador resolvido é o caminho feliz; isto é a rede embaixo dele.
        data = self._garantir_link(data, platform)

        # Normaliza asset_urls
        if not data.get("asset_urls") and data.get("videoUrl"):
            data["asset_urls"] = [data["videoUrl"]]
        elif not data.get("asset_urls") and data.get("imageUrl"):
            data["asset_urls"] = [data["imageUrl"]]

        # Para Instagram e Facebook: prepara URLs de mídia (Signed URL se GCS privado)
        if platform in ("instagram", "facebook") and data.get("asset_urls"):
            data["asset_urls"] = [_prepare_media_url(u) for u in data["asset_urls"] if u]
        if platform in ("instagram", "facebook") and data.get("image_url"):
            data["image_url"] = _prepare_media_url(data["image_url"])
        if platform in ("instagram", "facebook") and data.get("imageUrl"):
            data["imageUrl"] = _prepare_media_url(data["imageUrl"])

        match platform:

            case "linkedin":
                post_id = self._get_linkedin().publish(data)
                # Comentário fixado com o link — pós-publicação, best-effort:
                # o post já existe e vale por si, então uma falha aqui não
                # pode derrubar o resultado da publicação principal.
                comentario = data.get("comentario_fixado") or data.get("firstComment")
                if comentario and post_id:
                    try:
                        self._get_linkedin().post_first_comment(post_id, comentario)
                    except Exception as exc:
                        logger.warning(f"LinkedIn first comment falhou (não-fatal): {exc}")
                return post_id

            case "youtube" | "youtube_shorts":
                yt     = self._get_youtube()
                source = (data.get("asset_urls") or [None])[0] or data.get("videoUrl")
                if not source:
                    raise ValueError("YouTube: sem video URL")
                is_short = (platform == "youtube_shorts" or fmt == "shorts")

                # Gera thumbnail via Playwright antes do upload (não bloqueia se falhar)
                thumb_url: str | None = None
                try:
                    from publisher_job.thumbnail_generator import generate_thumbnail
                    import tempfile, os
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
                        tmp_thumb = tf.name
                    generate_thumbnail(
                        video_path  = source,
                        title       = data.get("title", "Vídeo éozoré")[:60],
                        subtitle    = data.get("subtitle", data.get("copy", "")[:80]),
                        format      = "reel" if is_short else "youtube",
                        category    = data.get("category", "ia"),
                        output_path = tmp_thumb,
                    )
                    # Upload thumbnail para GCS e gera Signed URL
                    from google.cloud import storage as gcs_storage
                    gcs   = gcs_storage.Client(project=self._project_id)
                    fname = f"thumbnails/{data.get('id','thumb')}_{int(time.time())}.png"
                    blob  = gcs.bucket(f"{self._project_id}-pipeline-media").blob(fname)
                    blob.upload_from_filename(tmp_thumb, content_type="image/png")
                    thumb_url = _gcs_to_signed_url(
                        f"gs://{self._project_id}-pipeline-media/{fname}", 120
                    )
                    try: os.unlink(tmp_thumb)
                    except Exception: pass
                    logger.info(f"Thumbnail gerada para YouTube: {fname}")
                except Exception as te:
                    logger.warning(f"Thumbnail generation skipped: {te}")

                return yt.upload_video(
                    video_source=source,
                    title=data.get("title", "Vídeo éozoré")[:100],
                    description=data.get("copy", "")[:5000],
                    tags=data.get("tags", ["ia", "machinelearning"]),
                    privacy=data.get("privacy", "public"),
                    is_short=is_short,
                    thumbnail_url=thumb_url,
                )

            case "youtube_community":
                # YouTube Community Posts não têm API pública.
                # Salva o conteúdo para publicação manual no YouTube Studio.
                logger.info(
                    "YouTube Community Post: API não disponível — conteúdo salvo para publicação manual."
                )
                return f"pending_manual_yt_community_{int(time.time())}"

            case "instagram":
                return self._get_meta().publish_instagram(data)

            case "facebook":
                return self._get_meta().publish_facebook(data)

            case "threads":
                # Thread sequencial (série de posts) ou post único
                thread_posts = data.get("threadPosts") or data.get("thread_posts")
                if thread_posts and isinstance(thread_posts, list) and len(thread_posts) > 1:
                    ids = self._get_meta().publish_thread_series(thread_posts)
                    return ids[0] if ids else "th-series-empty"
                return self._get_meta().publish_threads(data)

            case _:
                raise ValueError(f"Plataforma desconhecida: {platform!r}")
