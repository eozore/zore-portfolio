"""
agents/pipeline/heygen_callback/app.py
==========================================
HeyGen Callback Handler — Cloud Run Service (FastAPI).

Recebe dois tipos de webhook HeyGen:
  POST /heygen-callback       — callback do Lipsync API (legado, mantido por compatibilidade)
  POST /heygen-video-callback — callback do Video Generation API v2/v3 (novo fluxo sem delay)

Lógica crítica (ambos os endpoints):
  - Existe UM target: horizontal. O vertical é um recorte 9:16 feito depois,
    com FFmpeg, sem nova geração de avatar.
  - Publica avatar_completed quando todos os segmentos horizontais resolvem
    (completed OU failed) e pelo menos um tem vídeo.
  - Falha de segmento não interrompe os outros e NÃO pula a reavaliação do
    portão — pular era o que travava o projeto em pending_callback.
  - Sempre retorna HTTP 200 para evitar retry automático do HeyGen.
  - O callback_id é "{project_id}__{orientation}__{seg_id}".
"""

import asyncio
import logging
import os
import time
from typing import Optional

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from google.cloud import storage
from pydantic import BaseModel

from shared.firestore_client import FirestoreClient
from shared.models import AvatarCompletedMsg
from shared.pubsub_client import PubSubClient, get_secret

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="HeyGen Callback Handler")

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "vazfy-417019")
GCS_BUCKET     = os.environ.get("GCS_BUCKET", "vazfy-417019-pipeline-media")
TENANT_ID      = os.environ.get("TENANT_ID", "default")

AVATAR_COMPLETED_TOPIC = "content-pipeline.avatar-completed"

_firestore: Optional[FirestoreClient] = None
_pubsub: Optional[PubSubClient]       = None
_gcs: Optional[storage.Client]        = None
_callback_token: Optional[str]        = None


class HeyGenVideoCallbackPayload(BaseModel):
    """Payload do webhook do Video Generation API (callback_id = project_id__orientation)."""
    event_type: Optional[str] = None   # "avatar_video.success" | "avatar_video.fail"
    video_id:   Optional[str] = None
    callback_id: Optional[str] = None  # "{project_id}__{orientation}"
    video_url:  Optional[str] = None
    error:      Optional[str] = None
    status:     Optional[str] = None   # "completed" | "failed"


# Nomes alternativos por campo, em ordem de preferência.
#
# A especificação OpenAPI do v3 documenta `callback_url` e `callback_id`, mas
# NÃO a forma do payload entregue. Amarrar o handler a um nome exato é apostar:
# se o v3 chamar a URL de `url` em vez de `video_url`, o modelo Pydantic
# descarta o campo, o segmento é marcado sem vídeo e a produção morre depois de
# o crédito já ter sido gasto — sem erro nenhum no log.
_ALIASES: dict[str, tuple[str, ...]] = {
    "video_url":   ("video_url", "url", "video", "output_url", "download_url"),
    "video_id":    ("video_id", "id"),
    "callback_id": ("callback_id", "custom_id"),
    "error":       ("error", "error_message", "message"),
    "status":      ("status", "state"),
    "event_type":  ("event_type", "event", "type"),
}

# O v3 pode aninhar o conteúdo do evento. Procuramos nestes envelopes também.
_ENVELOPES = ("event_data", "data", "payload")


def _achatar(corpo: dict) -> dict:
    """Junta o nível raiz com o envelope de evento, se houver."""
    plano = dict(corpo)
    for envelope in _ENVELOPES:
        aninhado = corpo.get(envelope)
        if isinstance(aninhado, dict):
            # O aninhado tem precedência: é o conteúdo específico do evento.
            plano.update(aninhado)
    return plano


def extrair_campos(corpo: dict) -> HeyGenVideoCallbackPayload:
    """
    Normaliza o corpo do webhook, aceitando v2 e v3.

    Puro de propósito: é a peça que precisa de teste, porque a única forma de
    descobrir que ela errou em produção é um projeto travado em
    `pending_callback` com o crédito já consumido.
    """
    plano = _achatar(corpo)
    valores: dict[str, Optional[str]] = {}
    for campo, nomes in _ALIASES.items():
        for nome in nomes:
            v = plano.get(nome)
            if isinstance(v, str) and v.strip():
                valores[campo] = v
                break
        else:
            valores[campo] = None
    return HeyGenVideoCallbackPayload(**valores)


