"""
tests/test_retry.py
====================
Testes Nyquist para shared.retry.with_retry

NT-1: Sucesso na terceira tentativa após erros 429
NT-2: Falha rápida em erro permanente 401
NT-3: Atualiza Firestore com retry_count antes de dormir
"""

import pytest
from unittest.mock import AsyncMock

import sys
import os

# Garante que agents/pipeline/ esteja no PYTHONPATH ao rodar pytest diretamente
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.retry import with_retry, ApiError


@pytest.mark.asyncio
async def test_with_retry_succeeds_on_third_attempt() -> None:
    """
    Dado: função que lança ApiError(429) duas vezes e sucede na terceira
    Quando: with_retry é chamado com max_retries=3, backoff=[0,0,0]
    Então: executa 3 vezes e retorna o resultado da terceira chamada
    """
    call_count = 0

    async def flaky_fn() -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ApiError(429, "rate limited")
        return "success"

    # backoff=[0,0,0] para não atrasar os testes
    result = await with_retry(flaky_fn, max_retries=3, backoff=[0.0, 0.0, 0.0])

    assert result == "success"
    assert call_count == 3


@pytest.mark.asyncio
async def test_with_retry_raises_immediately_on_permanent_error() -> None:
    """
    Dado: função que lança ApiError(401)
    Quando: with_retry é chamado
    Então: re-lança imediatamente sem retry — call_count == 1
    """
    call_count = 0

    async def auth_fail() -> str:
        nonlocal call_count
        call_count += 1
        raise ApiError(401, "unauthorized")

    with pytest.raises(ApiError) as exc_info:
        await with_retry(auth_fail, max_retries=3, backoff=[0.0, 0.0, 0.0])

    assert exc_info.value.status_code == 401
    assert call_count == 1  # chamado apenas uma vez — sem retry


@pytest.mark.asyncio
async def test_with_retry_updates_firestore_before_sleep() -> None:
    """
    Dado: função que lança ApiError(429) e projeto/stage fornecidos
    Quando: with_retry detecta erro transitório na primeira tentativa
    Então: chama firestore.update_stage com retry_count=1 ANTES de dormir,
           depois a segunda tentativa retorna "ok"
    """
    mock_firestore = AsyncMock()
    mock_firestore.update_stage = AsyncMock()
    call_count = 0

    async def flaky() -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise ApiError(429, "rate limited")
        return "ok"

    result = await with_retry(
        flaky,
        max_retries=3,
        backoff=[0.0, 0.0, 0.0],
        project_id="proj-123",
        stage_id="tts",
        firestore=mock_firestore,
    )

    assert result == "ok"
    mock_firestore.update_stage.assert_called_once_with(
        "proj-123", "tts", {"retry_count": 1, "status": "retrying"}
    )
