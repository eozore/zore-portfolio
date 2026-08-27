# -*- coding: utf-8 -*-
"""
Cobertura da migração HeyGen v2 → v3 e da tarifa por motor.

Por que existe: nada aqui tinha teste, e as três coisas que mudaram falham em
silêncio se estiverem erradas.

  - O saldo vinha de `/v2/user/remaining_quota`, que a HeyGen remove em
    2026-10-31 e cuja unidade era opaca: o log dizia "17 créditos" com ~US$10
    na conta. Se a leitura do v3 pegar o campo errado, o gate de crédito passa
    a comparar grandezas diferentes de novo — e ele FALHA ABERTO, então não
    dá erro, só deixa a produção rodar sem saldo.
  - A tarifa era uma constante só, $0.0335/s ($2,01/min), que não corresponde
    a nenhum motor de avatar. Errar aqui é gastar 4x o previsto.
  - O corpo do POST mudou de aninhado para plano. Um campo com nome errado é
    HTTP 422 depois de o áudio já ter subido, uma vez por segmento.
"""

import io
import wave

import pytest

from avatar_job.job import AvatarJob, FORMATO_POR_TARGET, CONTENT_TYPE_POR_EXTENSAO
from shared.cost_tracker import (
    USD_POR_MINUTO_POR_MOTOR,
    USD_POR_MINUTO_PADRAO,
    usd_por_segundo,
)
from tts_job.job import _pcm_para_wav


@pytest.fixture
def job() -> AvatarJob:
    j = AvatarJob.__new__(AvatarJob)      # sem tocar Firestore nem GCS no __init__
    j.heygen_key   = "chave-de-teste"
    j.callback_url = "https://callback.exemplo"
    return j


class RespostaFake:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status
        self.text = str(payload)

    def json(self) -> dict:
        return self._payload


# ── Tarifa por motor ──────────────────────────────────────────────────────────

def test_cada_motor_tem_a_tarifa_publicada():
    # $1/min para o avatar padrão e $4/min para o Avatar IV em 1080p.
    assert usd_por_segundo("avatar_iii") == pytest.approx(1.0 / 60)
    assert usd_por_segundo("avatar_iv")  == pytest.approx(4.0 / 60)


def test_motor_desconhecido_cai_no_mais_caro():
    # Subestimar custo desarma o gate — o erro tem que ser para o lado caro.
    assert usd_por_segundo("avatar_xi") == pytest.approx(USD_POR_MINUTO_PADRAO / 60)
    assert USD_POR_MINUTO_PADRAO == max(USD_POR_MINUTO_POR_MOTOR.values())


def test_tarifa_antiga_nao_sobreviveu():
    # $0.0335/s = $2,01/min era a tarifa de video translation, não a de avatar.
    for motor in USD_POR_MINUTO_POR_MOTOR:
        assert usd_por_segundo(motor) != pytest.approx(0.0335)


def test_env_sobrescreve_a_tarifa(monkeypatch):
    monkeypatch.setenv("HEYGEN_USD_PER_MINUTE", "6")
    assert usd_por_segundo("avatar_v") == pytest.approx(6.0 / 60)


def test_env_invalida_nao_derruba_o_calculo(monkeypatch):
    monkeypatch.setenv("HEYGEN_USD_PER_MINUTE", "muito caro")
    assert usd_por_segundo("avatar_iv") == pytest.approx(4.0 / 60)


# ── Leitura de saldo (GET /v3/users/me) ───────────────────────────────────────

def _mock_users_me(monkeypatch, payload: dict, status: int = 200):
    import avatar_job.job as mod
    monkeypatch.setattr(
        mod.requests, "get", lambda *a, **k: RespostaFake(payload, status),
    )


@pytest.mark.asyncio
async def test_carteira_devolve_saldo_em_dolares(job, monkeypatch):
    _mock_users_me(monkeypatch, {
        "data": {"billing_type": "wallet", "wallet": {"remaining_balance": 9.72}},
    })
    assert await job._saldo_usd() == pytest.approx(9.72)


@pytest.mark.asyncio
async def test_usage_based_usa_teto_menos_gasto(job, monkeypatch):
    _mock_users_me(monkeypatch, {
        "data": {
            "billing_type": "usage_based",
            "usage_based": {"spending_cap_usd": 50.0, "spending_current_usd": 42.5},
        },
    })
    assert await job._saldo_usd() == pytest.approx(7.5)


@pytest.mark.asyncio
async def test_usage_based_sem_teto_cai_nos_creditos(job, monkeypatch):
    _mock_users_me(monkeypatch, {
        "data": {"billing_type": "usage_based", "usage_based": {"remaining_credits": 12.0}},
    })
    assert await job._saldo_usd() == pytest.approx(12.0)


