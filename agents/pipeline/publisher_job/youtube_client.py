# -*- coding: utf-8 -*-
"""
publisher_job/youtube_client.py
================================
Publica vídeos e Community Posts no canal Victor Zoré via YouTube Data API v3.

Funcionalidades:
  - Upload de vídeo (horizontal/vertical) com metadados
  - Community Post (texto + imagem opcional)
  - Renovação automática de access_token via refresh_token
  - Resumable upload para vídeos grandes (>= 5 MB)

Autenticação:
  Secrets no GCP Secret Manager (vazfy-417019):
    - youtube-oauth-client-id
    - youtube-oauth-client-secret
    - youtube-oauth-refresh-token
"""

import json
import logging
import os
import ssl
import time
import urllib.parse
import urllib.request
from typing import Any

import requests

logger = logging.getLogger("publisher_job.youtube")

YOUTUBE_API     = "https://www.googleapis.com/youtube/v3"
UPLOAD_API      = "https://www.googleapis.com/upload/youtube/v3"
TOKEN_ENDPOINT  = "https://oauth2.googleapis.com/token"

# Chunk size para resumable upload: 8 MB
CHUNK_SIZE = 8 * 1024 * 1024


class YouTubeClient:
    """
    Publica no canal Victor Zoré via YouTube Data API v3.

    Args:
        client_id:     OAuth 2.0 client ID.
        client_secret: OAuth 2.0 client secret.
        refresh_token: Refresh token de longa duração.
    """

    def __init__(self, client_id: str, client_secret: str, refresh_token: str) -> None:
        self._client_id     = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._access_token: str | None = None
        self._token_expiry: float = 0.0

    # ── Access token ──────────────────────────────────────────────────────────

    def _get_access_token(self) -> str:
        """Retorna access_token válido, renovando se necessário."""
        if self._access_token and time.time() < self._token_expiry - 60:
            return self._access_token

        data = urllib.parse.urlencode({
            "client_id":     self._client_id,
            "client_secret": self._client_secret,
            "refresh_token": self._refresh_token,
            "grant_type":    "refresh_token",
        }).encode()

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode    = ssl.CERT_NONE

        req = urllib.request.Request(
            TOKEN_ENDPOINT, data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            result = json.loads(resp.read())

        if "access_token" not in result:
            raise RuntimeError(f"YouTube OAuth refresh failed: {result}")

        self._access_token = result["access_token"]
        self._token_expiry = time.time() + result.get("expires_in", 3600)
        logger.debug("YouTube access_token renovado")
        return self._access_token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type":  "application/json",
        }

    # ── Upload de vídeo ───────────────────────────────────────────────────────

    def upload_video(
        self,
        video_source: str,
        title:        str,
        description:  str,
        tags:         list[str] | None = None,
        category_id:  str = "27",          # Educação
        privacy:      str = "public",       # public | unlisted | private
        is_short:     bool = False,
        thumbnail_url: str | None = None,
    ) -> str:
        """
        Faz upload de um vídeo para o canal.

        Args:
            video_source:  URL pública do vídeo (GCS, HeyGen, etc.) ou caminho local.
            title:         Título do vídeo (máx 100 chars).
            description:   Descrição do vídeo.
            tags:          Lista de tags (máx 500 chars total).
            category_id:   ID da categoria YouTube (27 = Educação, 28 = C&T).
            privacy:       Visibilidade: 'public', 'unlisted', 'private'.
            is_short:      Se True, adiciona #Shorts à descrição para indexação.
            thumbnail_url: URL de thumbnail customizada (opcional).

        Returns:
            video_id (str) do vídeo publicado.

        Raises:
            RuntimeError: falha no upload.
        """
        # Prepara metadados
        if is_short and "#Shorts" not in description:
            description = f"{description}\n\n#Shorts"

        title = title[:100]
        all_tags = (tags or []) + (["Shorts"] if is_short else [])

        metadata = {
            "snippet": {
                "title":       title,
                "description": description,
                "tags":        all_tags[:500 // max(1, len(" ".join(all_tags))) * len(all_tags)],
                "categoryId":  category_id,
                "defaultLanguage": "pt",
                "defaultAudioLanguage": "pt",
            },
            "status": {
                "privacyStatus":           privacy,
                "selfDeclaredMadeForKids": False,
            },
        }

        # Inicia upload resumable
        init_headers = {
            "Authorization":  f"Bearer {self._get_access_token()}",
            "Content-Type":   "application/json",
            "X-Upload-Content-Type": "video/*",
        }
        init_r = requests.post(
            f"{UPLOAD_API}/videos?uploadType=resumable&part=snippet,status",
            headers=init_headers,
            json=metadata,
            timeout=30,
        )
        if init_r.status_code != 200:
            raise RuntimeError(f"YouTube upload init failed {init_r.status_code}: {init_r.text[:300]}")

        upload_url = init_r.headers.get("Location")
        if not upload_url:
            raise RuntimeError("YouTube upload init: sem Location header")

        # Obtém bytes do vídeo (URL ou path local)
        video_bytes = self._fetch_video_bytes(video_source)
        total_size  = len(video_bytes)
        logger.info(f"YouTube upload: {title!r} ({total_size / 1024 / 1024:.1f} MB)")

        # Faz upload em chunks
        video_id = self._resumable_upload(upload_url, video_bytes, total_size)
        logger.info(f"YouTube video published: {video_id}")

        # Thumbnail customizada (opcional, não bloqueia se falhar)
        if thumbnail_url:
            self._set_thumbnail(video_id, thumbnail_url)

        return video_id

    def _fetch_video_bytes(self, source: str) -> bytes:
        """
        Baixa vídeo de URL, GCS, ou lê de path local.

        gs:// nunca foi tratado: video_editor_job publica o path final como
        "gs://bucket/projects/.../final_horizontal.mp4", e isso caía direto no
        fallback `open(source)`, que tenta abrir "gs://..." como caminho de
        arquivo local — sempre FileNotFoundError. Todo upload de YouTube
        falhava por esse motivo, incluindo os dois primeiros vídeos reais
        gerados por esta pipeline.

        Download via API do GCS, não Signed URL: isto roda dentro do próprio
        job/serviço com a identidade da service account, então é acesso
        servidor-a-servidor direto — não precisa de URL assinada, que é só
        para quando um terceiro externo (Instagram, Facebook) precisa buscar
        o arquivo por fora.
        """
        if source.startswith("gs://"):
            from google.cloud import storage
            bucket_name, blob_name = source[5:].split("/", 1)
            return storage.Client().bucket(bucket_name).blob(blob_name).download_as_bytes()
        if source.startswith("http://") or source.startswith("https://"):
            r = requests.get(source, timeout=120, stream=False)
            if r.status_code != 200:
                raise RuntimeError(f"Falha ao baixar vídeo {source}: {r.status_code}")
            return r.content
        with open(source, "rb") as f:
            return f.read()

    def _resumable_upload(self, upload_url: str, data: bytes, total_size: int) -> str:
        """Envia vídeo em chunks via resumable upload protocol."""
        offset = 0
        while offset < total_size:
            chunk = data[offset: offset + CHUNK_SIZE]
            end   = offset + len(chunk) - 1
            headers = {
                "Authorization":  f"Bearer {self._get_access_token()}",
                "Content-Length": str(len(chunk)),
                "Content-Range":  f"bytes {offset}-{end}/{total_size}",
            }
            r = requests.put(upload_url, headers=headers, data=chunk, timeout=120)

            if r.status_code in (200, 201):
                video_id = r.json().get("id")
                if not video_id:
                    raise RuntimeError(f"Upload completo mas sem video_id: {r.json()}")
                return video_id

            if r.status_code == 308:  # Resume Incomplete — continua
                range_header = r.headers.get("Range", "")
                if range_header:
                    offset = int(range_header.split("-")[1]) + 1
                else:
                    offset += len(chunk)
                logger.debug(f"YouTube upload progress: {offset}/{total_size} bytes")
                continue

            raise RuntimeError(f"YouTube upload chunk error {r.status_code}: {r.text[:200]}")

        raise RuntimeError("YouTube upload: loop terminou sem video_id")

    def _set_thumbnail(self, video_id: str, thumbnail_url: str) -> None:
        """Define thumbnail customizada. Não levanta exceção se falhar."""
        try:
            img_r = requests.get(thumbnail_url, timeout=30)
            if img_r.status_code != 200:
                logger.warning(f"Thumbnail download failed: {thumbnail_url}")
                return
            headers = {
                "Authorization":  f"Bearer {self._get_access_token()}",
                "Content-Type":   img_r.headers.get("Content-Type", "image/jpeg"),
            }
            # `/thumbnails/set`, não `/thumbnails`. O recurso da API é
            # `thumbnails.set` e o caminho tem o verbo; sem ele o Google
            # devolve 404 com corpo VAZIO, que não se parece nada com um erro
            # de permissão e por isso passou despercebido — o vídeo de 27/08
            # foi publicado sem thumbnail, com a imagem já gerada no GCS.
            r = requests.post(
                f"{UPLOAD_API}/thumbnails/set?uploadType=media&videoId={video_id}",
                headers=headers, data=img_r.content, timeout=60,
            )
            if r.status_code in (200, 201):
                logger.info(f"YouTube thumbnail set for {video_id}")
            else:
                logger.warning(f"YouTube thumbnail failed {r.status_code}: {r.text[:100]}")
        except Exception as e:
            logger.warning(f"YouTube thumbnail exception: {e}")

    # ── Community Post ────────────────────────────────────────────────────────

    def post_community(
        self,
        text:      str,
        image_url: str | None = None,
    ) -> str:
        """
        YouTube Community Posts NÃO estão disponíveis via YouTube Data API v3.

        A funcionalidade existe no YouTube Studio mas não tem endpoint público
        para desenvolvedores externos na Data API v3 (confirmado em julho/2026).

        Alternativa: postar manualmente via YouTube Studio ou YouTube mobile app.
        O texto gerado pelo distribution_agent fica salvo na publish_queue
        com status 'pending_manual' para publicação manual.

        Raises:
            NotImplementedError: sempre — API não disponível.
        """
        raise NotImplementedError(
            "YouTube Community Posts não estão disponíveis via API pública (YouTube Data API v3). "
            "O conteúdo foi salvo na fila para publicação manual no YouTube Studio."
        )

    # ── Metadados do canal ─────────────────────────────────────────────────────

    def get_channel_info(self) -> dict[str, Any]:
        """Retorna informações básicas do canal autenticado."""
        r = requests.get(
            f"{YOUTUBE_API}/channels",
            headers=self._headers(),
            params={"part": "snippet,statistics", "mine": "true"},
            timeout=15,
        )
        if r.status_code != 200:
            raise RuntimeError(f"YouTube channel info failed: {r.status_code}")
        items = r.json().get("items", [])
        if not items:
            raise RuntimeError("YouTube channel info: sem items — token sem acesso ao canal?")
        ch = items[0]
        return {
            "channel_id":   ch["id"],
            "title":        ch["snippet"]["title"],
            "subscribers":  ch.get("statistics", {}).get("subscriberCount", "N/A"),
            "video_count":  ch.get("statistics", {}).get("videoCount", "N/A"),
        }
