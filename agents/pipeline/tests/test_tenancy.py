"""
tests/test_tenancy.py
======================
Cobertura de shared.tenancy.resolve_tenant — a verificação que faltava para
o tenant_id que já circula pela pipeline (header, ContextVar, coleções
`tenants/{id}/...`) significar alguma coisa.

Antes deste módulo, qualquer chamador autenticado pelo segredo único do CSM
podia se declarar dono de qualquer tenant só passando o header — sem checar
nada. Não explorável enquanto só existe um tenant, mas deixa de ser inofensivo
no dia em que um segundo existir.
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("TENANT_KEY_PEPPER", "pepper-de-teste-nao-usar-em-producao")

from shared.tenancy import (  # noqa: E402
    DEFAULT_TENANT_ID,
    TenantAuthError,
    generate_tenant_key,
    hash_tenant_key,
    resolve_tenant,
)


def _mock_doc(exists: bool, data: dict | None = None) -> MagicMock:
    doc = MagicMock()
    doc.exists = exists
    doc.to_dict.return_value = data or {}
    return doc


def _mock_db(doc: MagicMock) -> AsyncMock:
    db = MagicMock()
    db.collection.return_value.document.return_value.get = AsyncMock(return_value=doc)
    return db


# ── Tenant default: comportamento de hoje, preservado ─────────────────────────

@pytest.mark.asyncio
async def test_sem_tenant_id_resolve_para_default_sem_exigir_chave():
    db = _mock_db(_mock_doc(exists=False))
    ctx = await resolve_tenant(db, tenant_id=None, tenant_key=None)

    assert ctx.tenant_id == DEFAULT_TENANT_ID
    assert ctx.is_default is True
    # Nunca consulta o Firestore para o tenant default — não existe doc para ele.
    db.collection.assert_not_called()


@pytest.mark.asyncio
async def test_tenant_id_explicito_default_tambem_nao_exige_chave():
    db = _mock_db(_mock_doc(exists=False))
    ctx = await resolve_tenant(db, tenant_id="default", tenant_key=None)
    assert ctx.tenant_id == DEFAULT_TENANT_ID


# ── Tenant não-default: precisa existir, estar ativo, e a chave bater ─────────

@pytest.mark.asyncio
async def test_tenant_desconhecido_e_rejeitado():
    db = _mock_db(_mock_doc(exists=False))
    with pytest.raises(TenantAuthError, match="não existe"):
        await resolve_tenant(db, tenant_id="acme", tenant_key="qualquer")


@pytest.mark.asyncio
async def test_tenant_sem_chave_presente_e_rejeitado():
    stored_hash = hash_tenant_key("acme", "chave-correta")
    db = _mock_db(_mock_doc(exists=True, data={
        "name": "Acme", "status": "active", "key_hash": stored_hash,
    }))
    with pytest.raises(TenantAuthError, match="exige X-Tenant-Key"):
        await resolve_tenant(db, tenant_id="acme", tenant_key=None)


@pytest.mark.asyncio
async def test_tenant_com_chave_errada_e_rejeitado():
    stored_hash = hash_tenant_key("acme", "chave-correta")
    db = _mock_db(_mock_doc(exists=True, data={
        "name": "Acme", "status": "active", "key_hash": stored_hash,
    }))
    with pytest.raises(TenantAuthError, match="Chave inválida"):
        await resolve_tenant(db, tenant_id="acme", tenant_key="chave-errada")


@pytest.mark.asyncio
async def test_tenant_suspenso_e_rejeitado_mesmo_com_chave_certa():
    stored_hash = hash_tenant_key("acme", "chave-correta")
    db = _mock_db(_mock_doc(exists=True, data={
        "name": "Acme", "status": "suspended", "key_hash": stored_hash,
    }))
    with pytest.raises(TenantAuthError, match="não está ativo"):
        await resolve_tenant(db, tenant_id="acme", tenant_key="chave-correta")


@pytest.mark.asyncio
async def test_tenant_ativo_com_chave_certa_e_aceito():
    stored_hash = hash_tenant_key("acme", "chave-correta")
    db = _mock_db(_mock_doc(exists=True, data={
        "name": "Acme", "status": "active", "key_hash": stored_hash,
    }))
    ctx = await resolve_tenant(db, tenant_id="acme", tenant_key="chave-correta")

    assert ctx.tenant_id == "acme"
    assert ctx.name == "Acme"
    assert ctx.is_default is False


# ── Propriedades do hash ──────────────────────────────────────────────────────

def test_mesma_chave_gera_hash_diferente_por_tenant():
    # Vazar o hash de um tenant não ajuda a forjar a chave de outro: o salt é
    # o tenant_id, não um valor fixo global.
    h1 = hash_tenant_key("acme", "mesma-chave")
    h2 = hash_tenant_key("globex", "mesma-chave")
    assert h1 != h2


def test_hash_e_deterministico_para_o_mesmo_par():
    assert hash_tenant_key("acme", "x") == hash_tenant_key("acme", "x")


def test_generate_tenant_key_produz_valores_unicos_e_longos():
    keys = {generate_tenant_key() for _ in range(20)}
    assert len(keys) == 20
    assert all(len(k) >= 32 for k in keys)


def test_pepper_ausente_falha_alto_em_vez_de_aceitar_qualquer_chave(monkeypatch):
    monkeypatch.delenv("TENANT_KEY_PEPPER", raising=False)
    with pytest.raises(RuntimeError, match="TENANT_KEY_PEPPER"):
        hash_tenant_key("acme", "x")
