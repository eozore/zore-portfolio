"""
agents/pipeline/tts_job/job.py
================================
TTSJob: Text-to-Speech via ElevenLabs para cada segmento de áudio do manifesto.

Regra crítica:
  Segmentos com script == "" (slide puro) são completamente ignorados.
  Apenas segmentos com script != "" geram áudio e custam créditos ElevenLabs.

Sobre modelo e formato: este áudio não é só ouvido, ele é a ÚNICA entrada que
o HeyGen tem para inferir os fonemas e animar a boca do avatar. Duas escolhas
que existiam aqui prejudicavam isso sem contrapartida:

  - `eleven_flash_v2_5` é o modelo de latência ultrabaixa (~75ms), feito para
    IA conversacional em tempo real. Esta pipeline é batch — o vídeo leva
    minutos e ninguém espera o primeiro byte. Era penalidade de prosódia
    paga por uma latência que não se usa.
  - `mp3_44100_128` faz o sinal passar por um codec com perda ANTES de o
    HeyGen extrair fonema dele.

Agora: `eleven_multilingual_v2` (o modelo que a própria ElevenLabs indica para
locução) e PCM embrulhado em WAV. PCM a 44.1kHz exige tier Pro na ElevenLabs,
daí a cadeia de fallback em FORMATOS_PREFERIDOS — uma conta fora do Pro
degrada para 24kHz sem perda, e só em último caso volta para MP3.
"""

import asyncio
import base64
import io
import json
import logging
import os
import re
import time
import wave
from typing import Literal

import requests
from google.cloud import storage

from shared.cost_tracker import CostTrackerService
from shared.firestore_client import FirestoreClient
from shared.models import Manifest, PackageApprovedMsg, Segment, TtsCompletedMsg
from shared.pubsub_client import PubSubClient
from shared.retry import ApiError, with_retry

logger = logging.getLogger(__name__)

# Base configurável — ver a mesma nota em avatar_job/job.py.
ELEVENLABS_BASE_URL = os.environ.get("ELEVENLABS_BASE_URL", "https://api.elevenlabs.io").rstrip("/")
TTS_COMPLETED_TOPIC = "content-pipeline.tts-completed"

# Modelo de síntese. `eleven_multilingual_v2` é o que a ElevenLabs indica para
# locução e conteúdo; `eleven_flash_v2_5` só ganha em latência, que aqui não
# vale nada.
ELEVENLABS_MODEL_ID = os.environ.get("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")

# Formatos em ordem de preferência. Sem perda vem primeiro porque o HeyGen
# extrai fonema deste sinal. `pcm_44100` exige tier Pro; `pcm_24000` está
# disponível abaixo dele e ainda é sem perda. MP3 é o último recurso.
#
# (formato ElevenLabs, taxa de amostragem, extensão, content-type)
FORMATOS_PREFERIDOS: tuple[tuple[str, int, str, str], ...] = (
    ("pcm_44100",     44100, "wav", "audio/wav"),
    ("pcm_24000",     24000, "wav", "audio/wav"),
    ("mp3_44100_192", 44100, "mp3", "audio/mpeg"),
)

_FORMATO_FORCADO = os.environ.get("ELEVENLABS_OUTPUT_FORMAT", "").strip()


def _pcm_para_wav(pcm: bytes, sample_rate: int) -> bytes:
    """
    Embrulha PCM cru em contêiner WAV.

    A ElevenLabs devolve `pcm_*` como amostras nuas, sem cabeçalho: 16 bits com
    sinal, little-endian, mono. Sem o cabeçalho o HeyGen recusa o upload, e o
    ffmpeg precisaria de flags de formato em todo ponto que tocasse o arquivo.
    """
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)          # 16 bits
        w.setframerate(sample_rate)
        w.writeframes(pcm)
    return buf.getvalue()


class ManifestParseError(Exception):
    pass


class CostLimitExceededError(Exception):
    pass


def _parse_manifest(html_content: str) -> Manifest:
    """Parseia manifesto HTML para dataclass Manifest via BeautifulSoup."""
    return Manifest._parse_from_html(html_content)


