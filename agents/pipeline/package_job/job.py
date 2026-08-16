"""
package_job/job.py
==================
Geração do pacote editorial (roteiro + slides + thumbnails + copies) fora do
caminho HTTP síncrono.

Antes, /api/csm/package fazia tudo dentro de um único request: o navegador
segurava um fetch de 4 a 8 minutos que atravessava Next.js → cmo-agent →
Vertex AI. Fechar a aba, o timeout de 600s do serviço frontend, ou uma
reciclagem de instância do Cloud Run matavam a geração inteira — e como o
estado só era gravado quando a promise resolvia, não sobrava nada para
retomar.

Aqui o trabalho roda num Cloud Run Job (task-timeout de 1h) e cada etapa
concluída é persistida na sessão. O ReviewTab já fazia polling do Firestore;
agora esse polling mostra progresso real em vez de um spinner cego.

Fases:
  script      → scriptwriter + slide_designer + manifest HTML
  derivatives → thumbnails + copies + derivações omnicanal
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any, Optional

from google.api_core.exceptions import NotFound

logger = logging.getLogger("package_job")

# Campos que o frontend guarda num doc irmão por causa do teto de 1MB por
# documento do Firestore. Mantidos em sincronia com apps/web/src/lib/session.ts
# (HEAVY_DRAFT_FIELDS) — se divergirem, o draft volta a crescer sem limite.
HEAVY_DRAFT_FIELDS = ("manifestHtml", "thumbnails")

DOC_SIZE_BUDGET_BYTES = 900_000


class PackageJob:
    """Executa uma fase do pacote e persiste o resultado na sessão."""

    def __init__(
        self,
        db,                       # google.cloud.firestore.Client (sync)
        cmo_agent_url: str,
        internal_secret: str,
        request_timeout_s: int = 1500,
    ) -> None:
        self._db = db
        self._cmo_url = cmo_agent_url.rstrip("/")
        self._secret = (internal_secret or "").strip()
        self._timeout = request_timeout_s

    # ── Acesso à sessão ──────────────────────────────────────────────────────

    def _session_ref(self, session_id: str, tenant_id: Optional[str]):
        path = (
            f"tenants/{tenant_id}/sessions/{session_id}"
            if tenant_id else f"csm_sessions/{session_id}"
        )
        return self._db.document(path)

    def _artifacts_ref(self, session_id: str, tenant_id: Optional[str]):
        base = (
            f"tenants/{tenant_id}/sessions/{session_id}"
            if tenant_id else f"csm_sessions/{session_id}"
        )
        return self._db.document(f"{base}/artifacts/package")

    def _load_draft(self, session_id: str, tenant_id: Optional[str]) -> dict[str, Any]:
        snap = self._session_ref(session_id, tenant_id).get()
        if not snap.exists:
            raise RuntimeError(f"Sessão {session_id} não existe")
        return (snap.to_dict() or {}).get("draft") or {}

    def _patch_draft(
        self,
        session_id: str,
        tenant_id: Optional[str],
        patch: dict[str, Any],
    ) -> None:
        """
        Grava um patch no draft separando os campos pesados para o doc irmão.

        Usa merge por caminho de campo (draft.<campo>) para NÃO sobrescrever o
        que o usuário editou em paralelo — um `set({draft: {...}}, merge=True)`
        substituiria o mapa inteiro do draft.
        """
        light: dict[str, Any] = {}
        heavy: dict[str, Any] = {}
        for key, value in patch.items():
            (heavy if key in HEAVY_DRAFT_FIELDS else light)[key] = value

        if light:
            payload = {f"draft.{k}": v for k, v in light.items()}
            payload["updatedAt"] = int(time.time() * 1000)
            size = len(json.dumps(payload, default=str).encode("utf-8"))
            if size > DOC_SIZE_BUDGET_BYTES:
                raise RuntimeError(
                    f"Patch do draft com {size // 1024}KB excede o limite de 1MB do Firestore"
                )
            ref = self._session_ref(session_id, tenant_id)
            try:
                # update() interpreta o ponto como caminho de campo, que é o que
                # queremos: sobrescreve draft.manifestV2 sem tocar no resto do
                # draft. set() trataria "draft.manifestV2" como nome literal.
                ref.update(payload)
            except NotFound:
                # A sessão sumiu entre o enfileiramento e a execução (usuário
                # começou de novo, limpeza de dados). Recria em vez de derrubar
                # o job — o trabalho já foi pago junto ao Vertex.
                logger.warning("[package-job] sessão %s não existe; recriando", session_id)
                ref.set({"draft": light, "updatedAt": payload["updatedAt"]}, merge=True)

        if heavy:
            self._artifacts_ref(session_id, tenant_id).set(
                {**heavy, "updatedAt": int(time.time() * 1000)}, merge=True
            )

    def _checkpoint(
        self,
        session_id: str,
        tenant_id: Optional[str],
        stage: str,
        detail: str = "",
    ) -> None:
        """Progresso legível para a UI — sem isto o usuário vê só um spinner."""
        logger.info("[package-job] %s :: %s %s", session_id, stage, detail)
        try:
            self._patch_draft(session_id, tenant_id, {
                "packageStage": stage,
                "packageStageDetail": detail,
                "packageStageAt": int(time.time() * 1000),
            })
        except Exception as exc:  # checkpoint nunca deve derrubar o job
            logger.warning("[package-job] falha ao gravar checkpoint: %s", exc)

    # ── Chamada ao cmo-agent ─────────────────────────────────────────────────

    def _call_cmo(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._secret:
            headers["X-Internal-Auth"] = self._secret

        req = urllib.request.Request(
            f"{self._cmo_url}{path}", data=body, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise RuntimeError(f"cmo-agent {path} HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"cmo-agent inacessível: {exc.reason}") from exc

    # ── Renderização de imagens sociais ──────────────────────────────────────

    def _render_and_upload(self, html: str, size: tuple[int, int], name: str,
                           session_id: str, fb_title: str = "", fb_body: str = "") -> str | None:
        """HTML → PNG → GCS. Devolve URL pública, ou None se falhar."""
        try:
            from publisher_job.html_image_renderer import render_html_image
            from google.cloud import storage

            png = render_html_image(html, size[0], size[1],
                                    fallback_title=fb_title, fallback_body=fb_body)
            bucket_name = os.environ.get("GCS_BUCKET", "vazfy-417019-pipeline-media")
            blob_path = f"social/{session_id}/{name}.png"
            blob = storage.Client().bucket(bucket_name).blob(blob_path)
            blob.upload_from_string(png, content_type="image/png")
            return f"https://storage.googleapis.com/{bucket_name}/{blob_path}"
        except Exception as exc:
            logger.warning("[package-job] falha ao renderizar %s: %s", name, exc)
            return None

    def _render_social_images(self, repurposed: dict, session_id: str, series: str = "") -> dict:
        """
        Renderiza as imagens que faltavam para o Instagram aceitar os posts.

        Sem isto, três formatos eram gerados e descartados: o distribution_agent
        produz `imageHtml` para posts de imagem e LinkedIn, mas nada para
        carrossel (só heading/body) nem stories (só copy) — e ninguém no fluxo
        convertia HTML em PNG. O publisher espera `imageUrl` pronto.
        """
        from shared.social_images import (
            CAROUSEL_SIZE, FEED_SIZE, LINKEDIN_SIZE,
            carousel_slide_html, story_html, fallback_image_html,
        )
        if not isinstance(repurposed, dict):
            return repurposed

        rendered = 0

        # Posts de imagem e de LinkedIn: já vêm com imageHtml do agente.
        for key, size in (("imagePosts", FEED_SIZE), ("linkedinPosts", LINKEDIN_SIZE)):
            for i, item in enumerate(repurposed.get(key) or []):
                if not isinstance(item, dict) or item.get("imageUrl"):
                    continue
                html = item.get("imageHtml") or fallback_image_html(
                    item.get("title") or item.get("hook") or "", item.get("copy") or "", *size)
                url = self._render_and_upload(
                    html, size, f"{key}-{i+1}", session_id,
                    fb_title=item.get("title") or "", fb_body=item.get("copy") or "")
                if url:
                    item["imageUrl"] = url
                    rendered += 1

        # Carrossel: sem HTML nenhum — cada slide vira imagem via template.
        for c_idx, carousel in enumerate(repurposed.get("carousels") or []):
            if not isinstance(carousel, dict) or carousel.get("imageUrls"):
                continue
            slides = carousel.get("slides") or []
            urls: list[str] = []
            for s in slides:
                n = int(s.get("slideNumber") or len(urls) + 1)
                url = self._render_and_upload(
                    carousel_slide_html(s.get("heading") or "", s.get("body") or "",
                                        n, len(slides), series),
                    CAROUSEL_SIZE, f"carousel-{c_idx+1}-slide-{n}", session_id,
                    fb_title=s.get("heading") or "", fb_body=s.get("body") or "")
                if url:
                    urls.append(url)
            # O Instagram exige 2+ imagens para publicar como carrossel.
            if len(urls) >= 2:
                carousel["imageUrls"] = urls
                rendered += len(urls)
            else:
                logger.warning("[package-job] carrossel %d com só %d slide(s) renderizado(s) — ignorado",
                               c_idx + 1, len(urls))

        # Stories: idem, só copy + elemento interativo.
        for i, story in enumerate(repurposed.get("storiesIdeas") or []):
            if not isinstance(story, dict) or story.get("imageUrl"):
                continue
            url = self._render_and_upload(
                story_html(story.get("copy") or "", story.get("interactiveElement") or "",
                           story.get("angle") or ""),
                (1080, 1920), f"story-{i+1}", session_id,
                fb_title=story.get("angle") or "", fb_body=story.get("copy") or "")
            if url:
                story["imageUrl"] = url
                rendered += 1

        logger.info("[package-job] %d imagem(ns) social(is) renderizada(s)", rendered)
        return repurposed

    @staticmethod
    def _script_from_manifest(manifest: Any) -> str:
        segments = ((manifest or {}).get("youtube") or {}).get("segments") or []
        return "\n\n".join(s.get("script", "") for s in segments if s.get("script"))

    # ── Execução ─────────────────────────────────────────────────────────────

    def run(self, session_id: str, phase: str, tenant_id: Optional[str] = None) -> None:
        started = time.time()
        try:
            draft = self._load_draft(session_id, tenant_id)
            article = draft.get("generatedContent") or ""
            if len(article.strip()) < 100:
                raise RuntimeError("Artigo ausente ou curto demais na sessão")

            pauta = draft.get("pauta") or {}
            if not (pauta.get("titulo") or "").strip():
                raise RuntimeError("Pauta sem título na sessão")

            self._checkpoint(session_id, tenant_id, f"{phase}:iniciado",
                             "chamando agentes especialistas")

            category = draft.get("category") or "ml"
            language = draft.get("language") or "pt-BR"

            data = self._call_cmo("/package", {
                "pauta":          pauta,
                "articleContent": article,
                "category":       category,
                "language":       language,
                "sessionId":      session_id,
                "phase":          phase,
                **({"manifest": draft.get("manifestV2")} if phase != "script" else {}),
            })

            partial = list(data.get("partialErrors") or [])

            if phase == "script":
                manifest = data.get("manifest")
                script = self._script_from_manifest(manifest)
                ok = bool(script.strip())
                self._checkpoint(session_id, tenant_id, "script:persistindo",
                                 f"{len(script)} chars de roteiro")
                self._patch_draft(session_id, tenant_id, {
                    "manifestV2":    manifest,
                    "manifestHtml":  data.get("manifestHtml") or "",
                    "youtubeScript": script,
                    "packageStatus": "script_ready" if ok else "error",
                    "workflowStage": "script_ready" if ok else "error",
                    "packageError":  "; ".join(partial) if partial else
                                     ("" if ok else "Roteiro não foi gerado."),
                })
            else:
                # As derivações omnicanal (reels, shorts, carrosséis, stories)
                # vêm de outro agente. Falha aqui é parcial: thumbnails e copies
                # já valem revisão, então o pacote não é perdido inteiro.
                self._checkpoint(session_id, tenant_id, "derivatives:omnicanal",
                                 "gerando reels, shorts, carrosséis e stories")
                script = (draft.get("youtubeScript")
                          or self._script_from_manifest(draft.get("manifestV2")))
                repurposed: Any = None
                try:
                    repurposed = self._call_cmo("/repurpose", {
                        "title":         draft.get("suggestedTitle") or pauta.get("titulo"),
                        "slug":          draft.get("suggestedSlug") or "",
                        "content":       article,
                        "category":      category,
                        "language":      language,
                        "youtubeScript": script,
                    })
                except Exception as exc:
                    partial.append(f"repurpose: {exc}")
                    logger.warning("[package-job] repurpose falhou (não-fatal): %s", exc)

                # Renderiza aqui, na geração, e não na publicação: assim as
                # imagens aparecem na aba de revisão e podem ser reprovadas
                # ANTES de ir ao ar — que é o ponto de ter uma etapa de revisão.
                if repurposed:
                    self._checkpoint(session_id, tenant_id, "derivatives:imagens",
                                     "renderizando carrossel, stories e posts de imagem")
                    try:
                        repurposed = self._render_social_images(
                            repurposed, session_id, str(pauta.get("serie") or ""))
                    except Exception as exc:
                        partial.append(f"imagens: {exc}")
                        logger.warning("[package-job] render de imagens falhou (não-fatal): %s", exc)

                self._checkpoint(session_id, tenant_id, "derivatives:persistindo", "")
                self._patch_draft(session_id, tenant_id, {
                    "thumbnails":       data.get("thumbnails"),
                    "specialistCopies": data.get("copies"),
                    "repurposedData":   repurposed,
                    "packageStatus":    "ready",
                    "workflowStage":    "package_ready",
                    "packageError":     "; ".join(partial) if partial else "",
                })

            elapsed = round(time.time() - started, 1)
            self._checkpoint(session_id, tenant_id, f"{phase}:concluido", f"{elapsed}s")
            logger.info("[package-job] concluído session=%s phase=%s em %ss",
                        session_id, phase, elapsed)

        except Exception as exc:
            # O erro precisa chegar na UI. Antes, uma falha aqui só existia nos
            # logs do Cloud Run e o usuário ficava com o spinner girando.
            logger.exception("[package-job] falhou session=%s phase=%s", session_id, phase)
            try:
                self._patch_draft(session_id, tenant_id, {
                    "packageStatus": "error",
                    "workflowStage": "error",
                    "packageError":  str(exc)[:500],
                    "packageStage":  f"{phase}:erro",
                })
            except Exception:
                logger.exception("[package-job] não conseguiu nem gravar o erro na sessão")
            raise
