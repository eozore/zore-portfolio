"""
agents/pipeline/avatar_job/job.py
====================================
AvatarJob: gera vídeos de avatar via HeyGen Video Generation API v3.

IMPORTANTE: Este job processa APENAS segmentos que precisam de avatar (sem slide).
Segmentos com slide são processados diretamente no video_editor_job (HTML + áudio TTS).

Fluxo:
  1. Recebe TtsCompletedMsg com heygen_segment_ids (segmentos sem slide)
  2. Para cada segmento em heygen_segment_ids:
     - Download do áudio do GCS
     - Upload para HeyGen Assets API → audio_asset_id
     - POST /v3/videos com avatar_id + audio_asset_id + engine
  3. Salva video_ids no Firestore + registra callback_id
  4. TERMINA — HeyGenCallbackHandler recebe o resultado via webhook

Se não houver segmentos HeyGen (todos são slide+áudio), o job:
  - Marca status como "completed"
  - Dispara AvatarCompletedMsg vazio para o video_editor_job
"""

import asyncio
import logging
import os
import time
from typing import Literal

import requests
from google.cloud import storage

from shared.cost_tracker import CostTrackerService, usd_por_segundo
from shared.firestore_client import FirestoreClient
from shared.models import TtsCompletedMsg
from shared.pubsub_client import PubSubClient
from shared.retry import ApiError, with_retry

logger = logging.getLogger(__name__)

# Base configurável para permitir apontar ao stub local sem tocar em código.
# Era constante fixa: o ambiente de validação não conseguia interceptar a
# chamada, e testar o fluxo de avatar exigia gastar crédito de verdade.
HEYGEN_BASE_URL = os.environ.get("HEYGEN_BASE_URL", "https://api.heygen.com").rstrip("/")

# Motor de renderização do HeyGen v3.
#
# É O parâmetro que mais mexe na sincronia labial, e explica por que um vídeo
# feito na plataforma web ficava melhor que o da API com o MESMO áudio: o
# endpoint legado /v2/video/generate resolve para `avatar_iii`, enquanto o v3
# tem `avatar_iv` como padrão. `avatar_v` usa animação por referência cruzada,
# analisando avatar e áudio juntos — é o de maior fidelidade.
#
# Nem todo avatar suporta todo motor: `supported_api_engines` no look diz
# quais valem, e o job checa isso antes de gastar (ver _motor_elegivel).
HEYGEN_ENGINE = os.environ.get("HEYGEN_ENGINE", "avatar_v")

# Resolução e proporção substituem o antigo `dimension` do v2.
FORMATO_POR_TARGET: dict[str, dict] = {
    "horizontal": {"aspect_ratio": "16:9", "resolution": "1080p"},
    "vertical":   {"aspect_ratio": "9:16", "resolution": "1080p"},
}

CONTENT_TYPE_POR_EXTENSAO = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
}


class CostGateBlockedError(Exception):
    pass


