"""
Publicador sub-agent — executes the publication gate and publishes via MCP.

The Publicador checks all preconditions before publishing (autoPublish toggle,
human approval, active connection, rate limits, tenant quotas) and then publishes
content through the MCP layer (Postiz) using per-tenant credentials read from
Secret Manager on each call.

Requirements: 10.1, 10.5, 19.1, 19.2, 19.4, 19.5, 22.1, 22.3
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

try:
    from google.adk.agents import LlmAgent
except ImportError:  # pragma: no cover
    LlmAgent = None  # type: ignore[assignment, misc]

from apps.agents.models import get_model_for_role
from apps.agents.team.prompts import PUBLICADOR_PROMPT

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

PublishFormat = Literal[
    "blog",
    "linkedin_post",
    "youtube_video",
    "instagram_feed",
    "instagram_reel",
    "instagram_story",
]

# Map format → platform name for connection lookup
FORMAT_TO_PLATFORM: dict[str, str] = {
    "blog": "blog",
    "linkedin_post": "linkedin",
    "youtube_video": "youtube",
    "instagram_feed": "instagram",
    "instagram_reel": "instagram",
    "instagram_story": "instagram",
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class PublishGateResult:
    """
    Result of the publication gate check.

    Attributes:
        can_publish: Whether all preconditions are met for publishing.
        reason: Human-readable reason if publishing is blocked.
        retry_after: Seconds until next retry attempt (rate limit / quota).
    """

    can_publish: bool
    reason: str | None = None
    retry_after: int | None = None


# ---------------------------------------------------------------------------
# Publication gate
# ---------------------------------------------------------------------------


async def check_publish_gate(
    tenant_id: str,
    format: str,
    platform: str,
) -> PublishGateResult:
    """
    Validate all preconditions before publishing content.

    The gate checks (in order):
    1. autoPublish toggle for the format
    2. Human approval (if toggle is off, approval must exist and be 'approved')
    3. Active connection and valid token for the target platform
    4. Rate limits of the target platform
    5. Tenant plan quotas (Phase 2 — currently pass-through)

    Args:
        tenant_id: The tenant attempting to publish.
        format: The publish format (e.g., 'linkedin_post', 'instagram_feed').
        platform: The target platform (e.g., 'linkedin', 'instagram').

    Returns:
        PublishGateResult indicating whether publishing can proceed.
    """
    try:
        from google.cloud import firestore  # type: ignore[import]
    except ImportError:  # pragma: no cover
        firestore = None

    # --- 1. Check autoPublish toggle ---
    auto_publish = await _check_auto_publish_toggle(tenant_id, format)

    # --- 2. Check human approval (if toggle is off) ---
    if not auto_publish:
        has_approval = await _check_human_approval(tenant_id, format)
        if not has_approval:
            return PublishGateResult(
                can_publish=False,
                reason=(
                    f"Auto-publish is off for '{format}' and no human "
                    f"approval found. Content requires manual approval."
                ),
            )

    # --- 3. Check active connection and valid token ---
    connection_valid = await _check_connection(tenant_id, platform)
    if not connection_valid:
        return PublishGateResult(
            can_publish=False,
            reason=(
                f"No active connection for platform '{platform}'. "
                f"Token is missing, expired, or revoked."
            ),
        )

    # --- 4. Check rate limits ---
    rate_limit_result = await _check_rate_limits(tenant_id, platform)
    if not rate_limit_result.can_publish:
        return rate_limit_result

    # --- 5. Check tenant plan quotas (Phase 2) ---
    quota_result = await _check_quotas(tenant_id, format)
    if not quota_result.can_publish:
        return quota_result

    return PublishGateResult(can_publish=True)


# ---------------------------------------------------------------------------
# Gate check helpers (each can be extended with Firestore/Secret Manager calls)
# ---------------------------------------------------------------------------


async def _check_auto_publish_toggle(tenant_id: str, format: str) -> bool:
    """
    Check if autoPublish is enabled for the given format.

    Reads from tenants/{tenant_id}/settings.publishing.<format>.autoPublish.
    Returns True if auto-publish is on, False otherwise.
    """
    try:
        from google.cloud import firestore as fs  # type: ignore[import]

        db = fs.AsyncClient()
        settings_ref = db.collection("tenants").document(tenant_id)
        doc = await settings_ref.get()

        if doc.exists:
            data = doc.to_dict() or {}
            settings = data.get("settings", {})
            publishing = settings.get("publishing", {})
            format_config = publishing.get(format, {})
            return bool(format_config.get("autoPublish", False))
    except Exception:  # noqa: BLE001
        pass

    # Default: auto-publish is off (safe default)
    return False


async def _check_human_approval(tenant_id: str, format: str) -> bool:
    """
    Check if there's an approved human approval record for this format.

    Looks for an approval document with status='approved' and matching format.
    """
    try:
        from google.cloud import firestore as fs  # type: ignore[import]

        db = fs.AsyncClient()
        approvals = (
            db.collection("tenants")
            .document(tenant_id)
            .collection("approvals")
            .where("format", "==", format)
            .where("status", "==", "approved")
            .limit(1)
        )
        docs = approvals.stream()
        async for _ in docs:
            return True
    except Exception:  # noqa: BLE001
        pass

    return False


async def _check_connection(tenant_id: str, platform: str) -> bool:
    """
    Check if the tenant has an active, valid connection to the platform.

    Reads tenants/{tenant_id}/connections/{platform} and verifies:
    - status == 'connected'
    - secretRef is present (token exists in Secret Manager)
    """
    try:
        from google.cloud import firestore as fs  # type: ignore[import]

        db = fs.AsyncClient()
        conn_ref = (
            db.collection("tenants")
            .document(tenant_id)
            .collection("connections")
            .document(platform)
        )
        doc = await conn_ref.get()

        if doc.exists:
            data = doc.to_dict() or {}
            status = data.get("status")
            secret_ref = data.get("secretRef")
            return status == "connected" and bool(secret_ref)
    except Exception:  # noqa: BLE001
        pass

    return False


async def _check_rate_limits(tenant_id: str, platform: str) -> PublishGateResult:
    """
    Check if the target platform's rate limits have been reached.

    For Phase 1, this is a basic check. Phase 2 will integrate with
    platform-specific rate limit tracking.
    """
    # Phase 1: pass-through (no rate limit tracking yet)
    # Phase 2: check usage counters against platform limits
    return PublishGateResult(can_publish=True)


async def _check_quotas(tenant_id: str, format: str) -> PublishGateResult:
    """
    Check if the tenant's plan quotas allow publishing.

    Phase 2: Will check subscription entitlements against current usage.
    Currently passes through for all tenants.
    """
    # Phase 2: enforce plan quotas
    return PublishGateResult(can_publish=True)


# ---------------------------------------------------------------------------
# Publishing execution
# ---------------------------------------------------------------------------


async def execute_publish(
    tenant_id: str,
    format: str,
    content_payload: dict,
) -> dict:
    """
    Execute publication via MCP (Postiz) after gate passes.

    Args:
        tenant_id: The tenant publishing content.
        format: The publish format.
        content_payload: Platform-specific content to publish.

    Returns:
        Dict with 'success', 'url' (if published), or 'error' details.
    """
    platform = FORMAT_TO_PLATFORM.get(format, format)

    # Run the publication gate
    gate_result = await check_publish_gate(tenant_id, format, platform)

    if not gate_result.can_publish:
        # Determine the appropriate failure status
        if gate_result.retry_after:
            return {
                "success": False,
                "status": "queued",
                "reason": gate_result.reason,
                "retry_after": gate_result.retry_after,
            }
        elif "connection" in (gate_result.reason or "").lower():
            return {
                "success": False,
                "status": "failed",
                "reason": gate_result.reason,
            }
        else:
            return {
                "success": False,
                "status": "pending_approval",
                "reason": gate_result.reason,
            }

    # Gate passed — publish via MCP
    try:
        result = await _publish_via_mcp(tenant_id, platform, format, content_payload)
        return result
    except Exception as exc:  # noqa: BLE001
        return {
            "success": False,
            "status": "failed",
            "reason": f"MCP publish error: {exc}",
        }


async def _publish_via_mcp(
    tenant_id: str,
    platform: str,
    format: str,
    content_payload: dict,
) -> dict:
    """
    Publish content through the MCP layer (Postiz) with per-tenant credentials.

    Reads the tenant's token from Secret Manager for each call (no caching).
    """
    # Read credential from Secret Manager
    token = await _read_tenant_secret(tenant_id, platform)
    if not token:
        return {
            "success": False,
            "status": "failed",
            "reason": (
                f"No credential found for tenant '{tenant_id}' "
                f"on platform '{platform}'"
            ),
        }

    # Call MCP endpoint with per-tenant credential
    postiz_base_url = os.environ.get("POSTIZ_BASE_URL", "http://localhost:4200")

    try:
        import httpx
    except ImportError:  # pragma: no cover
        return {
            "success": False,
            "status": "failed",
            "reason": "httpx not installed",
        }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{postiz_base_url}/api/publish",
                json={
                    "platform": platform,
                    "format": format,
                    "content": content_payload,
                    "tenant_id": tenant_id,
                },
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Tenant-ID": tenant_id,
                },
            )

        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "status": "published",
                "url": data.get("url"),
                "platform_post_id": data.get("post_id"),
            }
        else:
            return {
                "success": False,
                "status": "failed",
                "reason": (
                    f"MCP returned status {response.status_code}: "
                    f"{response.text[:200]}"
                ),
            }
    except httpx.TimeoutException:
        return {
            "success": False,
            "status": "failed",
            "reason": f"MCP publish timeout for platform '{platform}'",
        }


async def _read_tenant_secret(tenant_id: str, platform: str) -> str | None:
    """
    Read the tenant's OAuth token from Secret Manager.

    Path: social-tokens/{tenant_id}/{platform}

    Returns the token string or None if not found / unavailable.
    """
    try:
        from google.cloud import secretmanager  # type: ignore[import]

        project_id = os.environ.get("GCP_PROJECT_ID", "")
        if not project_id:
            return None

        client = secretmanager.SecretManagerServiceClient()
        secret_name = (
            f"projects/{project_id}/secrets/"
            f"social-tokens-{tenant_id}-{platform}/versions/latest"
        )
        response = client.access_secret_version(name=secret_name)
        return response.payload.data.decode("utf-8")
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------

if LlmAgent is not None:
    publicador_agent = LlmAgent(
        name="publicador",
        model=get_model_for_role("publisher"),
        instruction=PUBLICADOR_PROMPT,
        sub_agents=[],
    )
else:
    publicador_agent = None  # type: ignore[assignment]
