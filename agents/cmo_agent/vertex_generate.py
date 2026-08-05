# -*- coding: utf-8 -*-
"""
vertex_generate.py — Chamada direta ao Vertex AI Gemini sem o SDK antigravity.

Usado pelos agentes que geram conteúdo longo (writing, scriptwriter, copy, thumbnail, validator)
para evitar o bug de "looping content" do SDK google-antigravity, que aborta streams
de output longos interpretando-os incorretamente como loops.

Gemini 2.5 Flash no Vertex AI:
  - Input:  até 1,048,576 tokens
  - Output: até 65,536 tokens
  - Sem limitação de 16,384 tokens imposta pelo SDK antigravity

Autenticação: Application Default Credentials (ADC) — funciona no Cloud Run automaticamente.
"""

import asyncio
import json
import logging
import os
from typing import AsyncIterator, Optional

import google.auth
import google.auth.transport.requests
import requests as req_lib

logger = logging.getLogger("cmo_agent.vertex_generate")

VERTEX_REGION = "us-central1"
# gemini-3.5-flash-lite disponível via endpoint GLOBAL (não regional).
# Modelos 3.x do Vertex AI usam aiplatform.googleapis.com sem prefixo de região.
VERTEX_MODEL = os.environ.get("VERTEX_MODEL", "gemini-3.5-flash-lite")
VERTEX_USE_GLOBAL = True  # endpoint global para modelos 3.x


def _get_access_token() -> str:
    """Obtém token ADC. Funciona em Cloud Run (service account) e local (gcloud ADC)."""
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    auth_request = google.auth.transport.requests.Request()
    credentials.refresh(auth_request)
    return credentials.token


def _vertex_endpoint(project_id: str, stream: bool = True) -> str:
    """
    Modelos 3.x (gemini-3.5-flash-lite, gemini-3.5-flash, etc.) só estão
    disponíveis via endpoint global. Modelos 2.x usam o endpoint regional.
    """
    if VERTEX_USE_GLOBAL:
        # Endpoint global — sem prefixo de região na URL base
        base = f"https://aiplatform.googleapis.com/v1/projects/{project_id}/locations/{VERTEX_REGION}/publishers/google/models/{VERTEX_MODEL}"
    else:
        base = f"https://{VERTEX_REGION}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{VERTEX_REGION}/publishers/google/models/{VERTEX_MODEL}"
    return f"{base}:streamGenerateContent?alt=sse" if stream else f"{base}:generateContent"


async def generate_text(
    prompt: str,
    system_instruction: str = "",
    temperature: float = 0.7,  # ignorado em modelos 3.x mas mantido por compatibilidade
    top_p: float = 0.9,
) -> str:
    """
    Gera texto via Vertex AI diretamente (não-streaming).
    Modelo: gemini-3.5-flash (GA) ou configurável via env VERTEX_MODEL.
    """
    project_id = os.environ.get("FIREBASE_PROJECT_ID")
    if not project_id:
        raise RuntimeError("FIREBASE_PROJECT_ID not set")

    loop = asyncio.get_event_loop()

    def _call() -> str:
        token = _get_access_token()
        payload: dict = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "topP": top_p,
                "maxOutputTokens": 65536,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        resp = req_lib.post(
            _vertex_endpoint(project_id, stream=False),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=300,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Vertex AI error {resp.status_code}: {resp.text[:400]}")

        data = resp.json()
        parts = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [])
        )
        return "".join(p.get("text", "") for p in parts)

    return await loop.run_in_executor(None, _call)


async def stream_text(
    prompt: str,
    system_instruction: str = "",
    temperature: float = 0.7,
) -> AsyncIterator[str]:
    """
    Gera texto via Vertex AI em modo streaming (SSE).
    Decodifica corretamente como UTF-8 para evitar encoding Latin-1.
    """
    project_id = os.environ.get("FIREBASE_PROJECT_ID")
    if not project_id:
        raise RuntimeError("FIREBASE_PROJECT_ID not set")

    import queue
    import threading

    token_queue: queue.Queue = queue.Queue()
    SENTINEL = object()

    def _stream_thread():
        try:
            token = _get_access_token()
            payload: dict = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": temperature,
                    "topP": 0.9,
                    "maxOutputTokens": 65536,
                },
            }
            if system_instruction:
                payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

            with req_lib.post(
                _vertex_endpoint(project_id, stream=True),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                stream=True,
                timeout=600,
            ) as resp:
                if resp.status_code != 200:
                    token_queue.put(RuntimeError(
                        f"Vertex AI error {resp.status_code}: {resp.text[:400]}"
                    ))
                    return

                # CRÍTICO: iter_lines com UTF-8 explícito para evitar Ã£/Ã© (Latin-1)
                buffer = b""
                for raw_chunk in resp.iter_content(chunk_size=None):
                    if not raw_chunk:
                        continue
                    buffer += raw_chunk
                    while b"\n" in buffer:
                        line_bytes, buffer = buffer.split(b"\n", 1)
                        line = line_bytes.decode("utf-8", errors="replace").strip()
                        if not line:
                            continue
                        if line.startswith("data: "):
                            line = line[6:]
                        if not line or line == "[DONE]":
                            continue
                        try:
                            chunk = json.loads(line)
                            parts = (
                                chunk.get("candidates", [{}])[0]
                                .get("content", {})
                                .get("parts", [])
                            )
                            text = "".join(p.get("text", "") for p in parts)
                            if text:
                                token_queue.put(text)
                        except json.JSONDecodeError:
                            pass

        except Exception as exc:
            token_queue.put(exc)
        finally:
            token_queue.put(SENTINEL)

    thread = threading.Thread(target=_stream_thread, daemon=True)
    thread.start()

    loop = asyncio.get_event_loop()
    while True:
        item = await loop.run_in_executor(None, token_queue.get)
        if item is SENTINEL:
            break
        if isinstance(item, Exception):
            raise item
        yield item
