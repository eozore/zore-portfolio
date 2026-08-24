"""
agents/pipeline/video_editor_job/job.py
========================================
VideoEditorJob — monta o vídeo horizontal do YouTube.

REGRA DO PRODUTO, e o que este job existe para garantir:

    Cada segmento é UMA tela cheia. Ou o avatar falando, ou a ilustração com
    a voz por cima. Nunca os dois ao mesmo tempo, nunca avatar reduzido num
    canto do slide.

    O roteiro distribui ~20% do tempo para o avatar (gancho, reentradas de
    respiro, fechamento) e ~80% para ilustração. Só os segmentos de avatar
    passam pelo HeyGen.

Entrada:  AvatarCompletedMsg (clipes de avatar já no GCS) + manifesto v2.
Saída:    final_horizontal.mp4, os clipes por segmento em clips/, e o mapa de
          tempos — tudo no GCS. É desse material que o corte vertical é
          derivado depois, sem nenhuma nova geração de avatar.

Este job NÃO produz vertical. O Reel/Short é um recorte deste vídeo, feito
sob demanda pelo vertical_cut_job depois que o dono do canal aprova o longo.
"""

import asyncio
import json
import logging
import os
import tempfile
import time
from pathlib import Path

from google.cloud import storage

from shared.compose import (
    ComposeError,
    concat_clips,
    normalize_clip,
    probe_duration,
    render_slide_clip,
    trim_edge_silence,
)
from shared.firestore_client import FirestoreClient
from shared.models import AvatarCompletedMsg, Manifest, Segment, VideoReadyMsg
from shared.pubsub_client import PubSubClient

logger = logging.getLogger(__name__)

VIDEO_READY_TOPIC = "content-pipeline.video-ready"


