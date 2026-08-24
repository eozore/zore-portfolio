# -*- coding: utf-8 -*-
"""
stub_server.py — HeyGen e ElevenLabs falsos para o ambiente local.

Devolvem arquivos REAIS que já estão no repositório: o resultado de uma
geração anterior do HeyGen e uma amostra do ElevenLabs. Melhor que áudio
sintético — o compositor exercita codec, duração e faixa de áudio de verdade.

O alinhamento do ElevenLabs é sintetizado a partir do texto pedido,
distribuído pela duração do MP3. Não é o tempo real da fala, mas tem a MESMA
FORMA da resposta verdadeira — que é o que o `words_from_alignment` consome.
"""

import base64
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Stub HeyGen + ElevenLabs")

SAMPLES = Path(os.environ.get("SAMPLES_DIR", "/app/samples"))
AUDIO   = SAMPLES / "voice_clone_flash_v2_5_test.mp3"
VIDEO   = SAMPLES / "spike_lipsync_result.mp4"

# Duração real da amostra de áudio, medida uma vez no boot.
def _dur(path: Path) -> float:
    import subprocess
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=30,
        ).stdout.strip()
        return float(out)
    except Exception:
        return 10.0


@app.get("/health")
def health():
    return {"ok": True, "audio": AUDIO.exists(), "video": VIDEO.exists()}


# ── ElevenLabs ────────────────────────────────────────────────────────────────

@app.post("/elevenlabs/v1/text-to-speech/{voice_id}/with-timestamps")
async def tts_with_timestamps(voice_id: str, request: Request):
    body  = await request.json()
    texto = body.get("text", "")
    dur   = _dur(AUDIO)

    # Alinhamento sintético: distribui os caracteres uniformemente na duração.
    # A forma é idêntica à da API real — characters + start/end por caractere.
    chars = list(texto)
    passo = dur / max(1, len(chars))
    starts = [round(i * passo, 4) for i in range(len(chars))]
    ends   = [round((i + 1) * passo, 4) for i in range(len(chars))]

    return JSONResponse({
        "audio_base64": base64.b64encode(AUDIO.read_bytes()).decode(),
        "alignment": {
            "characters": chars,
            "character_start_times_seconds": starts,
            "character_end_times_seconds": ends,
        },
    })


@app.post("/elevenlabs/v1/text-to-speech/{voice_id}")
async def tts(voice_id: str):
    from fastapi.responses import Response
    return Response(AUDIO.read_bytes(), media_type="audio/mpeg")


# ── HeyGen ────────────────────────────────────────────────────────────────────

@app.post("/heygen/v3/videos")
async def gerar_video(request: Request):
    body = await request.json()
    # Espelha o gate do v3 real: corpo plano, avatar_id e uma fonte de fala.
    # Aceitar qualquer coisa aqui deixaria passar localmente o mesmo payload
    # malformado que o v3 recusa com 422 em produção — que é exatamente o que
    # este ambiente existe para pegar.
    faltando = [c for c in ("type", "avatar_id") if not body.get(c)]
    if not body.get("audio_asset_id") and not body.get("audio_url") and not body.get("script"):
        faltando.append("audio_asset_id|audio_url|script")
    if "video_inputs" in body or "dimension" in body:
        faltando.append("corpo no formato v2 (video_inputs/dimension)")
    if faltando:
        return JSONResponse({"error": {"message": f"faltando: {', '.join(faltando)}"}}, status_code=422)

    # O callback_id carrega project/target/segmento; devolvê-lo no video_id
    # deixa o rastro legível no log local.
    return JSONResponse({"data": {
        "video_id": f"stub-{body.get('callback_id','x')[:40]}",
        "status": "waiting",
    }})


@app.get("/heygen/v1/video_status.get")
async def status_video(video_id: str = ""):
    return JSONResponse({
        "data": {"id": video_id, "status": "completed",
                 "video_url": "http://media-stub:8095/asset/avatar.mp4"},
    })


@app.get("/heygen/v3/users/me")
async def usuario():
    # Carteira pay-as-you-go, que é a forma de cobrança real desta conta.
    return JSONResponse({"data": {
        "username": "stub", "email": "stub@local",
        "billing_type": "wallet",
        "wallet": {"remaining_balance": 9999.0},
    }})


@app.get("/heygen/v3/avatars/looks/{look_id}")
async def look(look_id: str):
    # Declara os três motores para o _motor_elegivel não degradar localmente.
    return JSONResponse({"data": {
        "id": look_id,
        "supported_api_engines": ["avatar_iii", "avatar_iv", "avatar_v"],
    }})


@app.get("/asset/avatar.mp4")
def asset_video():
    from fastapi.responses import FileResponse
    return FileResponse(VIDEO, media_type="video/mp4")
