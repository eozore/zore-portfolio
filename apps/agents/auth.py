"""
Tenant resolution module.

Provides `get_tenant_id_for_user(uid)` which resolves a Firebase UID to its
corresponding tenant_id by querying Firestore. This indirection supports both
Phase 1 (tenant_id == uid) and Phase 2 (multi-member tenants via the
`members` subcollection).

Requirements: 2.3, 20.3, 20.4
"""

from __future__ import annotations

from google.cloud import firestore

from apps.agents.config import settings


class TenantNotFoundError(Exception):
    """Raised when no tenant is associated with the given UID."""

    def __init__(self, uid: str) -> None:
        self.uid = uid
        super().__init__(f"No tenant found for uid={uid}")


def _get_firestore_client() -> firestore.Client:
    """Return a Firestore client (lazy-initialized per call for statelessness)."""
    return firestore.Client(
        project=settings.gcp_project_id or None,
        database=settings.firestore_database,
    )


async def get_tenant_id_for_user(uid: str) -> str:
    """
    Resolve the tenant_id for a given Firebase UID.

    Resolution strategy (supports Phase 2 multi-member tenants):
    1. Check if a tenant document exists at `tenants/{uid}` (Phase 1: owner == tenant).
    2. If not found, perform a collection-group query on the `members` subcollection
       to find a tenant where the user is a member.
    3. If neither lookup succeeds, raise TenantNotFoundError.

    Parameters
    ----------
    uid : str
        The Firebase Authentication UID of the current user.

    Returns
    -------
    str
        The resolved tenant_id.

    Raises
    ------
    TenantNotFoundError
        If no tenant is associated with the given UID.
    """
    db = _get_firestore_client()

    # Phase 1 fast path: tenant_id == uid
    tenant_ref = db.collection("tenants").document(uid)
    tenant_doc = tenant_ref.get()

    if tenant_doc.exists:
        return uid

    # Phase 2 path: look up via members subcollection (collection group query)
    members_query = (
        db.collection_group("members")
        .where("uid", "==", uid)
        .limit(1)
    )
    member_docs = list(members_query.stream())

    if member_docs:
        # The parent path is: tenants/{tenantId}/members/{uid}
        # Navigate up to get the tenant document reference
        member_ref = member_docs[0].reference
        tenant_id = member_ref.parent.parent.id
        return tenant_id

    raise TenantNotFoundError(uid)
