# -*- coding: utf-8 -*-
"""
publisher_job/meta_client.py
==============================
Publica nas contas éozoré do Instagram, Facebook e Threads.

IDs validados em 2026-07-24 via Graph API:
  instagram_user_id : 17841452013376253  (@eozore.ai)
  facebook_page_id  : 1205137722677825   (página Eozore)
  threads_user_id   : 27208112735475765  (@eozore.ai)

Portado do ainewz social-publisher com ajuste de IDs para éozoré.
"""

import json
import logging
import time
from typing import Any

import requests

logger = logging.getLogger("publisher_job.meta")

GRAPH_URL   = "https://graph.facebook.com/v20.0"
THREADS_URL = "https://graph.threads.net/v1.0"


class MetaClient:
    """
    Publica no Instagram, Facebook e Threads da conta éozoré.

    Args:
        instagram_token:   Token de acesso (page token da página Eozore).
        threads_token:     Token de acesso do Threads @eozore.ai.
        instagram_user_id: ID da conta IG Business (17841452013376253).
        facebook_page_id:  ID da página FB Eozore (1205137722677825).
        threads_user_id:   User ID no Threads (27208112735475765).
    """

    def __init__(
        self,
        instagram_token:   str,
        threads_token:     str,
        instagram_user_id: str,
        facebook_page_id:  str,
        threads_user_id:   str,
    ) -> None:
        self._ig_token    = instagram_token
        self._th_token    = threads_token
        self._ig_user_id  = instagram_user_id
        self._fb_page_id  = facebook_page_id
        self._th_user_id  = threads_user_id

    # ── Instagram ──────────────────────────────────────────────────────────────

    def publish_instagram(self, data: dict[str, Any]) -> str:
        """
        Publica no Instagram.

        Suporte: photo, carousel, reel, story.
        """
        fmt        = data.get("format", "image")
        asset_urls = data.get("asset_urls") or []
        copy       = data.get("copy", "")

        if fmt == "carousel" and len(asset_urls) > 1:
            return self._ig_carousel(asset_urls, copy)
        if fmt == "reel" and asset_urls:
            cover = asset_urls[1] if len(asset_urls) > 1 else data.get("image_url")
            return self._ig_reel(asset_urls[0], copy, cover)
        if fmt == "story":
            media = asset_urls[0] if asset_urls else data.get("image_url")
            if not media:
                raise ValueError("Story sem media_url")
            return self._ig_story(media)
        # feed photo
        img = asset_urls[0] if asset_urls else data.get("image_url")
        if not img:
            raise ValueError(f"Instagram {fmt} sem image_url")
        return self._ig_photo(img, copy)

    def _ig_photo(self, image_url: str, caption: str) -> str:
        r = requests.post(
            f"{GRAPH_URL}/{self._ig_user_id}/media",
            data={"image_url": image_url, "caption": caption, "access_token": self._ig_token},
            timeout=30,
        )
        res = r.json()
        if "id" not in res:
            raise RuntimeError(f"IG photo container: {res.get('error', {}).get('message', res)}")
        if not self._wait_ig_container(res["id"]):
            raise RuntimeError("IG photo container timeout")
        return self._ig_publish(res["id"])

    def _ig_reel(self, video_url: str, caption: str, cover_url: str | None = None) -> str:
        data: dict[str, str] = {
            "media_type": "REELS",
            "video_url":  video_url,
            "caption":    caption,
            "access_token": self._ig_token,
        }
        if cover_url:
            data["cover_url"] = cover_url
        r = requests.post(f"{GRAPH_URL}/{self._ig_user_id}/media", data=data, timeout=30)
        res = r.json()
        if "id" not in res:
            raise RuntimeError(f"IG reel container: {res.get('error', {}).get('message', res)}")
        cid = res["id"]
        # Poll até 5 min para vídeo processar
        start = time.time()
        delay = 5
        while time.time() - start < 300:
            s = requests.get(
                f"{GRAPH_URL}/{cid}",
                params={"fields": "status_code", "access_token": self._ig_token}, timeout=15,
            )
            status = s.json().get("status_code")
            if status == "FINISHED":
                break
            if status == "ERROR":
                raise RuntimeError(f"IG reel processing error: {s.json()}")
            time.sleep(delay)
            delay = min(delay * 1.5, 15)
        else:
            raise RuntimeError("IG reel processing timeout (5 min)")
        return self._ig_publish(cid)

    def _ig_story(self, media_url: str) -> str:
        is_video = any(ext in media_url.lower() for ext in [".mp4", ".mov", ".webm"])
        data: dict[str, str] = {"media_type": "STORIES", "access_token": self._ig_token}
        if is_video:
            data["video_url"] = media_url
        else:
            data["image_url"] = media_url
        r = requests.post(f"{GRAPH_URL}/{self._ig_user_id}/media", data=data, timeout=30)
        res = r.json()
        if "id" not in res:
            raise RuntimeError(f"IG story container: {res.get('error', {}).get('message', res)}")
        if not self._wait_ig_container(res["id"], timeout=120 if is_video else 60):
            raise RuntimeError("IG story container timeout")
        return self._ig_publish(res["id"])

    def _ig_carousel(self, image_urls: list[str], caption: str) -> str:
        children = []
        for img in image_urls[:10]:  # máx 10 slides
            r = requests.post(
                f"{GRAPH_URL}/{self._ig_user_id}/media",
                data={"image_url": img, "is_carousel_item": True, "access_token": self._ig_token},
                timeout=30,
            )
            res = r.json()
            if "id" in res:
                self._wait_ig_container(res["id"], timeout=30)
                children.append(res["id"])
        if not children:
            raise RuntimeError("IG carousel: nenhum container criado")
        r = requests.post(
            f"{GRAPH_URL}/{self._ig_user_id}/media",
            data={
                "media_type": "CAROUSEL",
                "children":   ",".join(children),
                "caption":    caption,
                "access_token": self._ig_token,
            },
            timeout=30,
        )
        res = r.json()
        if "id" not in res:
            raise RuntimeError(f"IG carousel container: {res.get('error', {}).get('message', res)}")
        if not self._wait_ig_container(res["id"], timeout=60):
            raise RuntimeError("IG carousel container timeout")
        return self._ig_publish(res["id"])

    def _ig_publish(self, creation_id: str) -> str:
        pub = requests.post(
            f"{GRAPH_URL}/{self._ig_user_id}/media_publish",
            data={"creation_id": creation_id, "access_token": self._ig_token},
            timeout=30,
        )
        post_id = pub.json().get("id")
        if not post_id:
            raise RuntimeError(f"IG publish failed: {pub.json().get('error', {}).get('message', pub.json())}")
        logger.info(f"Instagram published: {post_id}")
        return post_id

    def _wait_ig_container(self, creation_id: str, timeout: int = 60) -> bool:
        start = time.time()
        delay = 2
        while time.time() - start < timeout:
            r = requests.get(
                f"{GRAPH_URL}/{creation_id}",
                params={"fields": "status_code", "access_token": self._ig_token}, timeout=15,
            )
            status = r.json().get("status_code")
            if status == "FINISHED":
                return True
            if status == "ERROR":
                logger.error(f"IG container error: {r.json()}")
                return False
            time.sleep(delay)
            delay = min(delay * 1.5, 10)
        return False

    # ── Facebook ───────────────────────────────────────────────────────────────

    def publish_facebook(self, data: dict[str, Any]) -> str:
        """Publica na página Eozore do Facebook."""
        copy      = data.get("copy", "")
        image_url = (data.get("asset_urls") or [None])[0] or data.get("image_url")

        # Obtém page token a partir do user token
        r = requests.get(
            f"{GRAPH_URL}/{self._fb_page_id}",
            params={"fields": "access_token", "access_token": self._ig_token},
            timeout=15,
        )
        page_token = r.json().get("access_token", self._ig_token)

        if image_url:
            r = requests.post(
                f"{GRAPH_URL}/{self._fb_page_id}/photos",
                data={"caption": copy, "url": image_url, "access_token": page_token},
                timeout=30,
            )
        else:
            r = requests.post(
                f"{GRAPH_URL}/{self._fb_page_id}/feed",
                data={"message": copy, "access_token": page_token},
                timeout=30,
            )
        post_id = r.json().get("id")
        if not post_id:
            raise RuntimeError(f"Facebook publish failed: {r.json().get('error', {}).get('message', r.json())}")
        logger.info(f"Facebook published: {post_id}")
        return post_id

    # ── Threads ────────────────────────────────────────────────────────────────

    def publish_threads(self, data: dict[str, Any]) -> str:
        """
        Publica no Threads @eozore.ai.

        Suporte: TEXT, IMAGE. Para threads sequenciais (série de posts),
        usa publish_thread_series().
        """
        copy      = data.get("copy", "")
        image_url = (data.get("asset_urls") or [None])[0] or data.get("image_url")

        post_data: dict[str, str] = {
            "media_type":   "TEXT" if not image_url else "IMAGE",
            "text":         copy,
            "access_token": self._th_token,
        }
        if image_url:
            post_data["image_url"] = image_url

        r = requests.post(f"{THREADS_URL}/me/threads", data=post_data, timeout=30)
        res = r.json()
        if "id" not in res:
            raise RuntimeError(f"Threads container failed: {res.get('error', {}).get('message', res)}")

        if not self._wait_threads_container(res["id"]):
            raise RuntimeError("Threads container processing timeout")

        pub = requests.post(
            f"{THREADS_URL}/me/threads_publish",
            data={"creation_id": res["id"], "access_token": self._th_token},
            timeout=30,
        )
        post_id = pub.json().get("id")
        if not post_id:
            raise RuntimeError(f"Threads publish failed: {pub.json().get('error', {}).get('message', pub.json())}")
        logger.info(f"Threads published: {post_id}")
        return post_id

    def publish_thread_series(self, posts: list[str]) -> list[str]:
        """
        Publica uma série de posts encadeados (thread sequencial).

        Cada post é publicado em sequência. O primeiro é independente;
        os demais são replies do anterior.

        Args:
            posts: lista de textos (cada item = 1 post individual).

        Returns:
            lista de post_ids publicados.
        """
        if not posts:
            return []

        published_ids: list[str] = []
        reply_to_id: str | None = None

        for i, text in enumerate(posts):
            post_data: dict[str, str] = {
                "media_type":   "TEXT",
                "text":         text,
                "access_token": self._th_token,
            }
            if reply_to_id:
                post_data["reply_to_id"] = reply_to_id

            r = requests.post(f"{THREADS_URL}/me/threads", data=post_data, timeout=30)
            res = r.json()
            if "id" not in res:
                logger.error(f"Threads series post {i+1} container failed: {res}")
                break

            if not self._wait_threads_container(res["id"]):
                logger.error(f"Threads series post {i+1} container timeout")
                break

            pub = requests.post(
                f"{THREADS_URL}/me/threads_publish",
                data={"creation_id": res["id"], "access_token": self._th_token},
                timeout=30,
            )
            post_id = pub.json().get("id")
            if not post_id:
                logger.error(f"Threads series post {i+1} publish failed: {pub.json()}")
                break

            logger.info(f"Threads series post {i+1}/{len(posts)} published: {post_id}")
            published_ids.append(post_id)
            reply_to_id = post_id

            # Pequena pausa entre posts para evitar rate limit
            if i < len(posts) - 1:
                time.sleep(2)

        return published_ids

    def _wait_threads_container(self, creation_id: str, timeout: int = 60) -> bool:
        start = time.time()
        delay = 2
        while time.time() - start < timeout:
            r = requests.get(
                f"{THREADS_URL}/{creation_id}",
                params={"fields": "status", "access_token": self._th_token}, timeout=15,
            )
            status = r.json().get("status")
            if status == "FINISHED":
                return True
            if status == "ERROR":
                logger.error(f"Threads container error: {r.json()}")
                return False
            time.sleep(delay)
            delay = min(delay * 1.5, 10)
        return False
