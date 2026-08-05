# -*- coding: utf-8 -*-
"""
publisher_job/linkedin_client.py
=================================
Publica posts no perfil pessoal de Victor Zoré no LinkedIn.

Diferença crítica em relação ao ainewz:
  - ainewz: author = urn:li:organization:104296536  (página de empresa)
  - éozoré: author = urn:li:person:ArvptA8OhR       (perfil pessoal)

Suporte:
  - Texto puro
  - Texto + imagem (upload nativo LinkedIn)
  - Poll

Referência: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api
"""

import logging
import time
from typing import Any

import requests

logger = logging.getLogger("publisher_job.linkedin")

LINKEDIN_API = "https://api.linkedin.com/rest"
API_VERSION  = "202601"


class LinkedInClient:
    """
    Publica no perfil pessoal do LinkedIn via Posts API (REST).

    Args:
        access_token: Bearer token OAuth 2.0 do perfil pessoal.
        person_id:    sub/person ID do usuário (ex: "ArvptA8OhR").
    """

    def __init__(self, access_token: str, person_id: str) -> None:
        self._token      = access_token
        self._person_urn = f"urn:li:person:{person_id}"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization":              f"Bearer {self._token}",
            "Content-Type":               "application/json",
            "LinkedIn-Version":           API_VERSION,
            "X-Restli-Protocol-Version":  "2.0.0",
        }

    # ── Publicação principal ───────────────────────────────────────────────────

    def publish(self, data: dict[str, Any]) -> str:
        """
        Publica post no LinkedIn.

        Args:
            data: dict com chaves:
                - copy (str): texto do post
                - image_url (str | None): URL pública da imagem
                - format (str): 'poll' para enquete, qualquer outro = imagem/texto
                - poll_data (dict | None): {'question': str, 'options': list[str]}

        Returns:
            post_id (str) em caso de sucesso.

        Raises:
            RuntimeError: falha na API.
        """
        fmt = data.get("format", "image")
        if fmt == "poll":
            return self._post_poll(data)
        image_url = (data.get("asset_urls") or [None])[0] or data.get("image_url")
        if image_url:
            return self._post_image(data["copy"], image_url)
        return self._post_text(data["copy"])

    # ── Texto puro ─────────────────────────────────────────────────────────────

    def _post_text(self, copy: str) -> str:
        body = {
            "author":        self._person_urn,
            "commentary":    copy,
            "visibility":    "PUBLIC",
            "distribution":  {"feedDistribution": "MAIN_FEED"},
            "lifecycleState": "PUBLISHED",
        }
        r = requests.post(f"{LINKEDIN_API}/posts", headers=self._headers(), json=body, timeout=30)
        return self._extract_post_id(r, "text")

    # ── Texto + imagem ─────────────────────────────────────────────────────────

    def _post_image(self, copy: str, image_url: str) -> str:
        # 1. Inicializa upload
        init_body = {"initializeUploadRequest": {"owner": self._person_urn}}
        init = requests.post(
            f"{LINKEDIN_API}/images?action=initializeUpload",
            headers=self._headers(), json=init_body, timeout=30,
        )
        if init.status_code not in (200, 201):
            logger.warning(f"LinkedIn image init {init.status_code} — falling back to text post")
            return self._post_text(copy)

        val = init.json().get("value", {})
        upload_url = val.get("uploadUrl", "")
        image_urn  = val.get("image", "")
        if not upload_url or not image_urn:
            logger.warning("LinkedIn image init missing uploadUrl/image — falling back to text")
            return self._post_text(copy)

        # 2. Baixa imagem e faz upload binário
        img_r = requests.get(image_url, timeout=30)
        if img_r.status_code != 200:
            logger.warning(f"Failed to download image {image_url} — falling back to text")
            return self._post_text(copy)

        up = requests.put(
            upload_url,
            headers={"Authorization": f"Bearer {self._token}", "Content-Type": "application/octet-stream"},
            data=img_r.content, timeout=60,
        )
        if up.status_code not in (200, 201):
            logger.warning(f"LinkedIn image upload {up.status_code} — falling back to text")
            return self._post_text(copy)

        # 3. Cria o post com a imagem
        body = {
            "author":        self._person_urn,
            "commentary":    copy,
            "visibility":    "PUBLIC",
            "distribution":  {"feedDistribution": "MAIN_FEED"},
            "content":       {"media": {"id": image_urn}},
            "lifecycleState": "PUBLISHED",
        }
        r = requests.post(f"{LINKEDIN_API}/posts", headers=self._headers(), json=body, timeout=30)
        return self._extract_post_id(r, "image")

    # ── Poll ───────────────────────────────────────────────────────────────────

    def _post_poll(self, data: dict[str, Any]) -> str:
        poll = data.get("poll_data") or {}
        body = {
            "author":        self._person_urn,
            "commentary":    data.get("copy", ""),
            "visibility":    "PUBLIC",
            "distribution":  {"feedDistribution": "MAIN_FEED"},
            "content": {
                "poll": {
                    "question": poll.get("question", data.get("copy", "")[:140]),
                    "options":  [{"text": o} for o in poll.get("options", ["Sim", "Não"])[:4]],
                    "settings": {"duration": "SEVEN_DAYS"},
                }
            },
            "lifecycleState": "PUBLISHED",
        }
        r = requests.post(f"{LINKEDIN_API}/posts", headers=self._headers(), json=body, timeout=30)
        return self._extract_post_id(r, "poll")

    # ── Primeiro comentário (link do artigo) ───────────────────────────────────

    def post_first_comment(self, post_urn: str, comment_text: str) -> str | None:
        """Posta primeiro comentário com link do artigo. Não levanta exceção."""
        if not post_urn or not comment_text:
            return None
        if not post_urn.startswith("urn:"):
            post_urn = f"urn:li:share:{post_urn}"
        body = {
            "actor":   self._person_urn,
            "object":  post_urn,
            "message": {"text": comment_text},
        }
        try:
            r = requests.post(
                f"{LINKEDIN_API}/socialActions/{post_urn}/comments",
                headers=self._headers(), json=body, timeout=30,
            )
            if r.status_code in (200, 201):
                cid = r.json().get("id", "")
                logger.info(f"LinkedIn first comment posted: {cid}")
                return cid
            logger.warning(f"LinkedIn first_comment {r.status_code}: {r.text[:100]}")
        except Exception as e:
            logger.warning(f"LinkedIn first_comment exception: {e}")
        return None

    # ── Helper ─────────────────────────────────────────────────────────────────

    def _extract_post_id(self, response: requests.Response, kind: str) -> str:
        if response.status_code not in (200, 201):
            raise RuntimeError(
                f"LinkedIn {kind} post failed {response.status_code}: {response.text[:300]}"
            )
        post_id = response.headers.get("x-restli-id", "")
        if not post_id:
            try:
                post_id = response.json().get("id", "")
            except Exception:
                pass
        if not post_id:
            post_id = f"li-{kind}-{int(time.time())}"
        logger.info(f"LinkedIn {kind} published: {post_id}")
        return post_id