class HeyGenLipsyncCallbackPayload(BaseModel):
    """Payload do webhook do Lipsync API (legado)."""
    lipsync_id: Optional[str] = None
    status:     Optional[str] = None
    video_url:  Optional[str] = None
    error:      Optional[str] = None


class CallbackResponse(BaseModel):
    ok: bool
    message: Optional[str] = None


@app.on_event("startup")
async def startup() -> None:
    global _firestore, _pubsub, _gcs, _callback_token
    _firestore = FirestoreClient(GCP_PROJECT_ID)
    _pubsub    = PubSubClient(GCP_PROJECT_ID)
    _gcs       = storage.Client()
    try:
        _callback_token = get_secret("heygen-callback-token", GCP_PROJECT_ID)
    except Exception:
        logger.warning("[HeyGenCallback] Token não encontrado — autenticação desabilitada em dev.")
        _callback_token = None
    logger.info("[HeyGenCallback] Serviço iniciado. project=%s", GCP_PROJECT_ID)


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}


@app.post("/heygen-video-callback", response_model=CallbackResponse)
async def heygen_video_callback(
    request: Request,
    token: Optional[str] = None,
    x_heygen_token: Optional[str] = Header(default=None, alias="X-HeyGen-Token"),
) -> CallbackResponse:
    """
    Callback do Video Generation API v2/v3.

    BUG2 fix: callback_id agora é "{project_id}__{target}__{seg_id}".
    Cada segmento individual chega aqui separadamente.
    Quando TODOS os segmentos de AMBOS os targets completarem → publica avatar_completed.

    Autenticação: token na QUERY STRING, não header. O HeyGen não suporta
    header customizado em webhook — ele só faz POST na URL exata que você
    configurou em callback_url. Um header de app não protege nada se o Cloud
    Run também exigir IAM na frente: o HeyGen não tem como enviar OIDC do
    Google, então --no-allow-unauthenticated bloqueia 100% dos callbacks
    antes mesmo de chegar aqui — foi exatamente isso que travou os primeiros
    4 projetos de vídeo em produção, já com créditos HeyGen consumidos.
    """
    if _callback_token and token != _callback_token and x_heygen_token != _callback_token:
        raise HTTPException(status_code=401, detail="Token inválido")

    try:
        corpo = await request.json()
    except Exception:
        corpo = {}
    if not isinstance(corpo, dict):
        corpo = {}

    # Corpo cru no log: a forma do webhook do v3 não está documentada, e é o
    # primeiro callback real que vai revelá-la. Truncado para não despejar um
    # payload grande a cada segmento.
    logger.info("[HeyGenCallback] Corpo do webhook: %s", str(corpo)[:600])

    payload = extrair_campos(corpo)

    status = payload.status or (
        "completed" if payload.event_type == "avatar_video.success"
        else "failed" if payload.event_type == "avatar_video.fail"
        else "unknown"
    )

    callback_id = payload.callback_id or ""
    video_url   = payload.video_url
    video_id    = payload.video_id

    logger.info(
        "[HeyGenCallback] Video callback: callback_id=%s status=%s video_id=%s",
        callback_id, status, video_id,
    )

    # BUG2 fix: callback_id formato "{project_id}__{target}__{seg_id}"
    parts = callback_id.split("__")
    if len(parts) < 2:
        logger.warning("[HeyGenCallback] callback_id sem formato esperado: %s", callback_id)
        return CallbackResponse(ok=False, message="callback_id inválido")

    project_id  = parts[0]
    orientation = parts[1]   # "horizontal" | "vertical"
    seg_id      = parts[2] if len(parts) >= 3 else None

    return await _process_segment_result(
        project_id=project_id,
        orientation=orientation,
        seg_id=seg_id,
        status=status,
        video_url=video_url,
        error=payload.error,
    )


