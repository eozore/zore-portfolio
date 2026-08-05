"""
agents/pipeline/video_editor_job/job.py
==========================================
VideoEditorJob: compõe o vídeo final (horizontal + vertical) usando:
  - Avatar (HeyGen): vídeo do avatar falando (segmentos sem slide)
  - Slide + Áudio: HTML renderizado via Playwright + áudio TTS colado (segmentos com slide)
  - Slide puro: HTML renderizado via Playwright (segmentos sem script)
  - FFmpeg: composição determinística baseada no manifesto
  - Jump cuts: remove silêncios > 0.8s nos segmentos de avatar

Três tipos de segmento:
  1. script != "" e slide == None → vídeo HeyGen (avatar full screen)
  2. script != "" e slide != None → slide HTML renderizado + áudio TTS
  3. script == "" e slide != None → slide HTML renderizado (sem áudio)

Fluxo:
  1. Recebe AvatarCompletedMsg com vídeos HeyGen (pode ser vazio)
  2. Carrega slide_audio_paths do Firestore (áudios TTS para slides)
  3. Para cada segmento do manifesto:
     - HeyGen: usa vídeo do AvatarCompletedMsg
     - Slide+áudio: renderiza HTML → cria vídeo → cola áudio TTS
     - Slide puro: renderiza HTML → cria vídeo mudo
  4. Concatena tudo na ordem do manifesto
  5. Aplica jump cuts e publica video_ready
"""

import asyncio
import logging
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Literal, Optional

from google.cloud import storage
from playwright.sync_api import sync_playwright

from shared.firestore_client import FirestoreClient
from shared.models import AvatarCompletedMsg, Manifest, Segment, VideoReadyMsg
from shared.pubsub_client import PubSubClient

# Sprint 3 / G3 — anchor-driven slide transitions
from anchor_resolver import resolve_anchors, SlideTransition

logger = logging.getLogger(__name__)

VIDEO_READY_TOPIC    = "content-pipeline.video-ready"
MIN_SILENCE_SEC      = 0.8   # silêncios maiores que isso são cortados
JUMP_CUT_PADDING     = 0.15  # segundos de margem antes/depois da fala
SLIDE_RECORD_SECS    = 15.0  # quanto tempo gravar cada slide (animações completas)