@pytest.mark.asyncio
async def test_assinatura_nao_conta_como_saldo_de_api(job, monkeypatch):
    # Os dois pools são independentes: ter 2239 créditos de plano não paga
    # uma única chamada de API. Contar isso deixaria o gate liberar uma
    # produção que a HeyGen recusa.
    _mock_users_me(monkeypatch, {
        "data": {
            "billing_type": "subscription",
            "subscription": {"credits": {"premium_credits": {"remaining": 2239}}},
        },
    })
    assert await job._saldo_usd() == 0.0


@pytest.mark.asyncio
async def test_saldo_indisponivel_devolve_none(job, monkeypatch):
    _mock_users_me(monkeypatch, {"error": "boom"}, status=500)
    assert await job._saldo_usd() is None


# ── Gate de crédito ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gate_bloqueia_quando_o_saldo_nao_cobre(job, monkeypatch):
    monkeypatch.setattr(AvatarJob, "_saldo_usd", lambda self: _valor(2.00))
    # 60s em avatar_v ($4/min) = US$4,00 > US$2,00
    msg = await job._credito_insuficiente(60.0)
    assert msg is not None and "US$2.00" in msg and "US$4.00" in msg


@pytest.mark.asyncio
async def test_gate_libera_quando_ha_saldo(job, monkeypatch):
    monkeypatch.setattr(AvatarJob, "_saldo_usd", lambda self: _valor(20.0))
    assert await job._credito_insuficiente(60.0) is None


@pytest.mark.asyncio
async def test_gate_falha_aberto_sem_leitura_de_saldo(job, monkeypatch):
    # Endpoint de saldo fora do ar não pode barrar uma produção que talvez
    # tivesse crédito — a geração ainda pegaria o caso.
    monkeypatch.setattr(AvatarJob, "_saldo_usd", lambda self: _valor(None))
    assert await job._credito_insuficiente(60.0) is None


async def _valor(v):
    return v


# ── Corpo do POST /v3/videos ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_payload_v3_tem_a_forma_plana_e_o_motor(job, monkeypatch):
    capturado: dict = {}

    import avatar_job.job as mod

    def fake_post(url, headers=None, json=None, timeout=None):
        capturado["url"]     = url
        capturado["payload"] = json
        return RespostaFake({"data": {"video_id": "vid-1", "status": "waiting"}})

    monkeypatch.setattr(mod.requests, "post", fake_post)

    video_id = await job._generate_avatar_video(
        "asset-1", "avatar-abc", "horizontal", "proj-1", "yt-03", "avatar_v",
    )

    assert video_id == "vid-1"
    assert capturado["url"].endswith("/v3/videos")

    p = capturado["payload"]
    # Forma plana do v3 — o corpo aninhado do v2 dava 422 aqui.
    assert "video_inputs" not in p and "dimension" not in p
    assert p["type"] == "avatar"
    assert p["avatar_id"] == "avatar-abc"
    assert p["audio_asset_id"] == "asset-1"
    assert p["engine"] == {"type": "avatar_v"}
    assert p["aspect_ratio"] == "16:9" and p["resolution"] == "1080p"
    # O callback_id carrega o segmento: sem ele o webhook não sabe qual dos
    # N vídeos chegou.
    assert p["callback_id"] == "proj-1__horizontal__yt-03"


@pytest.mark.asyncio
async def test_vertical_pede_9_16(job, monkeypatch):
    capturado: dict = {}
    import avatar_job.job as mod
    monkeypatch.setattr(mod.requests, "post", lambda url, headers=None, json=None, timeout=None: (
        capturado.update(payload=json) or RespostaFake({"data": {"video_id": "v"}})
    ))
    await job._generate_avatar_video("a", "b", "vertical", "p", "s", "avatar_iv")
    assert capturado["payload"]["aspect_ratio"] == "9:16"


@pytest.mark.asyncio
async def test_resposta_sem_video_id_falha_alto(job, monkeypatch):
    import avatar_job.job as mod
    monkeypatch.setattr(mod.requests, "post", lambda *a, **k: RespostaFake({"data": {}}))
    with pytest.raises(mod.ApiError):
        await job._generate_avatar_video("a", "b", "horizontal", "p", "s", "avatar_v")


def test_todo_target_tem_formato_declarado():
    assert set(FORMATO_POR_TARGET) == {"horizontal", "vertical"}


# ── Áudio: PCM → WAV e content-type ───────────────────────────────────────────

def test_pcm_vira_wav_valido_e_mono_16bit():
    # 0,1s de silêncio a 44,1kHz, 16 bits mono.
    pcm = b"\x00\x00" * 4410
    wav = _pcm_para_wav(pcm, 44100)

    with wave.open(io.BytesIO(wav), "rb") as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getframerate() == 44100
        assert w.getnframes() == 4410
    assert wav[:4] == b"RIFF" and wav[8:12] == b"WAVE"


def test_content_type_acompanha_a_extensao():
    # Declarar audio/mpeg para um WAV faz o HeyGen recusar o upload.
    assert CONTENT_TYPE_POR_EXTENSAO[".wav"] == "audio/wav"
    assert CONTENT_TYPE_POR_EXTENSAO[".mp3"] == "audio/mpeg"


# ── Webhook: v2 e v3 ──────────────────────────────────────────────────────────

