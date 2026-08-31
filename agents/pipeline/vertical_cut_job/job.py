"""
agents/pipeline/vertical_cut_job/job.py
========================================
VerticalCutJob — deriva a peça vertical (Reel / Short) do vídeo do YouTube.

O corte vertical NÃO é uma produção nova. É um recorte do que já existe:

  • Segmento de avatar → crop central 9:16 do clipe horizontal já gerado.
    Nenhuma chamada ao HeyGen. Nenhum crédito consumido.
  • Segmento de ilustração → uma ilustração NOVA, desenhada para 9:16, com
    exatamente o MESMO áudio TTS do segmento horizontal de origem.
    Nenhuma chamada ao ElevenLabs.

Antes, cada Reel e cada Short era um `content_project` independente, com
roteiro, TTS, avatar e edição próprios. Três peças curtas custavam três
produções completas, o texto não tinha relação com o vídeo longo, e o avatar
era gerado duas vezes com a mesma fala — uma por orientação.

O job só roda sob demanda, depois que o dono do canal assistiu ao vídeo do
YouTube e liberou o pacote. Se o vídeo longo não estiver pronto, ele recusa.
"""

import asyncio
import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Optional

from google.cloud import storage

from shared.captions import (
    Cue,
    group_into_cues,
    words_from_alignment,
    words_from_text_estimated,
    write_ass,
)
from shared.compose import (
    ComposeError,
    burn_subtitles,
    concat_clips,
    crop_to_vertical,
    probe_duration,
    render_slide_clip,
)
from shared.firestore_client import FirestoreClient
from shared.models import Manifest, Segment, VideoReadyMsg
from shared.pubsub_client import PubSubClient

logger = logging.getLogger(__name__)

VIDEO_READY_TOPIC = "content-pipeline.video-ready"

# Enquadramento do crop: 0.5 = janela 9:16 centrada. O HeyGen entrega o
# apresentador no centro do frame 16:9, mas isso muda por preset de avatar —
# daí ser configurável sem redeploy de código.
CROP_X_RATIO = float(os.environ.get("HEYGEN_AVATAR_CROP_X_RATIO", "0.5"))

# Legendas queimadas. Ligadas por padrão: a maior parte do público de Reels e
# Shorts assiste sem som, e uma peça vertical sem legenda perde o espectador
# nos primeiros segundos. Desligável por env sem redeploy de código.
BURN_CAPTIONS = os.environ.get("VERTICAL_BURN_CAPTIONS", "true").strip().lower() != "false"


