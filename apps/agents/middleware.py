"""
FastAPI middleware for Firebase Authentication and tenant resolution.

Validates the Firebase ID token from the Authorization header, resolves the
tenant_id for the authenticated user, and attaches it to `request.state`.

Rejects with:
- HTTP 401: missing/invalid/expired token
- HTTP 403: tenant not found for authenticated user

Also enforces that path-level tenant_id (if present) matches the token's
resolved tenant_id, rejecting divergent requests in < 500ms.

Requirements: 2.4, 2.5, 2.6, 3.6
"""

from __future__ import annotations

import time
from typing import Callable

import firebase_admin
from firebase_admin import auth as firebase_auth, credentials
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from apps.agents.auth import TenantNotFoundError, get_tenant_id_for_user
from apps.agents.config import settings

# ---------------------------------------------------------------------------
# Firebase Admin SDK initialization (singleton)
# ---------------------------------------------------------------------------

_firebase_app: firebase_admin.App | None = None


def _ensure_firebase_initialized() -> None:
    """Initialize Firebase Admin SDK if not already done."""
    global _firebase_app
    if _firebase_app is not None:
        return

    cred = None
    if settings.firebase_service_account_path:
        cred = credentials.Certificate(settings.firebase_service_account_path)
    # If no explicit path, firebase_admin uses GOOGLE_APPLICATION_CREDENTIALS
    # or Application Default Credentials on GCP.

    _firebase_app = firebase_admin.initialize_app(
        cred,
        options={"projectId": settings.gcp_project_id} if settings.gcp_project_id else None,
    )


# ---------------------------------------------------------------------------
# Paths that bypass authentication (public endpoints, health checks)
# ---------------------------------------------------------------------------

PUBLIC_PATHS: set[str] = {
    "/health",
    "/healthz",
    "/readyz",
    "/docs",
    "/openapi.json",
    "/redoc",
}


def _is_public_path(path: str) -> bool:
    """Return True if the request path does not require authentication."""
    return path in PUBLIC_PATHS


# ---------------------------------------------------------------------------
# Token verification
# ---------------------------------------------------------------------------


def verify_firebase_token(token: str) -> dict:
    """
    Verify a Firebase ID token and return the decoded claims.

    Parameters
    ----------
    token : str
        The raw Firebase ID token (JWT).

    Returns
    -------
    dict
        Decoded token claims including `uid`, and optionally `tenantId`.

    Raises
    ------
    firebase_auth.InvalidIdTokenError
        If the token is malformed.
    firebase_auth.ExpiredIdTokenError
        If the token has expired.
    firebase_auth.RevokedIdTokenError
        If the token has been revoked.
    """
    _ensure_firebase_initialized()
    return firebase_auth.verify_id_token(token, check_revoked=True)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class FirebaseAuthMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware that:
    1. Extracts Bearer token from the Authorization header.
    2. Verifies it with Firebase Admin SDK.
    3. Resolves the tenant_id via `get_tenant_id_for_user(uid)`.
    4. Attaches `tenant_id` and `uid` to `request.state`.
    5. Validates that any path-level tenant_id matches the token tenant_id.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip auth for public endpoints
        if _is_public_path(request.url.path):
            return await call_next(request)

        # --- Step 1: Extract Bearer token ---
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid Authorization header"},
            )

        token = auth_header[len("Bearer "):]
        if not token:
            return JSONResponse(
                status_code=401,
                content={"detail": "Empty token"},
            )

        # --- Step 2: Verify token ---
        try:
            decoded_token = verify_firebase_token(token)
        except (
            firebase_auth.InvalidIdTokenError,
            firebase_auth.ExpiredIdTokenError,
            firebase_auth.RevokedIdTokenError,
            ValueError,
        ):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"},
            )

        uid: str = decoded_token["uid"]

        # --- Step 3: Resolve tenant_id ---
        try:
            tenant_id = await get_tenant_id_for_user(uid)
        except TenantNotFoundError:
            return JSONResponse(
                status_code=403,
                content={"detail": "Tenant not found for authenticated user"},
            )

        # --- Step 4: Attach to request state ---
        request.state.uid = uid
        request.state.tenant_id = tenant_id

        # --- Step 5: Validate path tenant_id matches token tenant_id ---
        path_tenant_id = _extract_path_tenant_id(request.url.path)
        if path_tenant_id is not None and path_tenant_id != tenant_id:
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Tenant ID in path does not match authenticated tenant"
                },
            )

        return await call_next(request)


def _extract_path_tenant_id(path: str) -> str | None:
    """
    Extract tenant_id from the URL path if it follows the pattern
    `/tenants/{tenantId}/...` or similar patterns.

    Returns None if no tenant_id is present in the path.
    """
    parts = path.strip("/").split("/")

    # Pattern: /tenants/{tenantId}/...
    if len(parts) >= 2 and parts[0] == "tenants":
        return parts[1]

    # Pattern: /api/v1/tenants/{tenantId}/...
    if len(parts) >= 4 and parts[2] == "tenants":
        return parts[3]

    return None
