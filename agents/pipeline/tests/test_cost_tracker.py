"""
tests/test_cost_tracker.py
===========================
Testes Nyquist para shared.cost_tracker.CostTrackerService

NT-1: check_cost_gate bloqueia quando custo atual + estimado > limite
NT-2: check_cost_gate permite quando custo está dentro do limite
"""

import pytest
from unittest.mock import AsyncMock

import sys
import os

# Garante que agents/pipeline/ esteja no PYTHONPATH ao rodar pytest diretamente
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.cost_tracker import CostTrackerService


def _make_firestore_mock(total_real: float) -> AsyncMock:
    """Helper: cria um mock de FirestoreClient com total_real configurado."""
    mock = AsyncMock()
    mock.get_project = AsyncMock(
        return_value={"cost_breakdown": {"total_real": total_real}}
    )
    mock.update_project = AsyncMock()
    mock.get_pipeline_config = AsyncMock(
        return_value={"exchange_rate_usd_brl": 5.50}
    )
    return mock


@pytest.mark.asyncio
async def test_check_cost_gate_blocks_when_limit_exceeded() -> None:
    """
    Dado: projeto com total_real=85.0 BRL e additional_cost=20.0 BRL
    Quando: check_cost_gate("proj-abc", 20.0, 100.0) é chamado
    Então: retorna False e escreve cost_blocked no Firestore com campos corretos
    """
    mock_firestore = _make_firestore_mock(total_real=85.0)
    service = CostTrackerService(firestore=mock_firestore)

    result = await service.check_cost_gate(
        project_id="proj-abc",
        additional_cost=20.0,
        limit=100.0,
    )

    assert result is False

    # Verifica que update_project foi chamado com cost_blocked correto
    mock_firestore.update_project.assert_called_once()
    call_args = mock_firestore.update_project.call_args
    cost_blocked = call_args[0][1]["cost_blocked"]

    assert cost_blocked["blocked"] is True
    assert cost_blocked["current_cost"] == 85.0
    assert cost_blocked["estimated_next"] == 20.0
    assert cost_blocked["limit"] == 100.0
    assert "blocked_at" in cost_blocked


@pytest.mark.asyncio
async def test_check_cost_gate_allows_when_within_limit() -> None:
    """
    Dado: projeto com total_real=85.0 BRL e additional_cost=14.0 BRL
    Quando: check_cost_gate("proj-abc", 14.0, 100.0) é chamado
    Então: retorna True e NÃO chama update_project (85 + 14 = 99 <= 100)
    """
    mock_firestore = _make_firestore_mock(total_real=85.0)
    service = CostTrackerService(firestore=mock_firestore)

    result = await service.check_cost_gate(
        project_id="proj-abc",
        additional_cost=14.0,
        limit=100.0,
    )

    assert result is True
    mock_firestore.update_project.assert_not_called()
