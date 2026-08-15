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

# Visibilidade do upload no YouTube: 'public' | 'unlisted' | 'private'.
# Default 'public' preserva o comportamento existente. 'unlisted' é o modo
# recomendado para validar um ciclo end-to-end sem o vídeo ficar visível
# publicamente antes de revisão — o vídeo sobe de verdade, mas só quem tem
# o link acessa, até o dono trocar manualmente para público.
YOUTUBE_UPLOAD_PRIVACY = os.environ.get("YOUTUBE_UPLOAD_PRIVACY", "public").strip().lower()
if YOUTUBE_UPLOAD_PRIVACY not in ("public", "unlisted", "private"):
    logger.warning(
        "YOUTUBE_UPLOAD_PRIVACY=%r inválido, usando 'public'.", YOUTUBE_UPLOAD_PRIVACY
    )
    YOUTUBE_UPLOAD_PRIVACY = "public"
MAX_RETRIES      = 3
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
        credentials, project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/devstorage.read_only"]
        )
        # Força renovação para ter token fresco
        from google.auth.transport.requests import Request as GoogleAuthRequest
        credentials.refresh(GoogleAuthRequest())

        client = storage.Client(credentials=credentials)
        bucket = client.bucket(bucket_name)
        blob   = bucket.blob(blob_name)

        signed_url = blob.generate_signed_url(
            expiration=dt.timedelta(minutes=expiration_minutes),
            method="GET",
            version="v4",
            credentials=credentials,
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

    def run(self) -> dict[str, int]:
        """
        Processa todos os itens pending com scheduled_at <= agora.

        Returns:
            dict com contagens: published, failed, skipped.
        """
        now = datetime.now(timezone.utc)
        results = {"published": 0, "failed": 0, "skipped": 0}

        docs = list(
            self._db.collection(COLLECTION_QUEUE)
            .where("status", "==", "planned")   # pipeline-submit salva com status=planned
            .limit(50)
            .get()
        )

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
        category    = meta.get("category", "ia")

        copy_long = (
            f"{description}\n\n"
            f"📖 Artigo completo: {article_url}\n\n"
            f"💡 Assine o canal para mais conteúdo técnico sobre IA e ML."
        )
        copy_short = f"{title}\n\n#Shorts #IA #MachineLearning"
        copy_social = (
            f"{description[:300]}...\n\n"
            f"▶️ Vídeo completo no canal (link na bio)\n"
            f"📖 Artigo: {article_url}"
        )

        # ── Gera thumbnails via Playwright (não bloqueia se falhar) ───────────
        thumbnail_youtube_url: str | None = None
        thumbnail_reel_url:    str | None = None

        try:
            from publisher_job.thumbnail_generator import generate_thumbnail
            import tempfile, os

            # Baixa vídeo horizontal para extrair frame (ou usa path local se GCS)
            video_for_thumb = msg.horizontal_final

            # YouTube thumbnail (1280x720)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
                thumb_yt_path = tf.name
            generate_thumbnail(
                video_path      = video_for_thumb,
                title           = title,
                subtitle        = subtitle,
                format          = "youtube",
                category        = category,
                output_path     = thumb_yt_path,
            )

            # Reel thumbnail (1080x1920) — usa vídeo vertical
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
                thumb_reel_path = tf.name
            generate_thumbnail(
                video_path      = msg.vertical_final,
                title           = title,
                subtitle        = subtitle,
                format          = "reel",
                category        = category,
                output_path     = thumb_reel_path,
            )

            # Faz upload das thumbnails para GCS
            from google.cloud import storage as gcs_storage
            gcs = gcs_storage.Client(project=self._project_id)
            bucket_name = f"{self._project_id}-pipeline-media"
            bucket = gcs.bucket(bucket_name)

            yt_blob   = bucket.blob(f"{project_id}/thumbnail_youtube.png")
            reel_blob = bucket.blob(f"{project_id}/thumbnail_reel.png")
            yt_blob.upload_from_filename(thumb_yt_path,   content_type="image/png")
            reel_blob.upload_from_filename(thumb_reel_path, content_type="image/png")

            # Gera Signed URLs para usar no YouTube e Instagram
            thumbnail_youtube_url = _gcs_to_signed_url(
                f"gs://{bucket_name}/{project_id}/thumbnail_youtube.png", 120
            )
            thumbnail_reel_url = _gcs_to_signed_url(
                f"gs://{bucket_name}/{project_id}/thumbnail_reel.png", 120
            )
            results["thumbnail_youtube"] = f"gs://{bucket_name}/{project_id}/thumbnail_youtube.png"
            results["thumbnail_reel"]    = f"gs://{bucket_name}/{project_id}/thumbnail_reel.png"
            logger.info(f"Thumbnails geradas para {project_id}")

            # Limpa arquivos temporários
            for p in [thumb_yt_path, thumb_reel_path]:
                try: os.unlink(p)
                except Exception: pass

        except Exception as e:
            logger.warning(f"Thumbnail generation failed (non-fatal): {e}")

        # Cada plataforma abaixo checa `already_ok` antes de publicar — se uma
        # tentativa anterior deste projeto já teve sucesso nela, reaproveita o
        # post_id em vez de publicar de novo (evita vídeo/post duplicado num retry).
        platform_attempts: list[tuple[str, Any]] = [
            ("youtube", lambda: self._get_youtube().upload_video(
                video_source=msg.horizontal_final, title=title, description=copy_long,
                tags=tags, category_id="27", privacy=YOUTUBE_UPLOAD_PRIVACY, is_short=False,
                thumbnail_url=thumbnail_youtube_url,
            )),
            ("youtube_short", lambda: self._get_youtube().upload_video(
                video_source=msg.vertical_final, title=f"#{title} (Short)", description=copy_short,
                tags=tags + ["Shorts"], category_id="27", privacy=YOUTUBE_UPLOAD_PRIVACY, is_short=True,
                thumbnail_url=thumbnail_reel_url,
            )),
            ("instagram_reel", lambda: self._get_meta().publish_instagram({
                "format": "reel", "asset_urls": [_prepare_media_url(msg.vertical_final)], "copy": copy_social,
            })),
            ("linkedin", lambda: self._get_linkedin().publish({"copy": copy_social, "format": "text"})),
            ("threads", lambda: self._get_meta().publish_threads({"copy": copy_social})),
        ]

        platforms_status: dict[str, str] = dict(already_ok)  # preserva sucessos anteriores
        for platform, attempt in platform_attempts:
            if already_ok.get(platform):
                results[platform] = already_ok[platform]
                logger.info(f"[publisher] {platform} já publicado em tentativa anterior (post_id={already_ok[platform]}) — pulando.")
                continue
            try:
                post_id = attempt()
                results[platform] = post_id
                platforms_status[platform] = post_id
            except Exception as e:
                logger.error(f"{platform} failed: {e}")
                results[f"{platform}_error"] = str(e)[:200]
                platforms_status[platform] = ""  # marca tentativa feita, sem sucesso — não vira "já ok"

        # YouTube Community Post: não tem API pública — salva para publicação manual
        results["youtube_community"] = "pending_manual — publicar manualmente no YouTube Studio"

        # Sucesso = todas as plataformas com API real tiveram post_id não-vazio
        tracked_platforms = [p for p, _ in platform_attempts]
        all_ok = all(platforms_status.get(p) for p in tracked_platforms)
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
                return self._get_linkedin().publish(data)

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