@app.post("/heygen-callback", response_model=CallbackResponse)
async def heygen_lipsync_callback(
    payload: HeyGenLipsyncCallbackPayload,
    token: Optional[str] = None,
    x_heygen_token: Optional[str] = Header(default=None, alias="X-HeyGen-Token"),
) -> CallbackResponse:
    """
    Callback do Lipsync API (mantido para compatibilidade).
    Também recebe callbacks do Video Generation API que usem este endpoint.
    """
    if _callback_token and token != _callback_token and x_heygen_token != _callback_token:
        raise HTTPException(status_code=401, detail="Token inválido")

    lipsync_id = payload.lipsync_id or ""
    status     = payload.status or "unknown"

    logger.info("[HeyGenCallback] Lipsync/video callback: id=%s status=%s", lipsync_id, status)

    # Tentar resolver via Firestore collection_group
    result = await _firestore.resolve_lipsync_to_project(lipsync_id)
    if not result:
        logger.warning("[HeyGenCallback] ID não encontrado: %s", lipsync_id)
        return CallbackResponse(ok=False, message=f"ID {lipsync_id} não encontrado")

    project_id, orientation = result

    return await _process_segment_result(
        project_id=project_id,
        orientation=orientation,
        seg_id=None,  # legado: sem seg_id
        status=status,
        video_url=payload.video_url,
        error=payload.error,
    )


async def _process_segment_result(
    project_id: str,
    orientation: str,
    seg_id: Optional[str],
    status: str,
    video_url: Optional[str],
    error: Optional[str],
) -> CallbackResponse:
    """
    BUG2 fix: processa o resultado de geração de 1 segmento individual.

    Lógica:
      1. Localiza o segmento em segment_videos.{orientation}[i] pelo seg_id
      2. Se completed: baixa vídeo, salva no GCS, atualiza status do segmento
      3. Se failed: marca o segmento como failed (não cancela os outros)
      4. Verifica se TODOS os segmentos de AMBOS os targets completaram
      5. Se sim: monta listas e publica AvatarCompletedMsg
    """

    # Falha do segmento
    if status == "failed":
        logger.error(
            "[HeyGenCallback] Segmento FALHOU: project=%s orientation=%s seg=%s erro=%s",
            project_id, orientation, seg_id, error,
        )
        if not seg_id:
            # Fallback legado: marca o stage inteiro como erro
            await _firestore.update_stage(project_id, "avatar", {
                "status": "error",
                "error_message": f"HeyGen falhou para {orientation}: {error}",
                "error_type": "transient",
            })
            return CallbackResponse(ok=False, message="Falha sem seg_id")

        await _update_segment_status(project_id, orientation, seg_id, "failed", None)
        await _firestore.update_stage(project_id, "avatar", {
            "last_error": f"{seg_id}: {error}"[:400],
        })
        # Reavalia o portão TAMBÉM na falha. A versão anterior retornava aqui,
        # então um segmento que falhasse por último deixava o projeto parado em
        # pending_callback para sempre — mesmo com todos os outros prontos.
        return await _check_and_publish_if_complete(project_id)

    # Sucesso do segmento
    if status == "completed" and video_url:
        # Nome do arquivo no GCS inclui seg_id para unicidade
        suffix = f"_{seg_id}" if seg_id else f"_{orientation}"
        gcs_path = await _download_and_store_video(
            project_id=project_id,
            orientation=orientation,
            video_url=video_url,
            suffix=suffix,
        )
        if seg_id:
            await _update_segment_status(project_id, orientation, seg_id, "completed", gcs_path)
        else:
            # Fallback legado (sem seg_id): compatibilidade com lipsync_jobs
            await _firestore.update_stage(project_id, "avatar", {
                f"lipsync_jobs.{orientation}.status": "completed",
                f"lipsync_jobs.{orientation}.video_url": gcs_path,
            })
        logger.info("[HeyGenCallback] Segmento OK: seg=%s gcs=%s", seg_id, gcs_path)

    # Verifica se todos os segmentos completaram
    return await _check_and_publish_if_complete(project_id)


async def _update_segment_status(
    project_id: str,
    orientation: str,
    seg_id: str,
    new_status: str,
    video_url: Optional[str],
) -> None:
    """Atualiza o status de um segmento individual no Firestore."""
    project        = await _firestore.get_project(project_id)
    segment_videos = project["stages"]["avatar"].get("segment_videos", {})
    segs           = segment_videos.get(orientation, [])

    for seg in segs:
        if seg.get("seg_id") == seg_id:
            seg["status"]    = new_status
            seg["video_url"] = video_url
            break

    await _firestore.update_stage(project_id, "avatar", {
        f"segment_videos.{orientation}": segs,
    })