class VideoEditorJob:
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

    # ──────────────────────────────────────────────────────────────────────────
    # Entry point
    # ──────────────────────────────────────────────────────────────────────────

    async def run(self, msg: AvatarCompletedMsg) -> None:
        project_id = msg.project_id

        project = await self.firestore.get_project(project_id)
        if project["stages"]["editor"]["status"] == "completed":
            logger.info("[VideoEditorJob] Editor já concluído para %s. Ignorando.", project_id)
            return

        await self.firestore.update_stage(project_id, "editor", {
            "status": "running",
            "started_at": int(time.time()),
        })

        try:
            manifest = await self._load_manifest(project_id)
            res      = manifest.horizontal_resolution()
            width, height = res["width"], res["height"]

            avatar_stage      = project["stages"].get("avatar", {})
            slide_audio_paths = avatar_stage.get("slide_audio_paths", {}) or {}

            with tempfile.TemporaryDirectory(prefix=f"editor_{project_id}_") as work_dir:
                work = Path(work_dir)

                avatar_clips = await self._download_avatar_clips(msg, work)
                audio_files  = await self._download_slide_audio(
                    slide_audio_paths.get("horizontal", []), work
                )
                manifest_html = await self._download_html_manifest(project_id, work)

                logger.info(
                    "[VideoEditorJob] %s: %d clipes de avatar, %d áudios de ilustração",
                    project_id, len(avatar_clips), len(audio_files),
                )

                clips, timeline = await self._build_segment_clips(
                    manifest      = manifest,
                    avatar_clips  = avatar_clips,
                    audio_files   = audio_files,
                    manifest_html = manifest_html,
                    work          = work,
                    width         = width,
                    height        = height,
                )

                if not clips:
                    raise ComposeError(
                        "nenhum clipe utilizável — nem avatar nem ilustração foram produzidos"
                    )

                final_path = work / "final_horizontal.mp4"
                await asyncio.to_thread(
                    concat_clips, [c["path"] for c in clips], final_path, width, height
                )
                duration = probe_duration(final_path)

                final_uri = await self._upload(
                    final_path, f"projects/{project_id}/final_horizontal.mp4", "video/mp4"
                )
                # Os clipes por segmento sobrevivem à execução de propósito: são
                # a matéria-prima do corte vertical. Sem eles, gerar o Reel
                # exigiria recortar o vídeo final ou chamar o HeyGen de novo.
                for clip in clips:
                    clip["gcs_uri"] = await self._upload(
                        clip["path"],
                        f"projects/{project_id}/clips/{clip['segment_id']}.mp4",
                        "video/mp4",
                    )

                timeline_doc = {
                    "project_id":   project_id,
                    "duration_s":   round(duration, 2),
                    "resolution":   {"width": width, "height": height},
                    "avatar_share": self._avatar_share(timeline),
                    "segments":     timeline,
                }
                timeline_path = work / "timeline.json"
                timeline_path.write_text(
                    json.dumps(timeline_doc, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                await self._upload(
                    timeline_path, f"projects/{project_id}/timeline.json", "application/json"
                )

            logger.info(
                "[VideoEditorJob] %s pronto: %.1fs, %d segmentos, %.0f%% de avatar.",
                project_id, duration, len(timeline), timeline_doc["avatar_share"] * 100,
            )

            await self.firestore.update_stage(project_id, "editor", {
                "status":        "completed",
                "completed_at":  int(time.time()),
                "horizontal_url": final_uri,
                # Sem vertical aqui: o Reel é derivado deste vídeo depois da
                # aprovação, pelo vertical_cut_job.
                "vertical_url":  "",
                "duration_s":    round(duration, 2),
                "avatar_share":  timeline_doc["avatar_share"],
                "clips_prefix":  f"gs://{self.gcs_bucket}/projects/{project_id}/clips",
                "timeline":      timeline,
            })

            self.pubsub.publish(VIDEO_READY_TOPIC, VideoReadyMsg(
                project_id=project_id,
                horizontal_final=final_uri,
                vertical_final="",
                duration_seconds=round(duration, 2),
                trigger="scheduled",
            ))
            logger.info("[VideoEditorJob] video_ready publicado para %s", project_id)

        except Exception as exc:
            logger.exception("[VideoEditorJob] Erro para %s: %s", project_id, exc)
            await self.firestore.update_stage(project_id, "editor", {
                "status": "error",
                "error_message": str(exc)[:900],
                "error_type": "permanent" if isinstance(exc, ComposeError) else "transient",
            })
            raise

    # ──────────────────────────────────────────────────────────────────────────
    # Composição
    # ──────────────────────────────────────────────────────────────────────────

    async def _build_segment_clips(
        self,
        manifest: Manifest,
        avatar_clips: dict[str, Path],
        audio_files: dict[str, Path],
        manifest_html: Path,
        work: Path,
        width: int,
        height: int,
    ) -> tuple[list[dict], list[dict]]:
        """
        Um clipe de tela cheia por segmento, na ordem do manifesto.

        Falta de material é erro, não fallback silencioso. A versão anterior
        pulava o segmento com um `logger.warning` e seguia montando: o vídeo
        saía sem o pedaço e ninguém ficava sabendo até assistir.
        """
        clips_dir = work / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)

        segments = [Segment.from_raw(s) for s in manifest._get_raw_segments("horizontal")]
        clips: list[dict] = []
        timeline: list[dict] = []
        cursor = 0.0
        missing: list[str] = []

        for seg in segments:
            dest = clips_dir / f"{seg.id}.mp4"

            if seg.kind == "avatar":
                source = avatar_clips.get(seg.id)
                if not source:
                    missing.append(f"{seg.id} (avatar sem clipe do HeyGen)")
                    continue
                staged = clips_dir / f"{seg.id}_norm.mp4"
                await asyncio.to_thread(normalize_clip, source, staged, width, height)
                await asyncio.to_thread(trim_edge_silence, staged, dest)
                staged.unlink(missing_ok=True)

            else:
                if seg.slide is None:
                    missing.append(f"{seg.id} (ilustração sem id de slide)")
                    continue
                audio = audio_files.get(seg.id)
                if seg.script and not audio:
                    missing.append(f"{seg.id} (ilustração sem áudio TTS)")
                    continue
                await asyncio.to_thread(
                    render_slide_clip,
                    manifest_html, str(seg.slide), dest, width, height,
                    seg.min_duration_s, audio,
                )

            duration = probe_duration(dest)
            if duration <= 0:
                missing.append(f"{seg.id} (clipe vazio)")
                continue

            clips.append({"segment_id": seg.id, "path": dest, "kind": seg.kind})
            timeline.append({
                "segment_id": seg.id,
                "kind":       seg.kind,
                "slide":      seg.slide,
                "beat":       seg.beat,
                "start_s":    round(cursor, 3),
                "end_s":      round(cursor + duration, 3),
                "duration_s": round(duration, 3),
            })
            cursor += duration
            logger.info(
                "[VideoEditorJob] %s (%s) → %.1fs", seg.id, seg.kind, duration
            )

        if missing:
            raise ComposeError(
                "segmentos sem material para compor: " + "; ".join(missing)
            )
        return clips, timeline

    @staticmethod
    def _avatar_share(timeline: list[dict]) -> float:
        total = sum(t["duration_s"] for t in timeline)
        if not total:
            return 0.0
        avatar = sum(t["duration_s"] for t in timeline if t["kind"] == "avatar")
        return round(avatar / total, 3)

    # ──────────────────────────────────────────────────────────────────────────
    # GCS
    # ──────────────────────────────────────────────────────────────────────────

    async def _download_avatar_clips(
        self, msg: AvatarCompletedMsg, work: Path
    ) -> dict[str, Path]:
        clips: dict[str, Path] = {}
        for gcs_uri, seg_id in zip(msg.horizontal_video_paths, msg.segment_ids):
            clips[seg_id] = await self._download(gcs_uri, work / f"avatar_{seg_id}.mp4")
        return clips

    async def _download_slide_audio(
        self, gcs_uris: list[str], work: Path
    ) -> dict[str, Path]:
        """
        O TTS nomeia cada arquivo como `{segment_id}.mp3`, então o nome do
        arquivo é a chave de junção com o manifesto.
        """
        audio: dict[str, Path] = {}
        for uri in gcs_uris:
            seg_id = os.path.splitext(os.path.basename(uri))[0]
            audio[seg_id] = await self._download(uri, work / f"audio_{seg_id}.mp3")
        return audio

    async def _load_manifest(self, project_id: str) -> Manifest:
        project  = await self.firestore.get_project(project_id)
        bucket_name, blob_path = project["manifest_url"].replace("gs://", "").split("/", 1)
        blob     = self.gcs.bucket(bucket_name).blob(blob_path)
        content  = await asyncio.to_thread(blob.download_as_text)
        return Manifest._parse_from_html(content)

    async def _download_html_manifest(self, project_id: str, work: Path) -> Path:
        project = await self.firestore.get_project(project_id)
        return await self._download(project["manifest_url"], work / "manifest.html")

    async def _download(self, gcs_uri: str, dest: Path) -> Path:
        bucket_name, blob_path = gcs_uri.replace("gs://", "").split("/", 1)
        blob = self.gcs.bucket(bucket_name).blob(blob_path)
        await asyncio.to_thread(blob.download_to_filename, str(dest))
        return dest

    async def _upload(self, local: Path, blob_path: str, content_type: str) -> str:
        blob = self.gcs.bucket(self.gcs_bucket).blob(blob_path)
        await asyncio.to_thread(
            blob.upload_from_filename, str(local), content_type=content_type
        )
        return f"gs://{self.gcs_bucket}/{blob_path}"