class AvatarJob:
    def __init__(
        self,
        firestore: FirestoreClient,
        pubsub: PubSubClient,
        heygen_api_key: str,
        gcs_bucket: str,
        callback_url: str,
        tenant_id: str = "default",
    ) -> None:
        self.firestore    = firestore
        self.pubsub       = pubsub
        self.heygen_key   = heygen_api_key
        self.gcs_bucket   = gcs_bucket
        self.callback_url = callback_url
        self.cost         = CostTrackerService(firestore, tenant_id)
        self.gcs          = storage.Client()

    async def _saldo_usd(self) -> float | None:
        """
        Saldo disponível em DÓLARES, via GET /v3/users/me. None = indisponível.

        Substitui `/v2/user/remaining_quota`, que a HeyGen remove em
        2026-10-31 e que devolvia `details.api` numa unidade opaca — era ela
        que fazia o log dizer "17 créditos" enquanto a plataforma mostrava
        ~US$10. O v3 declara `billing_type` e a unidade de cada campo.

        Três formas de cobrança, mutuamente exclusivas:
          wallet      → remaining_balance, em USD (pay-as-you-go)
          usage_based → remaining_credits, mais teto e gasto corrente em USD
          subscription→ créditos do plano, que a API NÃO consome
        """
        try:
            resp = await asyncio.to_thread(
                lambda: requests.get(
                    f"{HEYGEN_BASE_URL}/v3/users/me",
                    headers={"X-Api-Key": self.heygen_key}, timeout=20,
                )
            )
            if resp.status_code != 200:
                logger.warning("[AvatarJob] GET /v3/users/me: HTTP %s", resp.status_code)
                return None
            dados = resp.json().get("data") or {}
        except Exception as exc:
            logger.warning("[AvatarJob] Saldo HeyGen indisponível (%s).", exc)
            return None

        tipo = dados.get("billing_type")

        if tipo == "wallet":
            carteira = dados.get("wallet") or {}
            return float(carteira.get("remaining_balance") or 0.0)

        if tipo == "usage_based":
            uso = dados.get("usage_based") or {}
            teto  = uso.get("spending_cap_usd")
            gasto = uso.get("spending_current_usd")
            if teto is not None and gasto is not None:
                return max(0.0, float(teto) - float(gasto))
            # Sem teto declarado, `remaining_credits` é o que sobra — e 1
            # crédito equivale a 1 dólar na tabela pay-as-you-go da HeyGen.
            return float(uso.get("remaining_credits") or 0.0)

        if tipo == "subscription":
            # Os créditos da assinatura são de outro pool: a API não os
            # consome. Tratar como saldo aqui deixaria o gate passar uma
            # produção que a HeyGen vai recusar.
            logger.warning(
                "[AvatarJob] Conta em 'subscription' — a API consome pool "
                "próprio (pay-as-you-go), não os créditos do plano."
            )
            return 0.0

        logger.warning("[AvatarJob] billing_type desconhecido: %r", tipo)
        return None

    async def _credito_insuficiente(self, duracao_s: float) -> str | None:
        """
        Devolve a mensagem de bloqueio, ou None se há saldo.

        Falha ABERTO de propósito: se a consulta de saldo não responder, o job
        segue. Um endpoint de quota fora do ar não deve impedir uma produção
        que talvez tivesse crédito — o erro do HeyGen na geração ainda pegaria
        o caso, só que mais tarde.
        """
        saldo = await self._saldo_usd()
        if saldo is None:
            return None

        necessario = duracao_s * usd_por_segundo(HEYGEN_ENGINE)
        logger.info(
            "[AvatarJob] Saldo HeyGen: US$%.2f; %s precisa de ~US$%.2f para %.0fs.",
            saldo, HEYGEN_ENGINE, necessario, duracao_s,
        )
        if saldo >= necessario:
            return None

        return (
            f"Saldo HeyGen insuficiente: US${saldo:.2f} disponíveis, "
            f"~US${necessario:.2f} necessários para {duracao_s:.0f}s de avatar "
            f"em {HEYGEN_ENGINE}. Recarregue antes de aprovar a produção."
        )

    async def _registrar_custo_medido(
        self, saldo_antes: float | None, duracao_s: float, motor: str,
    ) -> None:
        """
        Mede o custo REAL pela variação do saldo e loga contra a estimativa.

        Existe porque nenhuma das duas fontes de preço é confiável: a HeyGen
        não publica a tarifa do `avatar_v`, e o webhook de conclusão não
        devolve custo nenhum. O saldo é a única grandeza observável.

        Só loga — não corrige `USD_POR_MINUTO_POR_MOTOR` sozinho. Uma tarifa
        que se ajusta em silêncio a partir de uma amostra ruidosa (produções
        concorrentes mexem no mesmo saldo) é pior que uma constante errada e
        visível.
        """
        if saldo_antes is None or duracao_s <= 0:
            return
        saldo_depois = await self._saldo_usd()
        if saldo_depois is None:
            return

        gasto = saldo_antes - saldo_depois
        if gasto <= 0:
            # A cobrança do HeyGen pode não ter liquidado ainda no momento em
            # que os disparos terminam.
            logger.info(
                "[AvatarJob] Saldo inalterado (US$%.2f) logo após o disparo — "
                "a cobrança do HeyGen ainda não liquidou.", saldo_antes,
            )
            return

        medido   = gasto / duracao_s * 60.0
        estimado = usd_por_segundo(motor) * 60.0
        logger.info(
            "[AvatarJob] Custo medido: US$%.2f por %.0fs em %s = US$%.2f/min "
            "(estimado US$%.2f/min, desvio %+.0f%%).",
            gasto, duracao_s, motor, medido, estimado,
            (medido / estimado - 1) * 100 if estimado else 0.0,
        )

    async def _motor_elegivel(self, avatar_id: str) -> str:
        """
        Confirma que o avatar aceita HEYGEN_ENGINE; senão devolve o padrão.

        `avatar_v` só existe para looks que o declaram em
        `supported_api_engines`. Pedir sem checar devolve erro na geração —
        depois de já ter subido o áudio, e uma vez por segmento. Uma consulta
        no começo do job troca N falhas tardias por uma decisão explícita.

        Falha ABERTO: se a consulta não responder, segue com o motor pedido e
        deixa a geração decidir.
        """
        if HEYGEN_ENGINE == "avatar_iv":
            return HEYGEN_ENGINE          # padrão do v3, não precisa de checagem
        try:
            resp = await asyncio.to_thread(
                lambda: requests.get(
                    f"{HEYGEN_BASE_URL}/v3/avatars/looks/{avatar_id}",
                    headers={"X-Api-Key": self.heygen_key}, timeout=20,
                )
            )
            if resp.status_code != 200:
                logger.warning(
                    "[AvatarJob] Não consegui checar motores do avatar %s (HTTP %s); "
                    "seguindo com %s.", avatar_id, resp.status_code, HEYGEN_ENGINE,
                )
                return HEYGEN_ENGINE
            suportados = (resp.json().get("data") or {}).get("supported_api_engines") or []
        except Exception as exc:
            logger.warning("[AvatarJob] Checagem de motor falhou (%s); seguindo.", exc)
            return HEYGEN_ENGINE

        if not suportados or HEYGEN_ENGINE in suportados:
            return HEYGEN_ENGINE

        logger.warning(
            "[AvatarJob] Avatar %s não suporta %s (aceita: %s). Usando avatar_iv.",
            avatar_id, HEYGEN_ENGINE, ", ".join(suportados),
        )
        return "avatar_iv"

    async def run(self, msg: TtsCompletedMsg) -> None:
        """
        Processa apenas segmentos que precisam de HeyGen (avatar falando).
        Segmentos com slide são processados diretamente no video_editor_job.
        """
        project_id = msg.project_id

        # Idempotência
        project = await self.firestore.get_project(project_id)
        avatar_status = project["stages"]["avatar"]["status"]
        if avatar_status in ("completed", "pending_callback"):
            logger.info(
                "[AvatarJob] Avatar já em status '%s' para %s. Ignorando.",
                avatar_status, project_id,
            )
            return

        await self.firestore.update_stage(project_id, "avatar", {
            "status": "running",
            "started_at": int(time.time()),
        })

        try:
            # Filtra apenas segmentos que precisam de HeyGen (kind == "avatar")
            heygen_segment_ids = getattr(msg, 'heygen_segment_ids', {}) or {}
            slide_audio_segment_ids = getattr(msg, 'slide_audio_segment_ids', {}) or {}

            # Só o target horizontal consome crédito daqui em diante.
            heygen_segment_ids = {"horizontal": heygen_segment_ids.get("horizontal", [])}
            heygen_segment_count = len(heygen_segment_ids["horizontal"])

            if heygen_segment_count == 0:
                # Não há segmentos de avatar — pular HeyGen, ir direto para video_editor
                logger.info(
                    "[AvatarJob] Nenhum segmento precisa de HeyGen para %s. "
                    "Todos os %d segmentos são slide+áudio.",
                    project_id,
                    sum(len(ids) for ids in slide_audio_segment_ids.values()),
                )
                await self.firestore.update_stage(project_id, "avatar", {
                    "status": "completed",
                    "completed_at": int(time.time()),
                    "skipped_reason": "no_heygen_segments",
                    "slide_audio_paths": msg.audio_paths,  # salva para o video_editor
                    "slide_audio_segment_ids": slide_audio_segment_ids,
                })
                # Dispara video_editor diretamente via Pub/Sub
                from shared.models import AvatarCompletedMsg
                completed_msg = AvatarCompletedMsg(
                    project_id=project_id,
                    horizontal_video_paths=[],  # sem vídeos HeyGen
                    vertical_video_paths=[],
                    segment_ids=[],
                    vertical_segment_ids=[],
                    duration_seconds=0.0,
                    total_cost_usd=0.0,
                )
                AVATAR_COMPLETED_TOPIC = "content-pipeline.avatar-completed"
                self.pubsub.publish(AVATAR_COMPLETED_TOPIC, completed_msg)
                return

            # Cost gate sobre a duração REAL dos segmentos de avatar, enviada
            # pelo tts_job. O chute anterior de 5s por segmento subestimava em
            # 3 a 5 vezes uma produção com segmentos de 12 a 25s — o gate
            # aprovava gastos que nunca teria aprovado se soubesse o tamanho.
            total_duration_s = getattr(msg, "heygen_duration_s", 0.0) or (
                heygen_segment_count * 18.0
            )
            estimated_cost   = await self.cost.estimate_heygen_cost(total_duration_s)
            # Lê a config do TENANT DESTE JOB, não de "default" fixo — com um
            # único tenant a diferença nunca apareceu, mas ler sempre
            # "default" faria o teto e o orçamento mensal de qualquer outro
            # tenant serem avaliados contra a configuração de outro tenant.
            config           = await self.firestore.get_pipeline_config(self.cost.tenant_id)
            can_proceed      = await self.cost.check_cost_gate(
                project_id, estimated_cost, config.get("cost_limit", 100.0)
            )
            if not can_proceed:
                raise CostGateBlockedError(
                    f"Custo HeyGen bloqueado: estimado={estimated_cost:.2f} BRL"
                )

            # Gate mensal do tenant (independente do teto por projeto acima).
            if not await self.cost.check_tenant_budget():
                raise CostGateBlockedError(
                    f"Orçamento mensal do tenant '{self.cost.tenant_id}' esgotado — "
                    "HeyGen bloqueado até o próximo mês ou aumento do teto."
                )

            # Saldo REAL do HeyGen, consultado antes de disparar.
            #
            # Sem isto o pedido é aceito, o HeyGen recusa no DEDUCT_QUOTA por
            # falta de crédito e NÃO dispara webhook nenhum (ele nem registra o
            # callback_id). O projeto fica em pending_callback para sempre e
            # ninguém descobre por que — foi exatamente o que travou o vídeo
            # longo do primeiro ciclo real.
            #
            # Atenção ao pool: a conta tem 'plan_credit' (usado pelo app web) e
            # 'api' (usado por esta pipeline). Ter 2000 créditos de plano não
            # ajuda em nada aqui.
            faltou = await self._credito_insuficiente(total_duration_s)
            if faltou:
                raise CostGateBlockedError(faltou)

            # Avatar IDs de cada formato
            avatar_h_id = os.environ.get("HEYGEN_AVATAR_ID_HORIZONTAL", "32e2ad6b3e5a45bf8c61cbf7220912f4")
            avatar_v_id = os.environ.get("HEYGEN_AVATAR_ID_VERTICAL",   "d7fdce2942a244649820a0b5c989766f")
            avatar_ids  = {"horizontal": avatar_h_id, "vertical": avatar_v_id}

            # Uma checagem de motor por rodada, não por segmento: pedir um
            # motor que o avatar não aceita falha na geração, depois de o
            # áudio já ter subido.
            motor = await self._motor_elegivel(avatar_h_id)

            # Saldo ANTES, para medir o custo real da produção. O preço do
            # avatar_v não é publicado e o webhook do HeyGen não devolve custo
            # nenhum — a diferença de saldo é a única medida verdadeira, e é
            # ela que corrige a estimativa de USD_POR_MINUTO_POR_MOTOR.
            saldo_antes = await self._saldo_usd()

            # Salva slide_audio info no Firestore para o video_editor
            await self.firestore.update_stage(project_id, "avatar", {
                "slide_audio_paths": msg.audio_paths,
                "slide_audio_segment_ids": slide_audio_segment_ids,
            })

            # SÓ HORIZONTAL. A peça vertical é um recorte 9:16 deste mesmo
            # clipe, feito com FFmpeg depois que o vídeo do YouTube é aprovado.
            #
            # Gerar os dois formatos aqui dobrava o custo do avatar pela MESMA
            # fala e, pior, acoplava um ao outro: o heygen_callback só liberava
            # a edição quando os dois voltassem, então uma recusa no vertical
            # (crédito insuficiente) travava para sempre um horizontal que já
            # estava pronto no bucket. Foi exatamente assim que o vídeo longo
            # do primeiro ciclo real nunca chegou a ser montado.
            for target in ("horizontal",):
                heygen_ids_for_target = heygen_segment_ids.get(target, [])
                all_audio_paths = msg.audio_paths.get(target, [])
                
                if not heygen_ids_for_target:
                    logger.info("[AvatarJob] Sem segmentos HeyGen para target=%s, pulando.", target)
                    continue

                segment_videos: list[dict] = []

                # Mapeia seg_id → audio_path
                # O TTS gera áudios na ordem dos segmentos do manifesto
                # Precisamos filtrar apenas os que são HeyGen
                audio_path_map: dict[str, str] = {}
                for path in all_audio_paths:
                    seg_id = os.path.splitext(os.path.basename(path))[0]
                    audio_path_map[seg_id] = path

                for idx, seg_id in enumerate(heygen_ids_for_target):
                    seg_path = audio_path_map.get(seg_id)
                    if not seg_path:
                        logger.warning(
                            "[AvatarJob] Áudio não encontrado para seg_id=%s, pulando.", seg_id
                        )
                        continue

                    logger.info(
                        "[AvatarJob] Processando segmento HeyGen %d/%d: %s (target=%s)",
                        idx + 1, len(heygen_ids_for_target), seg_id, target,
                    )

                    try:
                        # 1. Baixar segmento do GCS para /tmp
                        local_audio = await self._download_segment_from_gcs(seg_path)

                        # 2. Upload individual por segmento para HeyGen Assets
                        audio_asset_id = await with_retry(
                            lambda p=local_audio: self._upload_to_heygen_assets(p),
                            max_retries=3, backoff=[1.0, 4.0, 16.0],
                            transient_errors=(429, 503),
                            project_id=project_id, stage_id="avatar",
                            firestore=self.firestore,
                        )
                        # Limpa arquivo local após upload
                        try:
                            os.remove(local_audio)
                        except OSError:
                            pass

                        logger.info(
                            "[AvatarJob] Upload OK: seg=%s asset_id=%s", seg_id, audio_asset_id
                        )

                        # 3. Gerar vídeo individual para este segmento
                        video_id = await with_retry(
                            lambda aid=audio_asset_id, av=avatar_ids[target], t=target, sid=seg_id, e=motor: \
                                self._generate_avatar_video(aid, av, t, project_id, sid, e),
                            max_retries=3, backoff=[1.0, 4.0, 16.0],
                            transient_errors=(429, 503),
                            project_id=project_id, stage_id="avatar",
                            firestore=self.firestore,
                        )
                        logger.info(
                            "[AvatarJob] Vídeo criado: seg=%s video_id=%s", seg_id, video_id
                        )

                        segment_videos.append({
                            "seg_id":   seg_id,
                            "video_id": video_id,
                            "status":   "pending",
                            "video_url": None,
                        })

                    except Exception as seg_err:
                        logger.error(
                            "[AvatarJob] Falha no segmento %s: %s", seg_id, seg_err
                        )
                        segment_videos.append({
                            "seg_id":   seg_id,
                            "video_id": None,
                            "status":   "failed",
                            "video_url": None,
                            "error":    str(seg_err),
                        })

                    # Delay entre chamadas HeyGen para evitar rate limit
                    if idx < len(heygen_ids_for_target) - 1:
                        await asyncio.sleep(0.5)

                # Salva lista de segment_videos no Firestore por target
                await self.firestore.update_stage(project_id, "avatar", {
                    f"segment_videos.{target}": segment_videos,
                })
                logger.info(
                    "[AvatarJob] %d segmentos HeyGen enfileirados para %s (target=%s).",
                    len([s for s in segment_videos if s["status"] != "failed"]),
                    project_id, target,
                )

            await self.firestore.update_stage(project_id, "avatar", {
                "status": "pending_callback",
                "cost_estimated": estimated_cost,
            })

            # Soma no mês do tenant NO MOMENTO DO DISPARO, não na confirmação
            # do callback: o HeyGen cobra pela geração pedida, e a API não
            # devolve custo real nenhum no webhook — a estimativa pré-voo é o
            # único número que existe. Registrar aqui, uma vez por rodada de
            # segmentos (não por segmento), evita contar duas vezes numa
            # idempotência que já verificou "avatar_status in (completed,
            # pending_callback)" no topo de run().
            await self.cost.record_tenant_spend_estimate_usd(
                total_duration_s * usd_por_segundo(motor)
            )

            await self._registrar_custo_medido(saldo_antes, total_duration_s, motor)

            logger.info(
                "[AvatarJob] Todos os segmentos HeyGen iniciados para %s. Aguardando callbacks.",
                project_id,
            )

        except CostGateBlockedError as exc:
            await self.firestore.update_stage(project_id, "avatar", {
                "status": "error",
                "error_message": str(exc),
                "error_type": "permanent",
            })
            raise
        except Exception as exc:
            await self.firestore.update_stage(project_id, "avatar", {
                "status": "error",
                "error_message": str(exc),
                "error_type": "transient",
            })
            raise

    async def _download_segment_from_gcs(self, gcs_uri: str) -> str:
        """Baixa um segmento de áudio do GCS para /tmp e retorna o path local."""
        bucket_name, blob_path = gcs_uri.replace("gs://", "").split("/", 1)
        filename    = os.path.basename(blob_path)
        local_path  = f"/tmp/{filename}"
        loop        = asyncio.get_event_loop()

        bucket = self.gcs.bucket(bucket_name)
        blob   = bucket.blob(blob_path)
        audio_bytes = await loop.run_in_executor(None, blob.download_as_bytes)

        with open(local_path, "wb") as f:
            f.write(audio_bytes)

        logger.debug("[AvatarJob] Download GCS: %s → %s (%d bytes)", gcs_uri, local_path, len(audio_bytes))
        return local_path

    async def _upload_to_heygen_assets(self, local_path: str) -> str:
        """POST /v3/assets (multipart/form-data) → retorna asset_id."""
        url  = f"{HEYGEN_BASE_URL}/v3/assets"
        H    = {"X-Api-Key": self.heygen_key}
        loop = asyncio.get_event_loop()

        # O content-type vem da extensão real. O TTS passou a emitir WAV
        # (PCM sem perda) quando o plano da ElevenLabs permite, e declarar
        # 'audio/mpeg' para um WAV faz o HeyGen recusar o upload.
        content_type = CONTENT_TYPE_POR_EXTENSAO.get(
            os.path.splitext(local_path)[1].lower(), "audio/mpeg",
        )

        def _upload() -> str:
            with open(local_path, "rb") as f:
                resp = requests.post(
                    url,
                    headers=H,
                    files={"file": (os.path.basename(local_path), f, content_type)},
                    timeout=120,
                )
            if resp.status_code not in (200, 201):
                raise ApiError(resp.status_code, resp.text[:200])
            return resp.json()["data"]["asset_id"]

        return await loop.run_in_executor(None, _upload)

    async def _generate_avatar_video(
        self,
        audio_asset_id: str,
        avatar_id: str,
        target: Literal["horizontal", "vertical"],
        project_id: str,
        seg_id: str = "",
        engine: str = HEYGEN_ENGINE,
    ) -> str:
        """
        POST /v3/videos — avatar dirigido pelo áudio já sintetizado.

        Migrado do `/v2/video/generate`, que a HeyGen remove em 2026-10-31 e
        que resolvia para `avatar_iii`. O corpo mudou de forma: era aninhado
        (`video_inputs[].character`, `.voice`, `dimension`) e agora é plano,
        com `aspect_ratio` + `resolution` no lugar de pixels.

        O `_generate` antigo tinha um "fallback para v3" que mandava o corpo
        do v2 para o endpoint v3 — schema incompatível, então esse caminho
        nunca teve como funcionar. Removido: um fallback que não funciona só
        transforma o erro real num erro de validação confuso.

        callback_id é "{project_id}__{target}__{seg_id}", o que permite ao
        heygen_callback resolver o segmento exato via Firestore.
        """
        url  = f"{HEYGEN_BASE_URL}/v3/videos"
        H    = {"X-Api-Key": self.heygen_key, "Content-Type": "application/json"}
        fmt  = FORMATO_POR_TARGET[target]
        loop = asyncio.get_event_loop()

        callback_id = f"{project_id}__{target}__{seg_id}" if seg_id else f"{project_id}__{target}"

        payload = {
            "type":           "avatar",
            "avatar_id":      avatar_id,
            # Mutuamente exclusivo com `script`: o áudio vem do ElevenLabs,
            # porque o clone de voz do HeyGen não tem a qualidade necessária.
            "audio_asset_id": audio_asset_id,
            "aspect_ratio":   fmt["aspect_ratio"],
            "resolution":     fmt["resolution"],
            "engine":         {"type": engine},
            "callback_url":   f"{self.callback_url}/heygen-video-callback",
            "callback_id":    callback_id,
        }

        def _generate() -> str:
            resp = requests.post(url, headers=H, json=payload, timeout=60)
            if resp.status_code not in (200, 201, 202):
                raise ApiError(resp.status_code, resp.text[:300])
            data = resp.json().get("data") or {}
            video_id = data.get("video_id")
            if not video_id:
                raise ApiError(502, f"v3 não devolveu video_id: {resp.text[:200]}")
            return video_id

        return await loop.run_in_executor(None, _generate)
