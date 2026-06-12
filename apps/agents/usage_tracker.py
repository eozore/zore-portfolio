"""
Token usage tracking for the Agentic Marketing Platform.

Records agent execution consumption (tokens in/out) and publication events
to the Firestore usage document at tenants/{tenantId}/usage/{yyyymm}.

Uses Firestore FieldValue.increment() for atomic counter updates —
no read-before-write required.

Key design principle: If tracking fails, the agent execution MUST NOT be
blocked. Failures are logged for later reconciliation.

Requirements: 5.5, 5.7
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from google.cloud.firestore_v1 import AsyncClient as AsyncFirestoreClient
from google.cloud.firestore_v1.transforms import Increment

logger = logging.getLogger(__name__)


def _get_current_period() -> str:
    """Return the current UTC period key in YYYYMM format."""
    return datetime.now(timezone.utc).strftime("%Y%m")


def _get_firestore_client() -> AsyncFirestoreClient:
    """Return an async Firestore client instance.

    In production, this is called per-request to avoid stale connections.
    """
    return AsyncFirestoreClient()


async def record_token_usage(
    tenant_id: str,
    agent_name: str,
    model_id: str,
    input_tokens: int,
    output_tokens: int,
    *,
    firestore_client: AsyncFirestoreClient | None = None,
) -> None:
    """
    Record token consumption after an agent execution completes.

    Atomically increments counters in tenants/{tenantId}/usage/{yyyymm}:
    - totalInputTokens
    - totalOutputTokens
    - byModel.{model_id}.inputTokens
    - byModel.{model_id}.outputTokens

    Args:
        tenant_id: The tenant that owns this execution.
        agent_name: Name of the agent that ran (e.g., "director", "writer").
        model_id: The model ID used for the execution.
        input_tokens: Number of input tokens consumed.
        output_tokens: Number of output tokens consumed.
        firestore_client: Optional injected client (for testing).

    Note:
        If this write fails, the failure is logged but NOT raised.
        The calling agent execution must continue uninterrupted (Req 5.7).
    """
    try:
        db = firestore_client or _get_firestore_client()
        period = _get_current_period()
        usage_ref = db.collection("tenants").document(tenant_id).collection("usage").document(period)

        update_data = {
            "totalInputTokens": Increment(input_tokens),
            "totalOutputTokens": Increment(output_tokens),
            f"byModel.{model_id}.inputTokens": Increment(input_tokens),
            f"byModel.{model_id}.outputTokens": Increment(output_tokens),
            "lastUpdated": datetime.now(timezone.utc).isoformat(),
        }

        # merge=True creates the document if it doesn't exist
        await usage_ref.set(update_data, merge=True)

        logger.info(
            "Token usage recorded",
            extra={
                "tenant_id": tenant_id,
                "agent": agent_name,
                "model": model_id,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "period": period,
            },
        )
    except Exception:
        logger.exception(
            "Failed to record token usage — execution continues",
            extra={
                "tenant_id": tenant_id,
                "agent": agent_name,
                "model": model_id,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
        )


async def record_publication(
    tenant_id: str,
    platform: str,
    *,
    firestore_client: AsyncFirestoreClient | None = None,
) -> None:
    """
    Record a successful publication event.

    Atomically increments counters in tenants/{tenantId}/usage/{yyyymm}:
    - postsPublished
    - byPlatform.{platform}

    Args:
        tenant_id: The tenant that published.
        platform: The platform published to (e.g., "linkedin_post", "blog").
        firestore_client: Optional injected client (for testing).

    Note:
        If this write fails, the failure is logged but NOT raised.
        The publication itself already succeeded at this point.
    """
    try:
        db = firestore_client or _get_firestore_client()
        period = _get_current_period()
        usage_ref = db.collection("tenants").document(tenant_id).collection("usage").document(period)

        update_data = {
            "postsPublished": Increment(1),
            f"byPlatform.{platform}": Increment(1),
            "lastUpdated": datetime.now(timezone.utc).isoformat(),
        }

        await usage_ref.set(update_data, merge=True)

        logger.info(
            "Publication recorded",
            extra={
                "tenant_id": tenant_id,
                "platform": platform,
                "period": period,
            },
        )
    except Exception:
        logger.exception(
            "Failed to record publication — continuing",
            extra={
                "tenant_id": tenant_id,
                "platform": platform,
            },
        )
