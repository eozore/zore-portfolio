"""
Tenant creation service.

Provides `create_tenant_for_user()` which atomically creates all required
Firestore documents for a new tenant on first login:
  - tenants/{uid} — main tenant document
  - tenants/{uid}/settings — publish settings with all toggles off
  - tenants/{uid}/members/{uid} — owner membership record

Uses a Firestore batch write for atomicity: either all documents are created
or none are (on failure, a clear error is returned to the caller).

Requirements: 2.2, 2.7, 4.3, 20.1, 20.2
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

from google.cloud import firestore

from apps.agents.config import settings


class TenantCreationError(Exception):
    """Raised when tenant creation fails in Firestore."""

    def __init__(self, uid: str, reason: str) -> None:
        self.uid = uid
        self.reason = reason
        super().__init__(
            f"Failed to create tenant for uid={uid}: {reason}"
        )


@dataclass
class TenantCreationResult:
    """Result of a tenant creation attempt."""

    success: bool
    tenant_id: str | None
    error: str | None = None


def _get_firestore_client() -> firestore.Client:
    """Return a Firestore client."""
    return firestore.Client(
        project=settings.gcp_project_id or None,
        database=settings.firestore_database,
    )


def create_tenant_for_user(
    uid: str,
    name: str,
    email: str,
    auth_method: Literal["google", "email"],
) -> TenantCreationResult:
    """
    Create a new tenant for a user on their first login.

    This function is idempotent: if the tenant already exists, it returns
    success without modifying the existing data.

    The operation uses a Firestore batch write to atomically create:
    1. The tenant document at `tenants/{uid}`
    2. The settings document at `tenants/{uid}/settings/publishing`
    3. The member document at `tenants/{uid}/members/{uid}` with role=owner

    Parameters
    ----------
    uid : str
        The Firebase Authentication UID (used as tenant_id in Phase 1).
    name : str
        Display name of the user.
    email : str
        Email address of the user.
    auth_method : "google" | "email"
        The authentication method used for signup.

    Returns
    -------
    TenantCreationResult
        Result with success=True and tenant_id on success,
        or success=False and error message on failure.
    """
    db = _get_firestore_client()

    # Idempotency check: if tenant already exists, return early
    tenant_ref = db.collection("tenants").document(uid)
    existing = tenant_ref.get()
    if existing.exists:
        return TenantCreationResult(success=True, tenant_id=uid)

    try:
        # Use a batch write for atomicity
        batch = db.batch()

        # 1. Create the main tenant document
        tenant_data = {
            "tenantId": uid,
            "name": name,
            "email": email,
            "authMethod": auth_method,
            "createdAt": int(time.time() * 1000),  # epoch millis
            "profile": {
                "brandVoice": "",
                "niche": "",
                "persona": "",
                "languages": [],
                "links": [],
            },
            "subscription": {
                "plan": "free",
                "status": "active",
                "stripeCustomerId": "",
                "entitlements": {},
            },
        }
        batch.set(tenant_ref, tenant_data)

        # 2. Create settings with all autoPublish toggles set to false
        settings_ref = tenant_ref.collection("settings").document("publishing")
        settings_data = {
            "publishing": {
                "blog": {"autoPublish": False},
                "linkedin_post": {"autoPublish": False},
                "youtube_video": {"autoPublish": False},
                "instagram_feed": {"autoPublish": False},
                "instagram_reel": {"autoPublish": False},
                "instagram_story": {"autoPublish": False},
            }
        }
        batch.set(settings_ref, settings_data)

        # 3. Create member document with role=owner
        member_ref = tenant_ref.collection("members").document(uid)
        member_data = {
            "uid": uid,
            "role": "owner",
        }
        batch.set(member_ref, member_data)

        # Commit all documents atomically
        batch.commit()

        return TenantCreationResult(success=True, tenant_id=uid)

    except Exception as e:
        # Handle any Firestore errors gracefully
        error_message = f"Firestore batch write failed: {str(e)}"
        return TenantCreationResult(
            success=False,
            tenant_id=None,
            error=error_message,
        )