async def _check_and_publish_if_complete(project_id: str) -> CallbackResponse:
    """
    Libera a edição quando todos os segmentos de avatar resolveram.

    Só existe UM target: horizontal. A peça vertical é um recorte 9:16 deste
    mesmo clipe, produzido depois pelo vertical_cut_job. O portão anterior
    exigia horizontal E vertical prontos e, como o HeyGen recusa a segunda
    geração quando o crédito acaba — sem sequer registrar o callback_id, então
    sem webhook nenhum —, o horizontal já pronto ficava preso atrás de um
    vertical que nunca ia chegar.

    Falha parcial não bloqueia: segmentos que voltaram são publicados e o
    video_editor recusa explicitamente a montagem se faltar algum, com o id do
    segmento no erro. Falhar com "faltou yt-05" é melhor que travar em silêncio.
    """
    project        = await _firestore.get_project(project_id)
    avatar_stage   = project["stages"]["avatar"]
    segment_videos = avatar_stage.get("segment_videos", {})
    h_segs         = segment_videos.get("horizontal", [])

    if not h_segs:
        logger.warning("[HeyGenCallback] %s sem segmentos horizontais.", project_id)
        return CallbackResponse(ok=True, message="Sem segmentos para resolver")

    pending = [s for s in h_segs if s.get("status") not in ("completed", "failed")]
    if pending:
        done = len(h_segs) - len(pending)
        logger.info(
            "[HeyGenCallback] Aguardando segmentos: %d/%d resolvidos, project=%s",
            done, len(h_segs), project_id,
        )
        return CallbackResponse(ok=True, message="Aguardando segmentos restantes")

    ok_segs = [s for s in h_segs if s.get("status") == "completed" and s.get("video_url")]
    failed  = [s.get("seg_id") for s in h_segs if s.get("status") == "failed"]

    if not ok_segs:
        detail = avatar_stage.get("last_error") or "todos os segmentos falharam"
        logger.error("[HeyGenCallback] Nenhum avatar gerado para %s: %s", project_id, detail)
        await _firestore.update_stage(project_id, "avatar", {
            "status": "error",
            "error_message": f"HeyGen não gerou nenhum segmento — {detail}",
            "error_type": "permanent",
        })
        return CallbackResponse(ok=False, message="Todos os segmentos falharam")

    if failed:
        logger.error(
            "[HeyGenCallback] %s: %d segmentos falharam (%s). Seguindo com %d — "
            "o editor vai recusar a montagem e nomear o que faltou.",
            project_id, len(failed), ", ".join(map(str, failed)), len(ok_segs),
        )

    logger.info(
        "[HeyGenCallback] %s: %d clipes de avatar prontos. Publicando avatar_completed.",
        project_id, len(ok_segs),
    )

    _pubsub.publish(AVATAR_COMPLETED_TOPIC, AvatarCompletedMsg(
        project_id=project_id,
        horizontal_video_paths=[s["video_url"] for s in ok_segs],
        vertical_video_paths=[],
        segment_ids=[s["seg_id"] for s in ok_segs],
        vertical_segment_ids=[],
        duration_seconds=0.0,
        total_cost_usd=0.0,
    ))
    await _firestore.update_stage(project_id, "avatar", {
        "status": "completed" if not failed else "completed_partial",
        "completed_at": int(time.time()),
        "failed_segments": failed,
    })
    return CallbackResponse(ok=True, message="avatar_completed publicado")


async def _download_and_store_video(
    project_id: str,
    orientation: str,
    video_url: str,
    suffix: str = "",
) -> str:
    """Baixa vídeo da URL HeyGen e armazena no GCS."""
    gcs_path     = f"projects/{project_id}/avatar{suffix}.mp4"
    full_gcs_uri = f"gs://{GCS_BUCKET}/{gcs_path}"

    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.get(video_url)
        resp.raise_for_status()

    video_bytes = resp.content
    bucket = _gcs.bucket(GCS_BUCKET)
    blob   = bucket.blob(gcs_path)
    loop   = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: blob.upload_from_string(video_bytes, content_type="video/mp4"),
    )
    logger.info(
        "[HeyGenCallback] Armazenado: %s (%d bytes)", full_gcs_uri, len(video_bytes)
    )
    return full_gcs_uri