class VerticalCutJob:
    def __init__(
        self,
        firestore: FirestoreClient,
        pubsub: PubSubClient,
        gcs_bucket: str,
        tenant_id: str = "default",
    ) -> None:
        self.firestore  = firestore
        self.pubsub     = pubsub
        self.gcs_bucket = gcs_bucket
        self.gcs        = storage.Client()

    async def run(self, project_id: str, channels: Optional[list[str]] = None) -> str:
        """
        Produz final_vertical.mp4 a partir dos artefatos do vídeo horizontal.

        Args:
            project_id: projeto do vídeo longo, já com o estágio editor pronto.
            channels:   canais de destino da peça (instagram_reel, youtube_short).

        Returns:
            gs:// URI do vídeo vertical.
        """
        project = await self.firestore.get_project(project_id)
        editor  = project.get("stages", {}).get("editor", {})

        if editor.get("status") != "completed":
            raise ComposeError(
                f"{project_id}: o vídeo horizontal ainda não está pronto "
                f"(editor={editor.get('status')}). O corte vertical sai dele."
            )

        clips_prefix = editor.get("clips_prefix")
        if not clips_prefix:
            raise ComposeError(
                f"{project_id}: sem clips_prefix — este projeto foi montado por "
                "uma versão anterior do editor, que não guardava os clipes por "
                "segmento. Reprocesse o estágio editor antes de cortar."
            )

        await self.firestore.update_stage(project_id, "vertical_cut", {
            "status": "running",
            "started_at": int(time.time()),
        })

        try:
            manifest = await self._load_manifest(project_id)
            res      = manifest.vertical_resolution()
            width, height = res["width"], res["height"]

            cut_items = [Segment.from_raw(s) for s in manifest._get_raw_segments("vertical")]
            if not cut_items:
                raise ComposeError(
                    f"{project_id}: manifesto sem vertical_cut — não há corte definido."
                )

            audio_map = (
                project.get("stages", {}).get("avatar", {})
                .get("slide_audio_paths", {})
                .get("horizontal", [])
            )

            with tempfile.TemporaryDirectory(prefix=f"vcut_{project_id}_") as work_dir:
                work = Path(work_dir)
                manifest_html = await self._download(
                    project["manifest_url"], work / "manifest.html"
                )

                clips, timeline = await self._build_clips(
                    project_id    = project_id,
                    manifest      = manifest,
                    cut_items     = cut_items,
                    clips_prefix  = clips_prefix,
                    audio_uris    = audio_map,
                    manifest_html = manifest_html,
                    work          = work,
                    width         = width,
                    height        = height,
                )

                composed = work / "composed_vertical.mp4"
                await asyncio.to_thread(
                    concat_clips, [c["path"] for c in clips], composed, width, height
                )

                # Legendas por último: os tempos das cues são absolutos na
                # linha do tempo da peça montada, então queimar antes do
                # concat deslocaria tudo a partir do segundo clipe.
                final_path = work / "final_vertical.mp4"
                cues = self._collect_cues(clips)
                if BURN_CAPTIONS and cues:
                    ass_path = work / "captions.ass"
                    await asyncio.to_thread(
                        write_ass, cues, ass_path, width, height
                    )
                    await asyncio.to_thread(
                        burn_subtitles, composed, ass_path, final_path, width, height
                    )
                    await self._upload(
                        ass_path, f"projects/{project_id}/captions.ass", "text/plain; charset=utf-8"
                    )
                else:
                    if BURN_CAPTIONS:
                        logger.warning(
                            "[VerticalCutJob] %s: sem palavras cronometradas — peça "
                            "vertical sai SEM legenda.", project_id,
                        )
                    composed.rename(final_path)

                duration = probe_duration(final_path)

                if duration > 180:
                    logger.warning(
                        "[VerticalCutJob] %s: corte de %.0fs — acima do limite de "
                        "Reels/Shorts. Publica, mas o roteiro deveria ter cortado antes.",
                        project_id, duration,
                    )

                final_uri = await self._upload(
                    final_path, f"projects/{project_id}/final_vertical.mp4", "video/mp4"
                )
                plan_path = work / "vertical_timeline.json"
                plan_path.write_text(
                    json.dumps(
                        {"project_id": project_id, "duration_s": round(duration, 2),
                         "resolution": res, "segments": timeline},
                        ensure_ascii=False, indent=2,
                    ),
                    encoding="utf-8",
                )
                await self._upload(
                    plan_path, f"projects/{project_id}/vertical_timeline.json",
                    "application/json",
                )

            logger.info(
                "[VerticalCutJob] %s: peça vertical de %.1fs a partir de %d segmentos "
                "do vídeo longo, sem nenhuma nova geração de avatar.",
                project_id, duration, len(timeline),
            )

            await self.firestore.update_stage(project_id, "vertical_cut", {
                "status":       "completed",
                "completed_at": int(time.time()),
                "vertical_url": final_uri,
                "duration_s":   round(duration, 2),
                "timeline":     timeline,
            })
            await self.firestore.update_stage(project_id, "editor", {
                "vertical_url": final_uri,
            })

            if channels:
                # A peça curta vai para a FILA, não para publicação imediata.
                #
                # Antes disparava `trigger="immediate"` e ia ao ar em minutos:
                # o Reel e o Short eram os únicos formatos que nunca apareciam
                # na lista de conteúdos, então não dava para revisar, nem para
                # distribuir no tempo junto com o resto da semana. E um Reel
                # publicado na hora concorre com o próprio vídeo longo, que
                # acabou de sair.
                await self._enfileirar_curto(
                    project_id, final_uri, channels, project, round(duration, 2),
                )

            return final_uri

        except Exception as exc:
            logger.exception("[VerticalCutJob] Erro para %s: %s", project_id, exc)
            await self.firestore.update_stage(project_id, "vertical_cut", {
                "status": "error",
                "error_message": str(exc)[:900],
                "error_type": "permanent" if isinstance(exc, ComposeError) else "transient",
            })
            raise

    # ──────────────────────────────────────────────────────────────────────────

    async def _enfileirar_curto(
        self, project_id: str, video_uri: str, channels: list[str],
        project: dict, duracao_s: float,
    ) -> None:
        """
        Põe o Short/Reel na `social_queue`, num horário que não colida.

        Um documento por canal: o publisher da fila trata Short e Reel como
        peças independentes, e é isso que permite soltar um sem o outro — que
        é exatamente o que faltou quando o Reel do Instagram precisou esperar
        o vídeo longo virar público.
        """
        from datetime import datetime, timedelta, timezone

        ocupados = await self.firestore.horarios_ocupados()
        base     = datetime.now(timezone.utc)

        # O curto sai DEPOIS do vídeo longo, nunca junto: ele existe para
        # levar tráfego a um vídeo que já está no ar.
        destino_por_canal = {
            "youtube_short":  ("youtube_shorts", "shorts"),
            "instagram_reel": ("instagram",      "reel"),
        }
        titulo = str(project.get("short_frase") or project.get("title") or "")[:120]

        for canal in channels:
            par = destino_por_canal.get(canal)
            if not par:
                continue
            plataforma, formato = par

            quando = None
            for dia in range(1, 8):
                for hora_brt in (9, 12, 18, 15, 20):
                    alvo = (base + timedelta(days=dia)).replace(
                        hour=0, minute=0, second=0, microsecond=0
                    ) + timedelta(hours=hora_brt + 3)
                    chave = (plataforma, alvo.isoformat()[:13])
                    if chave not in ocupados:
                        ocupados.add(chave)
                        quando = alvo.isoformat()
                        break
                if quando:
                    break
            if not quando:
                quando = (base + timedelta(days=1)).isoformat()

            await self.firestore.enfileirar_curto({
                "status":            "planned",
                "platform":          plataforma,
                "format":            formato,
                "title":             titulo,
                "copy":              "",       # o publisher monta com gancho e hashtags
                "asset_urls":        [video_uri],
                "video_url":         video_uri,
                "image_url":         None,
                "comentario_fixado": None,
                "thread_posts":      None,
                "scheduled_at":      quando,
                "session_id":        project.get("session_id"),
                "article_slug":      project.get("article_slug"),
                "article_url":       project.get("article_url"),
                "project_id":        project_id,
                "language":          project.get("language") or "pt-BR",
                "duration_s":        duracao_s,
                "retry_count":       0,
                "error_message":     None,
                "published_at":      None,
                "platform_post_id":  None,
                "created_at":        base.isoformat(),
                "updated_at":        base.isoformat(),
            })
            logger.info(
                "[VerticalCutJob] %s enfileirado para %s em %s",
                plataforma, project_id, quando[:16],
            )

    async def _build_clips(
        self,
        project_id: str,
        manifest: Manifest,
        cut_items: list[Segment],
        clips_prefix: str,
        audio_uris: list[str],
        manifest_html: Path,
        work: Path,
        width: int,
        height: int,
    ) -> tuple[list[dict], list[dict]]:
        clips_dir = work / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)

        audio_by_seg = {
            os.path.splitext(os.path.basename(uri))[0]: uri for uri in audio_uris
        }

        clips: list[dict] = []
        timeline: list[dict] = []
        cursor = 0.0

        for item in cut_items:
            source_id = item.source or item.id
            dest      = clips_dir / f"{item.id}.mp4"

            if item.kind == "avatar":
                # Crop do clipe horizontal já montado — o mesmo que está no
                # vídeo do YouTube, com o mesmo áudio e o mesmo corte de
                # silêncio. É literalmente o mesmo pedaço de vídeo.
                src = await self._download(
                    f"{clips_prefix}/{source_id}.mp4", work / f"h_{source_id}.mp4"
                )
                await asyncio.to_thread(
                    crop_to_vertical, src, dest, width, height, CROP_X_RATIO
                )
            else:
                if item.slide is None:
                    raise ComposeError(
                        f"{item.id}: item de ilustração no corte sem id de slide vertical"
                    )
                audio_uri = audio_by_seg.get(source_id)
                if not audio_uri:
                    raise ComposeError(
                        f"{item.id}: sem áudio TTS do segmento de origem {source_id}"
                    )
                audio = await self._download(audio_uri, work / f"a_{source_id}.mp3")
                await asyncio.to_thread(
                    render_slide_clip,
                    manifest_html, str(item.slide), dest, width, height,
                    item.min_duration_s, audio,
                )

            duration = probe_duration(dest)
            if duration <= 0:
                raise ComposeError(f"{item.id}: clipe vertical vazio")

            words = await self._words_for_segment(
                source_id  = source_id,
                script     = item.script or "",
                audio_uri  = audio_by_seg.get(source_id),
                duration_s = duration,
                work       = work,
            )

            clips.append({"segment_id": item.id, "path": dest, "words": words,
                          "duration_s": duration})
            timeline.append({
                "segment_id": item.id,
                "source":     source_id,
                "kind":       item.kind,
                "slide":      item.slide,
                "start_s":    round(cursor, 3),
                "end_s":      round(cursor + duration, 3),
                "duration_s": round(duration, 3),
            })
            cursor += duration
            logger.info(
                "[VerticalCutJob] %s ← %s (%s) → %.1fs",
                item.id, source_id, item.kind, duration,
            )

        return clips, timeline

    # ── Legendas ──────────────────────────────────────────────────────────────

    async def _words_for_segment(
        self,
        source_id: str,
        script: str,
        audio_uri: Optional[str],
        duration_s: float,
        work: Path,
    ) -> list:
        """
        Palavras cronometradas de um segmento, na linha do tempo DO CLIPE
        (começando em zero) — o offset na peça final é aplicado depois.

        Fonte preferida: o alinhamento por caractere que o tts_job salvou ao
        lado do áudio. Fallback: estimativa proporcional ao tamanho de cada
        palavra, para projetos cujo áudio foi gerado antes desta feature.
        Legenda levemente adiantada é muito melhor do que legenda nenhuma.
        """
        if audio_uri:
            alignment_uri = audio_uri.rsplit(".", 1)[0] + ".alignment.json"
            try:
                local = await self._download(
                    alignment_uri, work / f"align_{source_id}.json"
                )
                payload   = json.loads(local.read_text(encoding="utf-8"))
                words     = words_from_alignment(payload.get("alignment") or {})
                if words:
                    return words
                logger.warning("[VerticalCutJob] Alinhamento vazio para %s", source_id)
            except ComposeError:
                logger.info(
                    "[VerticalCutJob] %s sem alignment.json (áudio anterior à "
                    "feature de legendas) — estimando tempos pelo texto.", source_id,
                )
            except Exception as exc:
                logger.warning(
                    "[VerticalCutJob] Falha ao ler alinhamento de %s: %s", source_id, exc
                )

        if not script.strip():
            return []
        return words_from_text_estimated(script, duration_s)

    @staticmethod
    def _collect_cues(clips: list[dict]) -> list[Cue]:
        """
        Junta as palavras de todos os clipes numa linha do tempo única.

        Cada clipe traz tempos que começam em zero; aqui eles são deslocados
        pela posição do clipe na peça montada. As cues são agrupadas POR
        CLIPE, não no fim: agrupar tudo junto poderia criar uma cue que
        atravessa o corte entre dois segmentos, mostrando na ilustração uma
        frase que começou no avatar.
        """
        cues: list[Cue] = []
        offset = 0.0
        for clip in clips:
            words = clip.get("words") or []
            if words:
                shifted = [w.shifted(offset) for w in words]
                cues.extend(group_into_cues(shifted))
            offset += clip.get("duration_s") or 0.0
        return cues

    # ──────────────────────────────────────────────────────────────────────────

    async def _load_manifest(self, project_id: str) -> Manifest:
        project = await self.firestore.get_project(project_id)
        bucket_name, blob_path = project["manifest_url"].replace("gs://", "").split("/", 1)
        blob    = self.gcs.bucket(bucket_name).blob(blob_path)
        content = await asyncio.to_thread(blob.download_as_text)
        return Manifest._parse_from_html(content)

    async def _download(self, gcs_uri: str, dest: Path) -> Path:
        bucket_name, blob_path = gcs_uri.replace("gs://", "").split("/", 1)
        blob = self.gcs.bucket(bucket_name).blob(blob_path)
        if not await asyncio.to_thread(blob.exists):
            raise ComposeError(f"arquivo ausente no GCS: {gcs_uri}")
        await asyncio.to_thread(blob.download_to_filename, str(dest))
        return dest

    async def _upload(self, local: Path, blob_path: str, content_type: str) -> str:
        blob = self.gcs.bucket(self.gcs_bucket).blob(blob_path)
        await asyncio.to_thread(
            blob.upload_from_filename, str(local), content_type=content_type
        )
        return f"gs://{self.gcs_bucket}/{blob_path}"
