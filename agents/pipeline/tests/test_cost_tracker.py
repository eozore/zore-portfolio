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

from shared.cost_tracker import CostTrackerService, _current_month


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


# ── Orçamento mensal por tenant ───────────────────────────────────────────────
#
# Diferente do gate acima (por projeto), este olha o mês inteiro do tenant.
# Extraído porque o gate por projeto sozinho não impede N produções pequenas,
# nenhuma violando o teto individual, de somarem mais do que o tenant
# autorizou gastar no período.

def _make_tenant_firestore_mock(
    monthly_budget_brl: float | None,
    spent_brl: float = 0.0,
) -> AsyncMock:
    mock = AsyncMock()
    mock.get_pipeline_config = AsyncMock(
        return_value={
            "exchange_rate_usd_brl": 5.50,
            "monthly_budget_brl": monthly_budget_brl,
        }
    )
    mock.get_tenant_monthly_spend = AsyncMock(return_value=spent_brl)
    mock.add_tenant_spend = AsyncMock()
    return mock


@pytest.mark.asyncio
async def test_check_tenant_budget_sem_teto_configurado_sempre_libera() -> None:
    # Nenhum tenant é bloqueado por um limite que ninguém definiu — é o
    # comportamento de hoje, preservado quando monthly_budget_brl é None.
    mock_firestore = _make_tenant_firestore_mock(monthly_budget_brl=None, spent_brl=99999.0)
    service = CostTrackerService(firestore=mock_firestore, tenant_id="acme")

    assert await service.check_tenant_budget() is True


@pytest.mark.asyncio
async def test_check_tenant_budget_bloqueia_quando_mes_estourou() -> None:
    mock_firestore = _make_tenant_firestore_mock(monthly_budget_brl=100.0, spent_brl=100.0)
    service = CostTrackerService(firestore=mock_firestore, tenant_id="acme")

    assert await service.check_tenant_budget() is False
    mock_firestore.get_tenant_monthly_spend.assert_awaited_once_with("acme", _current_month())


@pytest.mark.asyncio
async def test_check_tenant_budget_libera_dentro_do_teto() -> None:
    mock_firestore = _make_tenant_firestore_mock(monthly_budget_brl=100.0, spent_brl=40.0)
    service = CostTrackerService(firestore=mock_firestore, tenant_id="acme")

    assert await service.check_tenant_budget() is True


@pytest.mark.asyncio
async def test_update_actual_cost_soma_no_mes_do_tenant() -> None:
    # update_actual_cost é o único ponto de gasto REAL (não estimado) hoje —
    # tem que alimentar o contador mensal do tenant automaticamente, sem que
    # cada chamador precise lembrar de somar por conta própria.
    mock_firestore = _make_firestore_mock(total_real=0.0)
    mock_firestore.get_tenant_monthly_spend = AsyncMock(return_value=0.0)
    mock_firestore.add_tenant_spend = AsyncMock()
    service = CostTrackerService(firestore=mock_firestore, tenant_id="acme")

    await service.update_actual_cost("proj-abc", "tts", cost_usd=1.0)

    mock_firestore.add_tenant_spend.assert_awaited_once()
    tenant_arg, month_arg, amount_arg = mock_firestore.add_tenant_spend.call_args[0]
    assert tenant_arg == "acme"
    assert amount_arg == pytest.approx(5.50, abs=0.01)  # 1 USD * 5.50 BRL/USD


@pytest.mark.asyncio
async def test_record_tenant_spend_estimate_usd_converte_para_brl() -> None:
    mock_firestore = _make_tenant_firestore_mock(monthly_budget_brl=None)
    service = CostTrackerService(firestore=mock_firestore, tenant_id="acme")

    await service.record_tenant_spend_estimate_usd(cost_usd=2.0)

    mock_firestore.add_tenant_spend.assert_awaited_once()
    _, _, amount_arg = mock_firestore.add_tenant_spend.call_args[0]
    assert amount_arg == pytest.approx(11.0, abs=0.01)  # 2 USD * 5.50


@pytest.mark.asyncio
async def test_record_tenant_spend_ignora_valores_zero_ou_negativos() -> None:
    mock_firestore = _make_tenant_firestore_mock(monthly_budget_brl=None)
    service = CostTrackerService(firestore=mock_firestore, tenant_id="acme")

    await service.record_tenant_spend(0.0)
    await service.record_tenant_spend(-5.0)

    mock_firestore.add_tenant_spend.assert_not_called()