from heygen_callback.app import extrair_campos


def test_webhook_v2_continua_sendo_lido():
    # Forma que roda em produção hoje. A migração não pode quebrá-la: há
    # projetos em voo quando o deploy acontece.
    p = extrair_campos({
        "event_type":  "avatar_video.success",
        "video_id":    "vid-1",
        "callback_id": "proj-1__horizontal__yt-03",
        "video_url":   "https://cdn.heygen/v.mp4",
    })
    assert p.video_url == "https://cdn.heygen/v.mp4"
    assert p.callback_id == "proj-1__horizontal__yt-03"
    assert p.event_type == "avatar_video.success"


def test_webhook_aninhado_em_event_data():
    # A OpenAPI do v3 não documenta a forma do webhook; se ela vier envelopada,
    # o modelo antigo devolveria video_url=None e o segmento morreria sem vídeo.
    p = extrair_campos({
        "event_type": "avatar_video.success",
        "event_data": {
            "video_id":    "vid-2",
            "callback_id": "proj-2__horizontal__yt-01",
            "url":         "https://cdn.heygen/w.mp4",
        },
    })
    assert p.video_url == "https://cdn.heygen/w.mp4"
    assert p.video_id == "vid-2"
    assert p.callback_id == "proj-2__horizontal__yt-01"


def test_nome_alternativo_de_url_e_aceito():
    for nome in ("url", "output_url", "download_url"):
        p = extrair_campos({nome: "https://x/v.mp4", "callback_id": "a__b__c"})
        assert p.video_url == "https://x/v.mp4", nome


def test_campo_ausente_vira_none_sem_explodir():
    p = extrair_campos({})
    assert p.video_url is None and p.callback_id is None


def test_string_vazia_nao_conta_como_valor():
    # "" no lugar da URL marcaria o segmento como pronto sem vídeo.
    p = extrair_campos({"video_url": "   ", "url": "https://x/v.mp4"})
    assert p.video_url == "https://x/v.mp4"


# ── Tarifa do TTS por modelo ──────────────────────────────────────────────────

from shared.cost_tracker import (
    USD_POR_CHAR_PADRAO,
    USD_POR_CHAR_POR_MODELO,
    CostTrackerService,
)


class FirestoreFake:
    async def get_pipeline_config(self, _tenant):
        return {"exchange_rate_usd_brl": 1.0}      # BRL = USD, simplifica a asserção


@pytest.fixture
def custo() -> CostTrackerService:
    return CostTrackerService(FirestoreFake(), "default")


@pytest.mark.asyncio
async def test_multilingual_custa_o_dobro_do_flash(custo):
    # A troca de Flash para multilingual_v2 dobra o custo por caractere; manter
    # a tarifa do Flash subestimaria o gasto pela metade.
    flash = await custo.estimate_tts_cost(10_000, "eleven_flash_v2_5")
    multi = await custo.estimate_tts_cost(10_000, "eleven_multilingual_v2")
    assert multi == pytest.approx(flash * 2)


@pytest.mark.asyncio
async def test_modelo_desconhecido_nao_derruba_a_producao(custo):
    # Antes isto levantava ValueError e matava o job por causa de uma
    # ESTIMATIVA. Agora cai na tarifa mais alta.
    valor = await custo.estimate_tts_cost(1_000, "eleven_modelo_do_futuro")
    assert valor == pytest.approx(1_000 * USD_POR_CHAR_PADRAO)


@pytest.mark.asyncio
async def test_modelo_padrao_vem_do_ambiente(custo, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_MODEL_ID", "eleven_flash_v2_5")
    valor = await custo.estimate_tts_cost(1_000)
    assert valor == pytest.approx(1_000 * USD_POR_CHAR_POR_MODELO["eleven_flash_v2_5"])


def test_callback_url_do_payload_e_usada_como_esta():
    """
    Regressão de produção (27/08/2026): os quatro callbacks do ciclo voltaram
    404 e o projeto ficou em `pending_callback` para sempre, com os créditos
    do HeyGen já gastos.

    O `__main__` montava `{base}?token=xxx` e o job concatenava
    `/heygen-video-callback` no fim, produzindo
    `.../?token=xxx/heygen-video-callback` — path "/" e o endpoint DENTRO do
    valor do token. O HeyGen fez o POST exatamente nessa URL, como faz sempre,
    e recebeu 404.

    O contrato agora é: quem monta a URL é o `__main__`, path antes da query,
    e o job não toca nela. Este teste falha se alguém voltar a concatenar.
    """
    import inspect

    from avatar_job import job as job_mod

    src = inspect.getsource(job_mod.AvatarJob._generate_avatar_video)
    assert '"callback_url":   self.callback_url,' in src or \
           '"callback_url": self.callback_url,' in src, \
        "o payload deve usar self.callback_url sem concatenar path"
    assert "/heygen-video-callback" not in src, (
        "o path não pode ser concatenado aqui — ele entra depois da query "
        "string do token e o webhook volta 404"
    )
