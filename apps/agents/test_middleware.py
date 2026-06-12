"""
Unit tests for apps/agents/middleware.py — Firebase auth middleware.

Tests cover:
- Missing/invalid Authorization header → 401
- Invalid/expired token → 401
- Tenant not found → 403
- Path tenant_id mismatch → 403
- Successful authentication attaches uid + tenant_id to request.state
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from apps.agents.auth import TenantNotFoundError
from apps.agents.middleware import FirebaseAuthMiddleware

# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------


def _create_test_app() -> FastAPI:
    """Create a minimal FastAPI app with the auth middleware for testing."""
    app = FastAPI()
    app.add_middleware(FirebaseAuthMiddleware)

    @app.get("/protected")
    async def protected_route(request: Request):
        return {
            "uid": request.state.uid,
            "tenant_id": request.state.tenant_id,
        }

    @app.get("/tenants/{tenant_id}/data")
    async def tenant_data(request: Request, tenant_id: str):
        return {
            "uid": request.state.uid,
            "tenant_id": request.state.tenant_id,
        }

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


# ---------------------------------------------------------------------------
# Tests: Public paths bypass auth
# ---------------------------------------------------------------------------


def test_public_path_bypasses_auth():
    """Health endpoint should not require authentication."""
    app = _create_test_app()
    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Tests: 401 — Missing/invalid token
# ---------------------------------------------------------------------------


def test_missing_authorization_header():
    """Request without Authorization header returns 401."""
    app = _create_test_app()
    client = TestClient(app)

    response = client.get("/protected")
    assert response.status_code == 401
    assert "Missing or invalid" in response.json()["detail"]


def test_non_bearer_authorization_header():
    """Request with non-Bearer auth scheme returns 401."""
    app = _create_test_app()
    client = TestClient(app)

    response = client.get("/protected", headers={"Authorization": "Basic abc123"})
    assert response.status_code == 401


def test_empty_bearer_token():
    """Request with empty Bearer token returns 401."""
    app = _create_test_app()
    client = TestClient(app)

    response = client.get("/protected", headers={"Authorization": "Bearer "})
    assert response.status_code == 401
    assert "Empty token" in response.json()["detail"]


@patch("apps.agents.middleware.verify_firebase_token")
def test_invalid_token_returns_401(mock_verify):
    """Invalid token (failed verification) returns 401."""
    from firebase_admin import auth as firebase_auth

    mock_verify.side_effect = firebase_auth.InvalidIdTokenError("bad token")

    app = _create_test_app()
    client = TestClient(app)

    response = client.get(
        "/protected", headers={"Authorization": "Bearer invalid-token"}
    )
    assert response.status_code == 401
    assert "Invalid or expired" in response.json()["detail"]


@patch("apps.agents.middleware.verify_firebase_token")
def test_expired_token_returns_401(mock_verify):
    """Expired token returns 401."""
    from firebase_admin import auth as firebase_auth

    mock_verify.side_effect = firebase_auth.ExpiredIdTokenError("expired", cause=None)

    app = _create_test_app()
    client = TestClient(app)

    response = client.get(
        "/protected", headers={"Authorization": "Bearer expired-token"}
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Tests: 403 — Tenant not found
# ---------------------------------------------------------------------------


@patch("apps.agents.middleware.get_tenant_id_for_user", new_callable=AsyncMock)
@patch("apps.agents.middleware.verify_firebase_token")
def test_tenant_not_found_returns_403(mock_verify, mock_get_tenant):
    """When tenant resolution fails, return 403."""
    mock_verify.return_value = {"uid": "user-no-tenant"}
    mock_get_tenant.side_effect = TenantNotFoundError("user-no-tenant")

    app = _create_test_app()
    client = TestClient(app)

    response = client.get(
        "/protected", headers={"Authorization": "Bearer valid-token"}
    )
    assert response.status_code == 403
    assert "Tenant not found" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Tests: 403 — Path tenant_id mismatch
# ---------------------------------------------------------------------------


@patch("apps.agents.middleware.get_tenant_id_for_user", new_callable=AsyncMock)
@patch("apps.agents.middleware.verify_firebase_token")
def test_path_tenant_mismatch_returns_403(mock_verify, mock_get_tenant):
    """When path tenant_id differs from token tenant_id, reject with 403."""
    mock_verify.return_value = {"uid": "user-123"}
    mock_get_tenant.return_value = "tenant-mine"

    app = _create_test_app()
    client = TestClient(app)

    # Access another tenant's data
    response = client.get(
        "/tenants/tenant-other/data",
        headers={"Authorization": "Bearer valid-token"},
    )
    assert response.status_code == 403
    assert "does not match" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Tests: Success — authenticated request
# ---------------------------------------------------------------------------


@patch("apps.agents.middleware.get_tenant_id_for_user", new_callable=AsyncMock)
@patch("apps.agents.middleware.verify_firebase_token")
def test_successful_auth_attaches_state(mock_verify, mock_get_tenant):
    """Valid token + resolved tenant → uid and tenant_id attached to request.state."""
    mock_verify.return_value = {"uid": "user-123"}
    mock_get_tenant.return_value = "tenant-xyz"

    app = _create_test_app()
    client = TestClient(app)

    response = client.get(
        "/protected", headers={"Authorization": "Bearer valid-token"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["uid"] == "user-123"
    assert data["tenant_id"] == "tenant-xyz"


@patch("apps.agents.middleware.get_tenant_id_for_user", new_callable=AsyncMock)
@patch("apps.agents.middleware.verify_firebase_token")
def test_matching_path_tenant_succeeds(mock_verify, mock_get_tenant):
    """When path tenant_id matches token tenant_id, request proceeds."""
    mock_verify.return_value = {"uid": "user-123"}
    mock_get_tenant.return_value = "tenant-mine"

    app = _create_test_app()
    client = TestClient(app)

    response = client.get(
        "/tenants/tenant-mine/data",
        headers={"Authorization": "Bearer valid-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == "tenant-mine"