class TTSJob:
    def __init__(
        self,
        firestore: FirestoreClient,
        pubsub: PubSubClient,
        elevenlabs_api_key: str,
        voice_id: str,
        gcs_bucket: str,
        tenant_id: str = "default",
    ) -> None:
        self.firestore  = firestore
        self.pubsub     = pubsub
        self.api_key    = elevenlabs_api_key
        self.voice_id   = voice_id
        self.gcs_bucket = gcs_bucket
        self.cost       = CostTrackerService(firestore, tenant_id)
        self.gcs        = storage.Client()

    async def run(self, msg: PackageApprovedMsg) -> None:
        """Entry point principal do Job."""
        project_id = msg.project_id

        # Idempotência
        project = await self.firestore.get_project(project_id)
        if project["stages"]["tts"]["status"] == "completed":
            logger.info("[TTSJob] TTS já concluído para %s. Ignorando.", project_id)
            return

        await self.firestore.update_stage(project_id, "tts", {
            "status": "running",
            "started_at": int(time.time()),
        })

        try:
            manifest = await self._load_manifest(msg.manifest_gcs_path)
            audio_paths, heygen_segment_ids, slide_audio_segment_ids = await self._process_all_targets(
                project_id, manifest, msg.cost_limit
            )

            segment_count = sum(len(p) for p in audio_paths.values())
            total_cost_usd = self._calculate_total_cost_usd(manifest)

            await self.firestore.update_stage(project_id, "tts", {
                "status": "completed",
                "completed_at": int(time.time()),
                "cost_real": total_cost_usd,
            })

            # Duração real dos segmentos de avatar — é ela que define o custo
            # do HeyGen. O avatar_job estimava 5s por segmento, chute que só
            # fazia sentido no roteiro achatado antigo; hoje um segmento de
            # avatar tem de 12 a 25s, e o gate de custo decidia sobre um número
            # 3 a 5 vezes menor que o real.
            heygen_duration_s = round(sum(
                seg.min_duration_s
                for seg in manifest.get_heygen_segments("horizontal")
            ), 1)

            completed_msg = TtsCompletedMsg(
                project_id=project_id,
                audio_paths=audio_paths,
                total_cost_usd=total_cost_usd,
                segment_count=segment_count,
                heygen_segment_ids=heygen_segment_ids,
                slide_audio_segment_ids=slide_audio_segment_ids,
                heygen_duration_s=heygen_duration_s,
            )
            self.pubsub.publish(TTS_COMPLETED_TOPIC, completed_msg)
            logger.info(
                "[TTSJob] Concluído: %d segmentos (HeyGen: %d, SlideAudio: %d) project=%s",
                segment_count,
                sum(len(ids) for ids in heygen_segment_ids.values()),
                sum(len(ids) for ids in slide_audio_segment_ids.values()),
                project_id,
            )

        except CostLimitExceededError as exc:
            await self.firestore.update_stage(project_id, "tts", {
                "status": "error",
                "error_message": str(exc),
                "error_type": "permanent",
            })
            raise
        except Exception as exc:
            error_type = "permanent" if isinstance(exc, ApiError) and exc.status_code in (401, 403) else "transient"
            await self.firestore.update_stage(project_id, "tts", {
                "status": "error",
                "error_message": str(exc),
                "error_type": error_type,
            })
            raise

    async def _load_manifest(self, gcs_path: str) -> Manifest:
        """Lê manifesto HTML do GCS e parseia."""
        bucket_name, blob_path = gcs_path.replace("gs://", "").split("/", 1)
        bucket = self.gcs.bucket(bucket_name)
        blob   = bucket.blob(blob_path)
        loop = asyncio.get_event_loop()
        content = await loop.run_in_executor(None, blob.download_as_text)
        return _parse_manifest(content)

    async def _process_all_targets(
        self,
        project_id: str,
        manifest: Manifest,
        cost_limit: float,
    ) -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str, list[str]]]:
        """
        Gera o áudio de TODOS os segmentos falados do vídeo horizontal.

        Só horizontal. O corte vertical não tem fala própria — ele reaproveita
        exatamente estes arquivos, porque é um recorte do mesmo vídeo. Antes,
        cada segmento era sintetizado duas vezes com o MESMO texto, uma por
        orientação: o dobro do custo de ElevenLabs para produzir dois áudios
        idênticos.

        Retorna:
            - audio_paths: áudios gerados (chave "horizontal")
            - heygen_segment_ids: segmentos de avatar → consomem HeyGen
            - slide_audio_segment_ids: segmentos de ilustração → HTML + áudio
        """
        audio_paths: dict[str, list[str]] = {"horizontal": [], "vertical": []}
        heygen_segment_ids: dict[str, list[str]] = {"horizontal": [], "vertical": []}
        slide_audio_segment_ids: dict[str, list[str]] = {"horizontal": [], "vertical": []}

        target   = "horizontal"
        segments = manifest.get_tts_segments(target)
        logger.info("[TTSJob] %d segmentos falados no vídeo horizontal", len(segments))

        for segment in segments:
            gcs_path = await self._process_segment(
                project_id, segment, target, cost_limit
            )
            audio_paths[target].append(gcs_path)

            if segment.needs_heygen:
                heygen_segment_ids[target].append(segment.id)
            elif segment.is_slide_with_audio:
                slide_audio_segment_ids[target].append(segment.id)

        return audio_paths, heygen_segment_ids, slide_audio_segment_ids

    async def _process_segment(
        self,
        project_id: str,
        segment: Segment,
        target: Literal["horizontal", "vertical"],
        cost_limit: float,
    ) -> str:
        """Cost gate → TTS → GCS upload para um segmento."""
        # Config do TENANT DESTE JOB — "default" fixo aqui faria o teto de
        # qualquer outro tenant ser avaliado contra a config de outro tenant.
        config = await self.firestore.get_pipeline_config(self.cost.tenant_id)
        limit = cost_limit or config.get("cost_limit", 100.0)
        estimated = await self.cost.estimate_tts_cost(len(segment.script))
        can_proceed = await self.cost.check_cost_gate(project_id, estimated, limit)
        if not can_proceed:
            raise CostLimitExceededError(
                f"Custo excede teto para segment={segment.id} project={project_id}"
            )
        if not await self.cost.check_tenant_budget():
            raise CostLimitExceededError(
                f"Orçamento mensal do tenant '{self.cost.tenant_id}' esgotado — "
                f"TTS bloqueado para segment={segment.id}."
            )

        audio_bytes, alignment, extensao, content_type = await with_retry(
            lambda: self._call_elevenlabs(segment.script),
            max_retries=3,
            backoff=[1.0, 4.0, 16.0],
            transient_errors=(429, 503),
            project_id=project_id,
            stage_id="tts",
            firestore=self.firestore,
        )

        # A extensão vem do formato que a ElevenLabs de fato aceitou, não de
        # uma constante: quem consome deriva o segment_id com splitext, então
        # gravar .mp3 um arquivo WAV quebraria o upload ao HeyGen pelo
        # content-type errado.
        base_path = f"gs://{self.gcs_bucket}/projects/{project_id}/audio/{target}/{segment.id}"
        gcs_path  = f"{base_path}.{extensao}"
        await self._upload_to_gcs(audio_bytes, gcs_path, content_type)

        # Alinhamento ao lado do áudio, como irmão de mesmo nome. É o que o
        # vertical_cut_job lê para gerar as legendas — sem ASR, sem adivinhar.
        # Falha aqui não derruba o TTS: sem alinhamento a legenda cai na
        # estimativa por tamanho de palavra, e um áudio bom com legenda
        # aproximada vale mais do que um segmento perdido.
        if alignment:
            try:
                await self._upload_json_to_gcs(
                    {"segment_id": segment.id, "script": segment.script,
                     "alignment": alignment},
                    f"{base_path}.alignment.json",
                )
            except Exception as exc:
                logger.warning(
                    "[TTSJob] Falha ao salvar alinhamento de %s (legenda cairá em "
                    "estimativa): %s", segment.id, exc,
                )
        else:
            logger.warning(
                "[TTSJob] ElevenLabs não devolveu alinhamento para %s.", segment.id
            )

        cost_usd = len(segment.script) * 0.00005
        await self.cost.update_actual_cost(project_id, "tts", cost_usd)

        return gcs_path

    async def _call_elevenlabs(self, text: str) -> tuple[bytes, dict, str, str]:
        """
        POST /v1/text-to-speech/{voice_id}/with-timestamps.

        Devolve (áudio, alinhamento, extensão, content_type).

        Devolve (áudio, alinhamento). O alinhamento traz o instante de início
        e fim de CADA CARACTERE falado — é a fonte de verdade das legendas do
        corte vertical, e vem pelo MESMO preço da chamada sem timestamps.

        A alternativa seria rodar ASR (Whisper) por cima do áudio já gerado
        para redescobrir tempos que o próprio sintetizador conhecia: mais CPU
        no job, mais uma dependência pesada, e um resultado só aproximado.

        Retorna dict vazio no alinhamento se a resposta não trouxer o campo —
        o chamador cai na estimativa por tamanho de palavra em vez de falhar,
        porque áudio sem legenda ainda é um vídeo utilizável.
        """
        url = f"{ELEVENLABS_BASE_URL}/v1/text-to-speech/{self.voice_id}/with-timestamps"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        loop = asyncio.get_event_loop()

        candidatos = [c for c in FORMATOS_PREFERIDOS if not _FORMATO_FORCADO or c[0] == _FORMATO_FORCADO]
        if not candidatos:
            raise ApiError(400, f"ELEVENLABS_OUTPUT_FORMAT desconhecido: {_FORMATO_FORCADO}")

        ultimo_erro: ApiError | None = None
        for indice, (formato, taxa, extensao, content_type) in enumerate(candidatos):
            payload = {
                "text": text,
                "model_id": ELEVENLABS_MODEL_ID,
                "output_format": formato,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                },
            }
            response = await loop.run_in_executor(
                None,
                lambda p=payload: requests.post(url, json=p, headers=headers, timeout=90),
            )

            if response.status_code != 200:
                erro = ApiError(response.status_code, response.text[:200])
                # 401/403/422 sobre formato é restrição de plano (pcm_44100 é
                # Pro ou acima) — cair para o próximo candidato resolve. Erro
                # de outra natureza sobe: mascarar 429 ou 503 com um downgrade
                # silencioso de qualidade seria pior que falhar.
                degradavel = response.status_code in (401, 403, 422)
                if degradavel and indice < len(candidatos) - 1:
                    logger.warning(
                        "[TTSJob] Formato %s recusado (HTTP %s) — tentando %s. "
                        "PCM a 44.1kHz exige tier Pro na ElevenLabs.",
                        formato, response.status_code, candidatos[indice + 1][0],
                    )
                    ultimo_erro = erro
                    continue
                raise erro

            data = response.json()
            audio_b64 = data.get("audio_base64")
            if not audio_b64:
                raise ApiError(502, "ElevenLabs não retornou audio_base64")

            bruto = base64.b64decode(audio_b64)
            audio = _pcm_para_wav(bruto, taxa) if formato.startswith("pcm_") else bruto

            if indice > 0:
                logger.info("[TTSJob] Áudio gerado em %s (fallback).", formato)

            # `alignment` segue o texto exatamente como enviado;
            # `normalized_alignment` segue o texto após a normalização interna
            # (números por extenso, etc.). A legenda tem que mostrar o que foi
            # ESCRITO no roteiro, então o não-normalizado é o que casa com o
            # script revisado.
            alignment = data.get("alignment") or data.get("normalized_alignment") or {}
            return audio, alignment, extensao, content_type

        raise ultimo_erro or ApiError(502, "nenhum formato de áudio aceito")

    async def _upload_to_gcs(
        self, audio_bytes: bytes, gcs_uri: str, content_type: str = "audio/mpeg",
    ) -> None:
        """Sobe o áudio para o GCS com o content-type do formato real."""
        bucket_name, blob_path = gcs_uri.replace("gs://", "").split("/", 1)
        bucket = self.gcs.bucket(bucket_name)
        blob   = bucket.blob(blob_path)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: blob.upload_from_string(audio_bytes, content_type=content_type),
        )
        logger.debug("[TTSJob] Uploaded: %s (%s)", gcs_uri, content_type)

    async def _upload_json_to_gcs(self, payload: dict, gcs_uri: str) -> None:
        """Upload de JSON (alinhamento de caracteres) para GCS."""
        bucket_name, blob_path = gcs_uri.replace("gs://", "").split("/", 1)
        blob = self.gcs.bucket(bucket_name).blob(blob_path)
        body = json.dumps(payload, ensure_ascii=False)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: blob.upload_from_string(
                body, content_type="application/json; charset=utf-8"
            ),
        )
        logger.debug("[TTSJob] Alinhamento salvo: %s", gcs_uri)

    def _calculate_total_cost_usd(self, manifest: Manifest) -> float:
        """Calcula custo total de todos os segmentos com script (TTS)."""
        total_chars = 0
        for target in ("horizontal", "vertical"):
            for seg in manifest.get_tts_segments(target):
                total_chars += len(seg.script)
        return round(total_chars * 0.00005, 6)