class VideoEditorJob:
    def __init__(
        self,
        firestore: FirestoreClient,
        pubsub: PubSubClient,
        gcs_bucket: str,
        tenant_id: str = "default",
    ) -> None:
        self.firestore   = firestore
        self.pubsub      = pubsub
        self.gcs_bucket  = gcs_bucket
        self.gcs         = storage.Client()

    # ──────────────────────────────────────────────────────────────────────────
    # Entry point
    # ──────────────────────────────────────────────────────────────────────────

    async def run(self, msg: AvatarCompletedMsg) -> None:
        project_id = msg.project_id

        # Idempotência
        project = await self.firestore.get_project(project_id)
        if project["stages"]["editor"]["status"] == "completed":
            logger.info("[VideoEditorJob] Editor já concluído para %s. Ignorando.", project_id)
            return

        await self.firestore.update_stage(project_id, "editor", {
            "status": "running",
            "started_at": int(time.time()),
        })

        try:
            # Baixar manifesto do GCS
            manifest = await self._load_manifest(project_id)

            # Buscar dados de slide+áudio do Firestore (salvos pelo avatar_job)
            avatar_stage = project["stages"].get("avatar", {})
            slide_audio_paths = avatar_stage.get("slide_audio_paths", {})
            slide_audio_segment_ids = avatar_stage.get("slide_audio_segment_ids", {})

            # Diretório de trabalho temporário
            with tempfile.TemporaryDirectory(prefix=f"editor_{project_id}_") as work_dir:
                work = Path(work_dir)

                # Baixar vídeos HeyGen (segmentos de avatar)
                h_heygen_paths: dict[str, str] = {}
                v_heygen_paths: dict[str, str] = {}

                for i, (gcs_uri, seg_id) in enumerate(
                    zip(msg.horizontal_video_paths, msg.segment_ids)
                ):
                    local = await self._download_from_gcs(
                        gcs_uri, work / f"avatar_h_{seg_id}.mp4"
                    )
                    h_heygen_paths[seg_id] = str(local)

                for i, gcs_uri in enumerate(msg.vertical_video_paths):
                    seg_id = (msg.vertical_segment_ids[i]
                              if i < len(msg.vertical_segment_ids)
                              else f"seg_{i:03d}")
                    local = await self._download_from_gcs(
                        gcs_uri, work / f"avatar_v_{seg_id}.mp4"
                    )
                    v_heygen_paths[seg_id] = str(local)

                # Baixar áudios TTS para segmentos slide+áudio
                h_slide_audio_paths: dict[str, str] = {}
                v_slide_audio_paths: dict[str, str] = {}

                for gcs_uri in slide_audio_paths.get("horizontal", []):
                    seg_id = os.path.splitext(os.path.basename(gcs_uri))[0]
                    # Só baixa se é um segmento de slide+áudio
                    if seg_id in (slide_audio_segment_ids.get("horizontal", [])):
                        local = await self._download_from_gcs(
                            gcs_uri, work / f"audio_h_{seg_id}.mp3"
                        )
                        h_slide_audio_paths[seg_id] = str(local)

                for gcs_uri in slide_audio_paths.get("vertical", []):
                    seg_id = os.path.splitext(os.path.basename(gcs_uri))[0]
                    if seg_id in (slide_audio_segment_ids.get("vertical", [])):
                        local = await self._download_from_gcs(
                            gcs_uri, work / f"audio_v_{seg_id}.mp3"
                        )
                        v_slide_audio_paths[seg_id] = str(local)

                logger.info(
                    "[VideoEditorJob] Recursos carregados: HeyGen H=%d V=%d, SlideAudio H=%d V=%d",
                    len(h_heygen_paths), len(v_heygen_paths),
                    len(h_slide_audio_paths), len(v_slide_audio_paths),
                )

                # Baixar manifesto HTML para o disco (Playwright precisa de arquivo local)
                manifest_html_path = await self._download_html_manifest(project_id, work)

                # Processar horizontal e vertical
                results = {}
                for target, heygen_paths, slide_audio_map in [
                    ("horizontal", h_heygen_paths, h_slide_audio_paths),
                    ("vertical",   v_heygen_paths, v_slide_audio_paths),
                ]:
                    out_path = work / f"final_{target}.mp4"
                    final_path = await self._process_target_v3(
                        manifest=manifest,
                        target=target,
                        heygen_video_paths=heygen_paths,
                        slide_audio_paths=slide_audio_map,
                        manifest_html=str(manifest_html_path),
                        output_path=str(out_path),
                        work_dir=work,
                    )
                    if final_path and os.path.exists(final_path):
                        # Upload para GCS
                        gcs_uri = await self._upload_to_gcs(final_path, project_id, target)
                        results[target] = gcs_uri
                        logger.info("[VideoEditorJob] %s → %s", target, gcs_uri)

            # Atualizar Firestore
            await self.firestore.update_stage(project_id, "editor", {
                "status": "completed",
                "completed_at": int(time.time()),
                "horizontal_url": results.get("horizontal", ""),
                "vertical_url":   results.get("vertical", ""),
            })

            # Publicar video_ready
            self.pubsub.publish(VIDEO_READY_TOPIC, VideoReadyMsg(
                project_id=project_id,
                horizontal_final=results.get("horizontal", ""),
                vertical_final=results.get("vertical", ""),
                duration_seconds=0.0,   # publisher calcula via ffprobe
                trigger="scheduled",
            ))
            logger.info("[VideoEditorJob] video_ready publicado para %s", project_id)

        except Exception as exc:
            logger.exception("[VideoEditorJob] Erro para %s: %s", project_id, exc)
            await self.firestore.update_stage(project_id, "editor", {
                "status": "error",
                "error_message": str(exc),
                "error_type": "transient",
            })
            raise

    # ──────────────────────────────────────────────────────────────────────────
    # Processamento por target v3 (3 tipos de segmento)
    # ──────────────────────────────────────────────────────────────────────────

    async def _process_target_v3(
        self,
        manifest: Manifest,
        target: Literal["horizontal", "vertical"],
        heygen_video_paths: dict[str, str],
        slide_audio_paths: dict[str, str],
        manifest_html: str,
        output_path: str,
        work_dir: Path,
    ) -> str:
        """
        Pipeline v3 para um target (horizontal ou vertical).
        
        Três tipos de segmento:
        1. HeyGen (script + no slide): usa vídeo do HeyGen
        2. Slide+áudio (script + slide): renderiza HTML + cola áudio TTS
        3. Slide puro (no script + slide): renderiza HTML mudo
        """
        logger.info("[VideoEditorJob] Processando target=%s (v3)", target)

        segments = manifest._get_raw_segments(target)
        if not segments:
            logger.warning("[VideoEditorJob] Sem segmentos para target=%s", target)
            return output_path

        # Resolução do target
        if target == "horizontal":
            resolution = manifest.youtube.get("resolution", {"width": 1920, "height": 1080})
        else:
            resolution = next(
                (r.get("resolution", {"width": 1080, "height": 1920}) 
                 for r in manifest.reels if r.get("reel_id") == "reel-01"),
                {"width": 1080, "height": 1920}
            )
        width, height = resolution["width"], resolution["height"]

        # Diretório para clipes individuais
        clips_dir = work_dir / f"clips_{target}"
        clips_dir.mkdir(parents=True, exist_ok=True)

        # Processar cada segmento
        clip_paths: list[str] = []
        
        for seg in segments:
            seg_id = seg.get("id", seg.get("segment_id", "unknown"))
            script = seg.get("script", "").strip()
            slide = seg.get("slide")
            
            clip_path = clips_dir / f"{seg_id}.mp4"
            
            if script and slide is None:
                # Tipo 1: HeyGen (avatar full screen)
                if seg_id in heygen_video_paths:
                    clip_paths.append(heygen_video_paths[seg_id])
                    logger.debug("[v3] Segmento %s: HeyGen video", seg_id)
                else:
                    logger.warning("[v3] Segmento %s: HeyGen esperado mas não encontrado", seg_id)
                    
            elif script and slide is not None:
                # Tipo 2: Slide + áudio TTS
                audio_path = slide_audio_paths.get(seg_id)
                if audio_path:
                    await self._render_slide_with_audio(
                        html_path=manifest_html,
                        slide_id=slide,
                        audio_path=audio_path,
                        output_path=str(clip_path),
                        width=width,
                        height=height,
                    )
                    clip_paths.append(str(clip_path))
                    logger.debug("[v3] Segmento %s: Slide+áudio", seg_id)
                else:
                    # Fallback: renderiza slide mudo se áudio não disponível
                    logger.warning("[v3] Segmento %s: áudio não encontrado, renderizando mudo", seg_id)
                    await self._render_slide_mute(
                        html_path=manifest_html,
                        slide_id=slide,
                        output_path=str(clip_path),
                        width=width,
                        height=height,
                        duration_s=seg.get("min_duration_s", 5.0),
                    )
                    clip_paths.append(str(clip_path))
                    
            elif slide is not None:
                # Tipo 3: Slide puro (sem áudio)
                await self._render_slide_mute(
                    html_path=manifest_html,
                    slide_id=slide,
                    output_path=str(clip_path),
                    width=width,
                    height=height,
                    duration_s=seg.get("min_duration_s", 5.0),
                )
                clip_paths.append(str(clip_path))
                logger.debug("[v3] Segmento %s: Slide puro (mudo)", seg_id)
            else:
                logger.warning("[v3] Segmento %s: sem slide nem HeyGen, pulando", seg_id)

        if not clip_paths:
            logger.error("[VideoEditorJob] Nenhum clipe gerado para target=%s", target)
            return output_path

        # Concatenar todos os clipes
        concat_path = work_dir / f"concat_{target}.mp4"
        await self._concat_clips(clip_paths, str(concat_path))

        # Jump cuts (remove silêncios)
        cut_path = work_dir / f"cut_{target}.mp4"
        await self._apply_jump_cuts(str(concat_path), str(cut_path))

        # Copiar para output final
        import shutil
        shutil.copy2(str(cut_path), output_path)
        return output_path

    async def _render_slide_with_audio(
        self,
        html_path: str,
        slide_id: str | int,
        audio_path: str,
        output_path: str,
        width: int,
        height: int,
    ) -> None:
        """
        Renderiza um slide HTML via Playwright e cola o áudio TTS.
        A duração do vídeo é determinada pelo áudio.
        """
        # 1. Obter duração do áudio via ffprobe
        audio_duration = await self._get_audio_duration(audio_path)
        record_duration = max(audio_duration + 0.5, 3.0)  # mínimo 3s, margem 0.5s

        # 2. Renderizar slide como vídeo mudo
        mute_path = output_path.replace(".mp4", "_mute.mp4")
        await self._render_slide_mute(
            html_path=html_path,
            slide_id=slide_id,
            output_path=mute_path,
            width=width,
            height=height,
            duration_s=record_duration,
        )

        # 3. Colar áudio no vídeo via FFmpeg
        cmd = [
            "ffmpeg", "-y",
            "-i", mute_path,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            output_path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error("[FFmpeg] Erro ao colar áudio: %s", stderr.decode())
            raise RuntimeError(f"FFmpeg falhou: {stderr.decode()}")

        # Limpar arquivo temporário
        if os.path.exists(mute_path):
            os.remove(mute_path)

        logger.info("[v3] Slide %s renderizado com áudio (%0.1fs)", slide_id, audio_duration)

    async def _render_slide_mute(
        self,
        html_path: str,
        slide_id: str | int,
        output_path: str,
        width: int,
        height: int,
        duration_s: float,
    ) -> None:
        """
        Renderiza um slide HTML via Playwright como vídeo mudo.
        """
        loop = asyncio.get_event_loop()
        file_url = Path(html_path).resolve().as_uri()

        def _record() -> None:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"]
                )
                raw_dir = Path(output_path).parent / "_raw_webm"
                raw_dir.mkdir(exist_ok=True)

                ctx = browser.new_context(
                    viewport={"width": width, "height": height},
                    record_video_dir=str(raw_dir),
                    record_video_size={"width": width, "height": height},
                )
                page = ctx.new_page()
                page.goto(file_url)
                page.wait_for_timeout(300)

                # Esconder HUD
                page.evaluate("try { if(window.hudVisible !== false) toggleHud(); } catch(e) {}")

                # Navegar para o slide correto
                if isinstance(slide_id, int):
                    page.evaluate(f"try {{ goTo({slide_id}); }} catch(e) {{ window.currentSlide = {slide_id}; }}")
                else:
                    # slide_id string (v2): "yt-02" → usa goToSlide ou similar
                    page.evaluate(f"try {{ goToSlide('{slide_id}'); }} catch(e) {{ goTo('{slide_id}'); }}")

                # Buffer antes de animar
                page.wait_for_timeout(500)

                # Disparar animações
                page.evaluate("""
                    try {
                        replaySlide();
                    } catch(e) {
                        const active = document.querySelector('section.slide.active');
                        if (active) {
                            active.classList.remove('active');
                            void active.offsetWidth;
                            active.classList.add('active');
                        }
                    }
                """)

                # Aguardar duração
                page.wait_for_timeout(int(duration_s * 1000))

                ctx.close()
                browser.close()

                # Converter webm → mp4
                webm_files = sorted(raw_dir.glob("*.webm"), key=lambda f: f.stat().st_mtime)
                if webm_files:
                    src_webm = webm_files[-1]
                    subprocess.run(
                        [
                            "ffmpeg", "-y",
                            "-i", str(src_webm),
                            "-c:v", "libx264",
                            "-preset", "fast",
                            "-crf", "23",
                            "-an",  # sem áudio
                            "-t", str(duration_s),
                            output_path,
                        ],
                        check=True,
                        capture_output=True,
                    )
                    src_webm.unlink()

        await loop.run_in_executor(None, _record)
        logger.debug("[Playwright] Slide %s renderizado mudo (%0.1fs)", slide_id, duration_s)

    async def _get_audio_duration(self, audio_path: str) -> float:
        """Retorna duração do áudio em segundos via ffprobe."""
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        try:
            return float(stdout.decode().strip())
        except ValueError:
            logger.warning("[ffprobe] Não conseguiu obter duração de %s", audio_path)
            return 5.0  # fallback

    async def _concat_clips(self, clip_paths: list[str], output_path: str) -> None:
        """Concatena lista de clipes em ordem usando FFmpeg concat demuxer."""
        if len(clip_paths) == 1:
            import shutil
            shutil.copy2(clip_paths[0], output_path)
            return

        # Criar arquivo de lista para concat
        list_path = Path(output_path).parent / "concat_list.txt"
        with open(list_path, "w") as f:
            for clip in clip_paths:
                f.write(f"file '{clip}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_path),
            "-c", "copy",
            output_path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error("[FFmpeg] Erro ao concatenar: %s", stderr.decode())
            raise RuntimeError(f"FFmpeg concat falhou: {stderr.decode()}")

        logger.info("[v3] Concatenados %d clipes → %s", len(clip_paths), output_path)

    # ──────────────────────────────────────────────────────────────────────────
    # Processamento por target (LEGADO - mantido para compatibilidade)
    # ──────────────────────────────────────────────────────────────────────────

    async def _process_target(
        self,
        manifest: Manifest,
        target: Literal["horizontal", "vertical"],
        segment_video_paths: dict[str, str],  # BUG2 fix: seg_id → local mp4 path
        manifest_html: str,
        output_path: str,
        work_dir: Path,
    ) -> str:
        """Pipeline completa para um target (horizontal ou vertical)."""
        logger.info("[VideoEditorJob] Processando target=%s", target)

        segments      = manifest._get_raw_segments(target)

        # ── Suporte a manifesto v2 (slide = string id) e v1 (slide = int) ──
        manifest_version = getattr(manifest, "version", 1)
        # Coleta ids de slide únicos — string (v2) ou inteiro (v1)
        slide_ids_raw = [s["slide"] for s in segments if s.get("slide") is not None]
        # Para v1: lista de ints. Para v2: lista de strings como "yt-02"
        slide_indices = sorted(
            {int(s) for s in slide_ids_raw if str(s).isdigit()},
            key=int,
        )
        # Para v2 (ids string): também coletamos para _export_slides_v2
        slide_str_ids = [s for s in slide_ids_raw if not str(s).isdigit()]

        if not segments:
            logger.warning("[VideoEditorJob] Sem segmentos para target=%s", target)
            # Fallback: concatena os vídeos de segmentos na ordem
            if segment_video_paths:
                first_path = next(iter(segment_video_paths.values()))
                return first_path
            return output_path

        # 1. Exportar slides do HTML via Playwright
        slides_dir = work_dir / f"slides_{target}"
        if slide_indices or slide_str_ids:
            resolution = manifest.youtube["resolution"] if target == "horizontal" \
                else next(
                    (r["resolution"] for r in manifest.reels if r.get("reel_id") == "reel-01"),
                    {"width": 1080, "height": 1920}
                )
            if slide_str_ids:
                await self._export_slides_v2(
                    html_path=manifest_html,
                    slide_str_ids=list(dict.fromkeys(slide_str_ids)),
                    width=resolution["width"],
                    height=resolution["height"],
                    output_dir=slides_dir,
                )
            else:
                await self._export_slides(
                    html_path=manifest_html,
                    slide_indices=slide_indices,
                    width=resolution["width"],
                    height=resolution["height"],
                    output_dir=slides_dir,
                )

        # 2. Construir timeline intercalando avatar (por segmento) e slides
        composed_path = work_dir / f"composed_{target}.mp4"
        if slide_str_ids:
            # v2: composição com âncoras — BUG2: passa segment_video_paths
            await self._compose_timeline_v2(
                segments=segments,
                segment_video_paths=segment_video_paths,
                slides_dir=slides_dir,
                output_path=str(composed_path),
                target=target,
                work_dir=work_dir,
            )
        else:
            await self._compose_timeline(
                segments=segments,
                segment_video_paths=segment_video_paths,
                slides_dir=slides_dir,
                output_path=str(composed_path),
                target=target,
            )

        # 3. Jump cuts (remove silêncios nos segmentos de avatar)
        cut_path = work_dir / f"cut_{target}.mp4"
        await self._apply_jump_cuts(
            input_path=str(composed_path),
            output_path=str(cut_path),
        )

        # 4. Copiar para output final
        import shutil
        shutil.copy2(str(cut_path), output_path)
        return output_path

    # ──────────────────────────────────────────────────────────────────────────
    # Exportação de slides via Playwright (serializado por segurança OOM)
    # ──────────────────────────────────────────────────────────────────────────

    async def _export_slides(
        self,
        html_path: str,
        slide_indices: list[int],
        width: int,
        height: int,
        output_dir: Path,
    ) -> None:
        """Renderiza slides do HTML via Playwright (serializado, 1 processo por vez)."""
        output_dir.mkdir(parents=True, exist_ok=True)
        file_url = Path(html_path).resolve().as_uri()
        loop = asyncio.get_event_loop()

        def _record_all() -> None:
            """Roda em thread para não bloquear event loop. Playwright é síncrono."""
            # Serializado: um contexto por vez (evita OOM com 4GB)
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"]
                )
                raw_dir = output_dir / "_raw_webm"
                raw_dir.mkdir(exist_ok=True)

                for slide_idx in slide_indices:
                    out_mp4 = output_dir / f"slide_{slide_idx:02d}.mp4"
                    if out_mp4.exists():
                        logger.debug("[Playwright] slide_%02d já existe, pulando", slide_idx)
                        continue

                    logger.info("[Playwright] Gravando slide_%02d (%dx%d)...", slide_idx, width, height)
                    ctx = browser.new_context(
                        viewport={"width": width, "height": height},
                        record_video_dir=str(raw_dir),
                        record_video_size={"width": width, "height": height},
                    )
                    page = ctx.new_page()
                    page.goto(file_url)
                    page.wait_for_timeout(300)

                    # Esconder HUD
                    page.evaluate("try { if(window.hudVisible !== false) toggleHud(); } catch(e) {}")

                    # Navegar para o slide correto
                    page.evaluate(f"try {{ goTo({slide_idx}); }} catch(e) {{ window.currentSlide = {slide_idx}; }}")

                    # 2s de buffer limpo antes de animar
                    page.wait_for_timeout(2000)

                    # Disparar animações
                    page.evaluate("""
                        try {
                            replaySlide();
                        } catch(e) {
                            // Disparar animações manualmente se replaySlide não existir
                            const active = document.querySelector('section.slide.active');
                            if (active) {
                                active.classList.remove('active');
                                void active.offsetWidth;
                                active.classList.add('active');
                            }
                        }
                    """)

                    # Aguardar duração total da animação
                    page.wait_for_timeout(int(SLIDE_RECORD_SECS * 1000))

                    video = page.video
                    ctx.close()

                    # Renomear webm gerado
                    webm_files = sorted(raw_dir.glob("*.webm"), key=lambda f: f.stat().st_mtime)
                    if webm_files:
                        src_webm = webm_files[-1]
                        # Converter para MP4
                        subprocess.run(
                            ["ffmpeg", "-y", "-i", str(src_webm),
                             "-c:v", "libx264", "-pix_fmt", "yuv420p",
                             "-crf", "18", "-preset", "fast", str(out_mp4)],
                            check=True, capture_output=True,
                        )
                        src_webm.unlink(missing_ok=True)

                browser.close()

        await loop.run_in_executor(None, _record_all)
        logger.info("[VideoEditorJob] %d slides exportados para %s", len(slide_indices), output_dir)

    # ──────────────────────────────────────────────────────────────────────────
    # Composição da timeline (sem Gemini — usa manifesto diretamente)
    # ──────────────────────────────────────────────────────────────────────────

    async def _compose_timeline(
        self,
        segments: list[dict],
        segment_video_paths: dict[str, str],  # BUG2: seg_id → local mp4 path
        slides_dir: Path,
        output_path: str,
        target: str,
    ) -> None:
        """
        Compõe o vídeo final intercalando clipes de avatar e slides.

        Para cada segmento:
          - script != "" → extrai trecho do avatar (acumula timestamps)
          - script == "" → usa clipe de slide (Playwright) por min_duration_s
        
        Depois concatena todos os clipes na ordem do manifesto.
        """
        loop = asyncio.get_event_loop()

        def _compose() -> None:
            clips: list[str] = []

            with tempfile.TemporaryDirectory(prefix="clips_") as clips_dir:
                for i, seg in enumerate(segments):
                    seg_id    = seg.get("id", f"seg_{i}")
                    script    = seg.get("script", "")
                    slide_idx = seg.get("slide")
                    min_dur   = float(seg.get("min_duration_s", 4.5))
                    pause     = float(seg.get("pause_after_s", 0.4))

                    clip_path = os.path.join(clips_dir, f"clip_{i:03d}.mp4")

                    if script:
                        # BUG2 fix: usar o vídeo individual do segmento
                        seg_video = segment_video_paths.get(seg_id)
                        if seg_video and os.path.exists(seg_video):
                            # O vídeo do segmento tem exatamente a duração do áudio — usar inteiro
                            _trim_clip(seg_video, min_dur + pause, clip_path)
                        else:
                            logger.warning(
                                "[VideoEditorJob] Vídeo do segmento %s não encontrado. Gerando clipe preto.",
                                seg_id,
                            )
                            _generate_black_clip(min_dur + pause, clip_path)
                    else:
                        # Slide puro: usa clipe do Playwright
                        slide_path = slides_dir / f"slide_{slide_idx:02d}.mp4" if slide_idx is not None else None
                        if slide_path and slide_path.exists():
                            _trim_clip(str(slide_path), min_dur + pause, clip_path)
                        else:
                            logger.warning("[VideoEditorJob] slide_%02d não encontrado para %s", slide_idx, seg_id)
                            _generate_black_clip(min_dur + pause, clip_path)

                    if os.path.exists(clip_path):
                        clips.append(clip_path)

                if not clips:
                    # Fallback: usar o primeiro vídeo de segmento disponível
                    first_seg_video = next(iter(segment_video_paths.values()), None)
                    if first_seg_video:
                        import shutil
                        shutil.copy2(first_seg_video, output_path)
                    return

                # Concatenar todos os clipes na ordem do manifesto
                _concat_clips(clips, output_path)

        await loop.run_in_executor(None, _compose)

    # ──────────────────────────────────────────────────────────────────────────
    # Exportação de slides v2 via goToSeg(segId) — Sprint 3 / G3
    # ──────────────────────────────────────────────────────────────────────────

    async def _export_slides_v2(
        self,
        html_path: str,
        slide_str_ids: list[str],
        width: int,
        height: int,
        output_dir: Path,
    ) -> None:
        """
        Renderiza slides do manifesto v2 usando goToSeg(segId) em vez de goTo(idx).
        Compatível com wrap_scriptwriter_manifest() do manifest_builder.py.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        file_url = Path(html_path).resolve().as_uri()
        loop = asyncio.get_event_loop()

        def _record_all_v2() -> None:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"]
                )
                raw_dir = output_dir / "_raw_webm"
                raw_dir.mkdir(exist_ok=True)

                for seg_id in slide_str_ids:
                    # Slug do arquivo — substitui caracteres não-alfanuméricos por _
                    safe_id  = re.sub(r"[^a-z0-9]", "_", seg_id.lower())
                    out_mp4  = output_dir / f"slide_{safe_id}.mp4"
                    if out_mp4.exists():
                        logger.debug("[Playwright v2] %s já existe, pulando", out_mp4.name)
                        continue

                    logger.info("[Playwright v2] Gravando slide %s (%dx%d)...", seg_id, width, height)
                    ctx = browser.new_context(
                        viewport={"width": width, "height": height},
                        record_video_dir=str(raw_dir),
                        record_video_size={"width": width, "height": height},
                    )
                    page = ctx.new_page()
                    page.goto(file_url)
                    page.wait_for_timeout(400)

                    # Esconder HUD
                    page.evaluate("try { if(window.hudVisible !== false) toggleHud(); } catch(e) {}")

                    # Navegar pelo ID do segmento (v2) com fallback para goTo(0)
                    page.evaluate(f"""
                        try {{
                            if (window.deckAPI && window.deckAPI.goToSeg) {{
                                window.deckAPI.goToSeg({seg_id!r});
                            }} else if (typeof goToSeg === 'function') {{
                                goToSeg({seg_id!r});
                            }}
                        }} catch(e) {{
                            console.warn('goToSeg failed for {seg_id}', e);
                        }}
                    """)

                    # Buffer antes de animar
                    page.wait_for_timeout(1500)

                    # Disparar animações (replaySlide ou equivalente)
                    page.evaluate("""
                        try {
                            if (window.deckAPI && window.deckAPI.replay) {
                                window.deckAPI.replay();
                            } else if (typeof replaySlide === 'function') {
                                replaySlide();
                            } else {
                                const active = document.querySelector('section.slide.active');
                                if (active) {
                                    active.classList.remove('active');
                                    void active.offsetWidth;
                                    active.classList.add('active');
                                }
                            }
                        } catch(e) {}
                    """)

                    page.wait_for_timeout(int(SLIDE_RECORD_SECS * 1000))
                    ctx.close()

                    webm_files = sorted(raw_dir.glob("*.webm"), key=lambda f: f.stat().st_mtime)
                    if webm_files:
                        src_webm = webm_files[-1]
                        subprocess.run(
                            ["ffmpeg", "-y", "-i", str(src_webm),
                             "-c:v", "libx264", "-pix_fmt", "yuv420p",
                             "-crf", "18", "-preset", "fast", str(out_mp4)],
                            check=True, capture_output=True,
                        )
                        src_webm.unlink(missing_ok=True)

                browser.close()

        await loop.run_in_executor(None, _record_all_v2)
        logger.info("[VideoEditorJob] v2: %d slides exportados", len(slide_str_ids))

    # ──────────────────────────────────────────────────────────────────────────
    # Composição da timeline v2 com âncoras — Sprint 3 / G3
    # ──────────────────────────────────────────────────────────────────────────

    async def _compose_timeline_v2(
        self,
        segments: list[dict],
        segment_video_paths: dict[str, str],  # BUG2: seg_id → local mp4 path
        slides_dir: Path,
        output_path: str,
        target: str,
        work_dir: Path,
    ) -> None:
        """
        Composição de timeline para manifesto v2.

        Diferença chave em relação a _compose_timeline (v1):
          — slide_id é uma string (ex: "yt-02"), não um inteiro
          — Segmentos de avatar COM slide_id recebem overlay do slide
            sobreposto no frame calculado pelo anchor_resolver
          — Segmentos de avatar SEM slide_id ficam em tela cheia de avatar
          — Segmentos com script="" e slide_id são slides puros (Playwright)

        Estratégia de overlay para segmentos avatar + slide (v2):
          1. Extrai o clipe de avatar com duração = min_duration_s
          2. Obtém a duração real via ffprobe (proxy para áudio TTS)
          3. Resolve anchors[] → SlideTransition timestamps
          4. Usa FFmpeg overlay para sobrepor o slide no frame correto:
             - Para show_slide: recorta o clipe do slide a partir do frame 0
               e aplica overlay a partir de t=anchor.time_s
             - Para reveal/highlight: injeta page.evaluate via Playwright
               (já gravado em SLIDE_RECORD_SECS — só o slice importa)
        """
        loop = asyncio.get_event_loop()

        def _get_duration(path: str) -> float:
            """ffprobe para obter duração real do clipe (proxy para áudio TTS)."""
            try:
                result = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", path],
                    capture_output=True, text=True, timeout=30,
                )
                return float(result.stdout.strip())
            except Exception:
                return 5.0

        def _overlay_slide_on_avatar(
            avatar_clip: str,
            slide_mp4: str,
            show_at_s: float,
            output: str,
            avatar_w: int = 1920,
            avatar_h: int = 1080,
            avatar_scale: float = 0.28,
            avatar_pos: str = "bottom-right",
        ) -> None:
            """
            Sobrepõe o slide como fundo e o avatar como overlay pequeno.
            O slide entra a partir de show_at_s (âncora show_slide).
            Antes de show_at_s: avatar em tela cheia.
            A partir de show_at_s: slide ocupa 100% do fundo, avatar reduzido.
            """
            slide_dur  = _get_duration(slide_mp4)
            avatar_dur = _get_duration(avatar_clip)
            total_dur  = avatar_dur

            # Posição do avatar pequeno (bottom-right ou bottom-center)
            if avatar_pos == "bottom-center":
                aw = int(avatar_w * avatar_scale)
                ah = int(avatar_h * avatar_scale)
                ax = (avatar_w - aw) // 2
                ay = avatar_h - ah - 20
            else:  # bottom-right
                aw = int(avatar_w * avatar_scale)
                ah = int(avatar_h * avatar_scale)
                ax = avatar_w - aw - 20
                ay = avatar_h - ah - 20

            # Filtergraph:
            # [0:v] = avatar_clip (tela cheia antes do slide, overlay depois)
            # [1:v] = slide_mp4 (entra em show_at_s, escala para tela cheia)
            # Fase 1 [0..show_at_s): avatar em tela cheia
            # Fase 2 [show_at_s..end]: slide scaled to full, avatar reduzido sobreposto
            filter_complex = (
                f"[0:v]scale={avatar_w}:{avatar_h}:force_original_aspect_ratio=decrease,"
                f"pad={avatar_w}:{avatar_h}:(ow-iw)/2:(oh-ih)/2[avatar_full];"
                f"[1:v]scale={avatar_w}:{avatar_h}:force_original_aspect_ratio=decrease,"
                f"pad={avatar_w}:{avatar_h}:(ow-iw)/2:(oh-ih)/2[slide_full];"
                f"[0:v]scale={aw}:{ah}[avatar_small];"
                f"[slide_full][avatar_small]overlay={ax}:{ay}:enable='gte(t,0)'[slide_with_av];"
                f"[avatar_full][slide_with_av]overlay=0:0:"
                f"enable='gte(t,{show_at_s:.3f})'[out]"
            )

            subprocess.run(
                ["ffmpeg", "-y",
                 "-i", avatar_clip,
                 "-i", slide_mp4,
                 "-filter_complex", filter_complex,
                 "-map", "[out]",
                 "-map", "0:a?",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-shortest",
                 "-t", str(total_dur),
                 output],
                check=True, capture_output=True,
            )

        def _compose_v2() -> None:
            clips: list[str] = []

            with tempfile.TemporaryDirectory(prefix="clips_v2_") as clips_dir_str:
                clips_tmp = Path(clips_tmp_dir := clips_dir_str)

                for i, seg in enumerate(segments):
                    seg_id    = seg.get("id", f"seg_{i}")
                    script    = seg.get("script", "")
                    slide_id  = seg.get("slide")    # string ou None (v2)
                    anchors   = seg.get("anchors", []) or []
                    min_dur   = float(seg.get("min_duration_s", 4.5))
                    pause     = float(seg.get("pause_after_s", 0.4))
                    clip_path = os.path.join(clips_tmp_dir, f"clip_{i:03d}.mp4")

                    # Localiza o arquivo de slide (v2: slug por id)
                    slide_mp4: Optional[str] = None
                    if slide_id:
                        safe_id    = re.sub(r"[^a-z0-9]", "_", str(slide_id).lower())
                        slide_path = slides_dir / f"slide_{safe_id}.mp4"
                        if slide_path.exists():
                            slide_mp4 = str(slide_path)

                    if script:
                        # BUG2 fix: usar o vídeo individual do segmento
                        seg_video = segment_video_paths.get(seg_id)
                        if seg_video and os.path.exists(seg_video):
                            raw_clip = seg_video  # já é o vídeo completo do segmento
                        else:
                            logger.warning(
                                "[v2] Vídeo do segmento %s não encontrado. Gerando clipe preto.", seg_id
                            )
                            raw_clip = os.path.join(clips_tmp_dir, f"raw_{i:03d}.mp4")
                            _generate_black_clip(min_dur + pause, raw_clip)

                        if slide_mp4 and anchors:
                            # Resolve âncoras para timing
                            avatar_dur  = _get_duration(raw_clip)
                            transitions = resolve_anchors(seg, avatar_dur)
                            show_at = next(
                                (tr.time_s for tr in transitions if tr.action == "show_slide"),
                                0.0,
                            )
                            overlay_conf = seg.get("_overlay", {})
                            av_pos   = overlay_conf.get("avatar_position", "bottom-right")
                            av_scale = float(overlay_conf.get("avatar_scale", 0.28))
                            av_w     = 1920 if target == "horizontal" else 1080
                            av_h     = 1080 if target == "horizontal" else 1920

                            _overlay_slide_on_avatar(
                                avatar_clip = raw_clip,
                                slide_mp4   = slide_mp4,
                                show_at_s   = show_at,
                                output      = clip_path,
                                avatar_w    = av_w,
                                avatar_h    = av_h,
                                avatar_scale= av_scale,
                                avatar_pos  = av_pos,
                            )
                        else:
                            import shutil
                            shutil.copy2(raw_clip, clip_path)

                    else:
                        # Slide puro (sem fala)
                        if slide_mp4:
                            _trim_clip(slide_mp4, min_dur + pause, clip_path)
                        else:
                            logger.warning("[v2] Slide %s não encontrado para %s", slide_id, seg_id)
                            _generate_black_clip(min_dur + pause, clip_path)

                    if os.path.exists(clip_path):
                        clips.append(clip_path)

                if not clips:
                    # Fallback: primeiro vídeo de segmento disponível
                    first = next(iter(segment_video_paths.values()), None)
                    if first:
                        import shutil
                        shutil.copy2(first, output_path)
                    return

                _concat_clips(clips, output_path)

        await loop.run_in_executor(None, _compose_v2)

    # ──────────────────────────────────────────────────────────────────────────
    # Jump cuts simples via silencedetect do FFmpeg
    # ──────────────────────────────────────────────────────────────────────────

    async def _apply_jump_cuts(self, input_path: str, output_path: str) -> None:
        """Remove silêncios > MIN_SILENCE_SEC usando FFmpeg silencedetect."""
        loop = asyncio.get_event_loop()

        def _cut() -> None:
            # 1. Detectar silêncios
            result = subprocess.run(
                ["ffmpeg", "-i", input_path, "-af",
                 f"silencedetect=noise=-30dB:d={MIN_SILENCE_SEC}",
                 "-f", "null", "-"],
                capture_output=True, text=True, timeout=300,
            )
            silence_log = result.stderr

            # 2. Parsear intervalos de silêncio
            import re
            starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", silence_log)]
            ends   = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", silence_log)]

            if not starts:
                # Sem silêncios detectados — copiar direto
                subprocess.run(["cp", input_path, output_path], check=True)
                return

            # 3. Construir segmentos de fala (inverso dos silêncios)
            total_dur = _get_duration(input_path)
            speech_segments: list[tuple[float, float]] = []
            cursor = 0.0

            for s_start, s_end in zip(starts, ends):
                if s_start > cursor + 0.1:
                    start = max(0.0, cursor - JUMP_CUT_PADDING)
                    end   = min(total_dur, s_start + JUMP_CUT_PADDING)
                    speech_segments.append((round(start, 3), round(end, 3)))
                cursor = s_end

            # Último segmento após o último silêncio
            if cursor < total_dur - 0.1:
                speech_segments.append((
                    max(0.0, cursor - JUMP_CUT_PADDING),
                    total_dur,
                ))

            if not speech_segments:
                subprocess.run(["cp", input_path, output_path], check=True)
                return

            # 4. Cortar e concatenar com FFmpeg trim+concat
            filter_v, filter_a = [], []
            for i, (s, e) in enumerate(speech_segments):
                filter_v.append(f"[0:v]trim=start={s}:end={e},setpts=PTS-STARTPTS[v{i}]")
                filter_a.append(f"[0:a]atrim=start={s}:end={e},asetpts=PTS-STARTPTS[a{i}]")

            n = len(speech_segments)
            concat_inputs = "".join(f"[v{i}][a{i}]" for i in range(n))
            filter_complex = ";".join(filter_v + filter_a) + \
                             f";{concat_inputs}concat=n={n}:v=1:a=1[outv][outa]"

            subprocess.run(
                ["ffmpeg", "-y", "-i", input_path,
                 "-filter_complex", filter_complex,
                 "-map", "[outv]", "-map", "[outa]",
                 "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                 "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                 output_path],
                check=True, capture_output=True, timeout=600,
            )
            logger.info(
                "[VideoEditorJob] Jump cuts: %d segmentos de fala → %s",
                len(speech_segments), output_path,
            )

        try:
            await loop.run_in_executor(None, _cut)
        except Exception as exc:
            logger.warning("[VideoEditorJob] Jump cuts falhou (%s), copiando original.", exc)
            import shutil
            shutil.copy2(input_path, output_path)

    # ──────────────────────────────────────────────────────────────────────────
    # GCS helpers
    # ──────────────────────────────────────────────────────────────────────────

    async def _load_manifest(self, project_id: str) -> Manifest:
        project = await self.firestore.get_project(project_id)
        gcs_path = project["manifest_url"]
        bucket_name, blob_path = gcs_path.replace("gs://", "").split("/", 1)
        bucket  = self.gcs.bucket(bucket_name)
        blob    = bucket.blob(blob_path)
        loop    = asyncio.get_event_loop()
        content = await loop.run_in_executor(None, blob.download_as_text)
        return Manifest._parse_from_html(content)

    async def _download_html_manifest(self, project_id: str, work_dir: Path) -> Path:
        project  = await self.firestore.get_project(project_id)
        gcs_path = project["manifest_url"]
        bucket_name, blob_path = gcs_path.replace("gs://", "").split("/", 1)
        bucket   = self.gcs.bucket(bucket_name)
        blob     = bucket.blob(blob_path)
        dest     = work_dir / "manifest.html"
        loop     = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: blob.download_to_filename(str(dest)))
        return dest

    async def _download_from_gcs(self, gcs_uri: str, dest: Path) -> Path:
        bucket_name, blob_path = gcs_uri.replace("gs://", "").split("/", 1)
        bucket = self.gcs.bucket(bucket_name)
        blob   = bucket.blob(blob_path)
        loop   = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: blob.download_to_filename(str(dest)))
        logger.info("[VideoEditorJob] Baixado: %s → %s", gcs_uri, dest)
        return dest

    async def _upload_to_gcs(self, local_path: str, project_id: str, target: str) -> str:
        gcs_path = f"projects/{project_id}/final_{target}.mp4"
        bucket   = self.gcs.bucket(self.gcs_bucket)
        blob     = bucket.blob(gcs_path)
        loop     = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, lambda: blob.upload_from_filename(local_path, content_type="video/mp4")
        )
        return f"gs://{self.gcs_bucket}/{gcs_path}"


# ──────────────────────────────────────────────────────────────────────────────
# Funções FFmpeg utilitárias (síncronas, chamadas via run_in_executor)
# ──────────────────────────────────────────────────────────────────────────────

def _get_duration(path: str) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True,
    )
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 10.0


def _extract_clip(src: str, start: float, duration: float, dest: str) -> None:
    """Extrai um trecho do vídeo avatar sem re-encode (rápido)."""
    subprocess.run(
        ["ffmpeg", "-y", "-ss", str(start), "-i", src,
         "-t", str(duration), "-c", "copy", dest],
        check=True, capture_output=True, timeout=120,
    )


def _trim_clip(src: str, duration: float, dest: str) -> None:
    """Trim de um clipe de slide para duração exata."""
    subprocess.run(
        ["ffmpeg", "-y", "-i", src, "-t", str(duration),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "18",
         "-an", dest],
        check=True, capture_output=True, timeout=120,
    )


def _generate_black_clip(duration: float, dest: str) -> None:
    """Gera clipe preto como fallback quando slide não existe."""
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"color=c=black:size=1920x1080:duration={duration}:rate=25",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", dest],
        check=True, capture_output=True, timeout=60,
    )


def _concat_clips(clips: list[str], dest: str) -> None:
    """Concatena lista de clipes MP4 via FFmpeg concat demuxer."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, prefix="concat_"
    ) as f:
        for c in clips:
            f.write(f"file '{c}'\n")
        list_file = f.name

    try:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "18",
             "-c:a", "aac", "-b:a", "192k", dest],
            check=True, capture_output=True, timeout=600,
        )
    finally:
        os.unlink(list_file)
