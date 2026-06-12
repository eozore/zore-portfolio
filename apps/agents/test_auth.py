"""
Unit tests for apps/agents/auth.py — tenant resolution.

These tests mock Firestore to verify the resolution logic without
requiring a live database.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.agents.auth import TenantNotFoundError, get_tenant_id_for_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_firestore_client(
    tenant_exists: bool = False,
    member_docs: list | None = None,
):
    """
    Create a mock Firestore client that simulates:
    - tenant_exists: whether the direct tenant document lookup succeeds
    - member_docs: list of mock member documents from collection group query
    """
    client = MagicMock()

    # Mock document get
    tenant_doc = MagicMock()
    tenant_doc.exists = tenant_exists
    client.collection.return_value.document.return_value.get.return_value = tenant_doc

    # Mock collection group query
    if member_docs is None:
        member_docs = []
    query = MagicMock()
    query.where.return_value.limit.return_value.stream.return_value = iter(member_docs)
    client.collection_group.return_value = query

    return client


def _make_member_doc(tenant_id: str, uid: str):
    """Create a mock member document with proper parent references."""
    doc = MagicMock()
    # reference.parent = members collection, reference.parent.parent = tenant doc
    doc.reference.parent.parent.id = tenant_id
    return doc


# ---------------------------------------------------------------------------
# Tests: Phase 1 — tenant_id == uid
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_tenant_id_phase1_owner():
    """When a tenant document exists at tenants/{uid}, return uid as tenant_id."""
    mock_client = _mock_firestore_client(tenant_exists=True)

    with patch("apps.agents.auth._get_firestore_client", return_value=mock_client):
        result = await get_tenant_id_for_user("user-123")

    assert result == "user-123"


# ---------------------------------------------------------------------------
# Tests: Phase 2 — member lookup via collection group query
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_tenant_id_phase2_member():
    """When user is a member of a tenant (not the owner), resolve via members subcollection."""
    member_doc = _make_member_doc(tenant_id="tenant-abc", uid="user-456")
    mock_client = _mock_firestore_client(tenant_exists=False, member_docs=[member_doc])

    with patch("apps.agents.auth._get_firestore_client", return_value=mock_client):
        result = await get_tenant_id_for_user("user-456")

    assert result == "tenant-abc"


# ---------------------------------------------------------------------------
# Tests: Error — no tenant found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_tenant_id_not_found_raises():
    """When uid has no tenant (neither owner nor member), raise TenantNotFoundError."""
    mock_client = _mock_firestore_client(tenant_exists=False, member_docs=[])

    with patch("apps.agents.auth._get_firestore_client", return_value=mock_client):
        with pytest.raises(TenantNotFoundError) as exc_info:
            await get_tenant_id_for_user("orphan-uid")

    assert exc_info.value.uid == "orphan-uid"
    assert "orphan-uid" in str(exc_info.value)
