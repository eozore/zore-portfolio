"""
Event persistence and buffering for SSE reconnection support.

Provides:
- EventBuffer: in-memory buffer with 300s TTL per event, keyed by run_id
- persist_event_to_firestore(): async persistence to Firestore
- get_events_after_id(): retrieve buffered events after a given event_id

Requirements: 8.5, 8.6
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from google.cloud import firestore

from apps.agents.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EVENT_BUFFER_TTL_SECONDS = 300  # 5 minutes


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------


@dataclass
class BufferedEvent:
    """A single SSE event stored in the buffer."""

    event_id: str
    event_type: str
    data: dict
    raw_sse: str
    created_at: float = field(default_factory=time.time)

    @property
    def is_expired(self) -> bool:
        """Check if this event has exceeded its TTL."""
        return (time.time() - self.created_at) > EVENT_BUFFER_TTL_SECONDS


# ---------------------------------------------------------------------------
# EventBuffer
# ---------------------------------------------------------------------------


class EventBuffer:
    """
    In-memory buffer for SSE events, keyed by run_id.

    Events are stored with a TTL of 300 seconds. Expired events are cleaned
    up lazily on access (when get_events_after_id or add_event is called).

    This allows clients to reconnect after a brief disconnection and receive
    any events they missed using the Last-Event-ID header.
    """

    def __init__(self) -> None:
        # Dict[run_id -> list of BufferedEvent]
        self._buffers: dict[str, list[BufferedEvent]] = {}

    def add_event(
        self,
        run_id: str,
        event_id: str,
        event_type: str,
        data: dict,
        raw_sse: str,
    ) -> None:
        """
        Add an event to the buffer for a given run_id.

        Triggers cleanup of expired events for this run_id.
        """
        if run_id not in self._buffers:
            self._buffers[run_id] = []
        else:
            self._cleanup_expired(run_id)

        # Re-check after cleanup (cleanup may have removed the key)
        if run_id not in self._buffers:
            self._buffers[run_id] = []

        self._buffers[run_id].append(
            BufferedEvent(
                event_id=event_id,
                event_type=event_type,
                data=data,
                raw_sse=raw_sse,
            )
        )

    def get_events_after_id(
        self, run_id: str, last_event_id: str
    ) -> list[BufferedEvent]:
        """
        Return all buffered events for a run_id that come after the given event_id.

        If last_event_id is not found in the buffer, returns all available events.
        Triggers cleanup of expired events.
        """
        if run_id not in self._buffers:
            return []

        self._cleanup_expired(run_id)

        events = self._buffers[run_id]
        if not events:
            return []

        # Find the index of last_event_id
        found_index = -1
        for i, evt in enumerate(events):
            if evt.event_id == last_event_id:
                found_index = i
                break

        if found_index == -1:
            # Last-Event-ID not found — return all available events
            return list(events)

        # Return events after the found index
        return list(events[found_index + 1 :])

    def get_all_events(self, run_id: str) -> list[BufferedEvent]:
        """Return all non-expired buffered events for a run_id."""
        if run_id not in self._buffers:
            return []

        self._cleanup_expired(run_id)
        return list(self._buffers[run_id])

    def _cleanup_expired(self, run_id: str) -> None:
        """Remove expired events from the buffer for a given run_id."""
        if run_id not in self._buffers:
            return

        self._buffers[run_id] = [
            evt for evt in self._buffers[run_id] if not evt.is_expired
        ]

        # Remove the run_id key entirely if no events remain
        if not self._buffers[run_id]:
            del self._buffers[run_id]

    def cleanup_all_expired(self) -> None:
        """Remove expired events across all run_ids."""
        run_ids = list(self._buffers.keys())
        for run_id in run_ids:
            self._cleanup_expired(run_id)


# ---------------------------------------------------------------------------
# Singleton event buffer instance
# ---------------------------------------------------------------------------

event_buffer = EventBuffer()


# ---------------------------------------------------------------------------
# Firestore Persistence
# ---------------------------------------------------------------------------


def _get_firestore_client() -> firestore.Client:
    """Get or create Firestore client."""
    return firestore.Client(
        project=settings.gcp_project_id or None,
        database=settings.firestore_database,
    )


async def persist_event_to_firestore(
    tenant_id: str,
    run_id: str,
    event_id: str,
    event_type: str,
    data: dict,
) -> None:
    """
    Persist an activity event to Firestore at
    tenants/{tenantId}/runs/{runId}/events/{eventId}.

    This function is fire-and-forget: errors are logged but do not
    propagate to the caller, ensuring agent execution continues.
    """
    try:
        client = _get_firestore_client()
        event_doc = {
            "agent": data.get("agent", "unknown"),
            "type": event_type,
            "message": data.get("message", ""),
            "timestamp": int(time.time() * 1000),  # Unix epoch milliseconds
        }

        doc_ref = (
            client.collection("tenants")
            .document(tenant_id)
            .collection("runs")
            .document(run_id)
            .collection("events")
            .document(event_id)
        )
        doc_ref.set(event_doc)

        logger.debug(
            "Persisted event to Firestore",
            extra={
                "tenant_id": tenant_id,
                "run_id": run_id,
                "event_id": event_id,
                "event_type": event_type,
            },
        )
    except Exception:
        logger.exception(
            "Failed to persist event to Firestore",
            extra={
                "tenant_id": tenant_id,
                "run_id": run_id,
                "event_id": event_id,
            },
        )


async def ensure_run_document(
    tenant_id: str,
    run_id: str,
    goal: str,
) -> None:
    """
    Ensure the run document exists at tenants/{tenantId}/runs/{runId}.

    Creates it with status 'running' if it doesn't exist.
    """
    try:
        client = _get_firestore_client()
        run_doc = {
            "goal": goal[:500],  # Enforce max 500 chars
            "status": "running",
            "startedAt": int(time.time() * 1000),
            "finishedAt": None,
        }

        doc_ref = (
            client.collection("tenants")
            .document(tenant_id)
            .collection("runs")
            .document(run_id)
        )
        doc_ref.set(run_doc, merge=True)

        logger.debug(
            "Ensured run document exists",
            extra={"tenant_id": tenant_id, "run_id": run_id},
        )
    except Exception:
        logger.exception(
            "Failed to create/update run document",
            extra={"tenant_id": tenant_id, "run_id": run_id},
        )
