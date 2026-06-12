"""
Tests for the event persistence and buffering module (apps/agents/event_store.py).

Tests cover:
- EventBuffer: add, retrieve, TTL expiration, cleanup
- get_events_after_id: replay from specific event ID
- persist_event_to_firestore: Firestore write (mocked)
- ensure_run_document: run document creation (mocked)

Requirements tested: 8.5, 8.6
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from apps.agents.event_store import (
    BufferedEvent,
    EventBuffer,
    EVENT_BUFFER_TTL_SECONDS,
    event_buffer,
    persist_event_to_firestore,
    ensure_run_document,
)


# ---------------------------------------------------------------------------
# BufferedEvent Tests
# ---------------------------------------------------------------------------


class TestBufferedEvent:
    """Tests for the BufferedEvent dataclass."""

    def test_event_not_expired_when_fresh(self):
        """A freshly created event should not be expired."""
        evt = BufferedEvent(
            event_id="evt_001",
            event_type="activity",
            data={"agent": "director"},
            raw_sse="event: activity\ndata: {}\n\n",
        )
        assert not evt.is_expired

    def test_event_expired_after_ttl(self):
        """An event older than TTL should be expired."""
        evt = BufferedEvent(
            event_id="evt_001",
            event_type="activity",
            data={"agent": "director"},
            raw_sse="event: activity\ndata: {}\n\n",
            created_at=time.time() - EVENT_BUFFER_TTL_SECONDS - 1,
        )
        assert evt.is_expired

    def test_event_not_expired_at_boundary(self):
        """An event exactly at TTL boundary should not be expired."""
        evt = BufferedEvent(
            event_id="evt_001",
            event_type="activity",
            data={"agent": "director"},
            raw_sse="event: activity\ndata: {}\n\n",
            created_at=time.time() - EVENT_BUFFER_TTL_SECONDS + 1,
        )
        assert not evt.is_expired


# ---------------------------------------------------------------------------
# EventBuffer Tests
# ---------------------------------------------------------------------------


class TestEventBuffer:
    """Tests for the EventBuffer class."""

    def setup_method(self):
        """Create a fresh buffer for each test."""
        self.buffer = EventBuffer()

    def test_add_event_stores_in_buffer(self):
        """Adding an event should store it retrievable by run_id."""
        self.buffer.add_event(
            run_id="run_1",
            event_id="evt_run_1_0001",
            event_type="activity",
            data={"agent": "director", "status": "working"},
            raw_sse="event: activity\ndata: {}\n\n",
        )
        events = self.buffer.get_all_events("run_1")
        assert len(events) == 1
        assert events[0].event_id == "evt_run_1_0001"
        assert events[0].event_type == "activity"

    def test_add_multiple_events_same_run(self):
        """Multiple events for the same run should all be stored."""
        for i in range(5):
            self.buffer.add_event(
                run_id="run_1",
                event_id=f"evt_run_1_{i:04d}",
                event_type="token",
                data={"text": f"chunk_{i}"},
                raw_sse=f"event: token\ndata: chunk_{i}\n\n",
            )
        events = self.buffer.get_all_events("run_1")
        assert len(events) == 5

    def test_add_events_different_runs_isolated(self):
        """Events for different runs should be isolated."""
        self.buffer.add_event(
            run_id="run_1",
            event_id="evt_run_1_0001",
            event_type="token",
            data={"text": "hello"},
            raw_sse="event: token\ndata: hello\n\n",
        )
        self.buffer.add_event(
            run_id="run_2",
            event_id="evt_run_2_0001",
            event_type="activity",
            data={"agent": "writer"},
            raw_sse="event: activity\ndata: {}\n\n",
        )
        assert len(self.buffer.get_all_events("run_1")) == 1
        assert len(self.buffer.get_all_events("run_2")) == 1

    def test_get_all_events_unknown_run(self):
        """Getting events for unknown run_id should return empty list."""
        events = self.buffer.get_all_events("nonexistent_run")
        assert events == []

    def test_get_events_after_id_returns_subsequent(self):
        """Should return only events after the specified event_id."""
        for i in range(5):
            self.buffer.add_event(
                run_id="run_1",
                event_id=f"evt_run_1_{i:04d}",
                event_type="token",
                data={"text": f"chunk_{i}"},
                raw_sse=f"event: token\ndata: chunk_{i}\n\n",
            )

        # Get events after the 3rd event (index 2)
        events = self.buffer.get_events_after_id("run_1", "evt_run_1_0002")
        assert len(events) == 2
        assert events[0].event_id == "evt_run_1_0003"
        assert events[1].event_id == "evt_run_1_0004"

    def test_get_events_after_id_not_found_returns_all(self):
        """If last_event_id is not in buffer, return all events."""
        for i in range(3):
            self.buffer.add_event(
                run_id="run_1",
                event_id=f"evt_run_1_{i:04d}",
                event_type="token",
                data={"text": f"chunk_{i}"},
                raw_sse=f"event: token\ndata: chunk_{i}\n\n",
            )

        events = self.buffer.get_events_after_id("run_1", "evt_unknown")
        assert len(events) == 3

    def test_get_events_after_id_unknown_run(self):
        """Getting events after ID for unknown run should return empty list."""
        events = self.buffer.get_events_after_id("nonexistent", "evt_001")
        assert events == []

    def test_get_events_after_last_event_returns_empty(self):
        """If last_event_id is the last event, should return empty."""
        for i in range(3):
            self.buffer.add_event(
                run_id="run_1",
                event_id=f"evt_run_1_{i:04d}",
                event_type="token",
                data={"text": f"chunk_{i}"},
                raw_sse=f"event: token\ndata: chunk_{i}\n\n",
            )

        events = self.buffer.get_events_after_id("run_1", "evt_run_1_0002")
        assert len(events) == 0

    def test_expired_events_cleaned_on_access(self):
        """Expired events should be removed when buffer is accessed."""
        # Add an expired event
        self.buffer.add_event(
            run_id="run_1",
            event_id="evt_old",
            event_type="token",
            data={"text": "old"},
            raw_sse="event: token\ndata: old\n\n",
        )
        # Manually age the event
        self.buffer._buffers["run_1"][0].created_at = (
            time.time() - EVENT_BUFFER_TTL_SECONDS - 10
        )

        # Add a fresh event
        self.buffer.add_event(
            run_id="run_1",
            event_id="evt_new",
            event_type="token",
            data={"text": "new"},
            raw_sse="event: token\ndata: new\n\n",
        )

        events = self.buffer.get_all_events("run_1")
        assert len(events) == 1
        assert events[0].event_id == "evt_new"

    def test_cleanup_all_expired_removes_empty_runs(self):
        """cleanup_all_expired should remove run keys with no events."""
        self.buffer.add_event(
            run_id="run_1",
            event_id="evt_old",
            event_type="token",
            data={"text": "old"},
            raw_sse="event: token\ndata: old\n\n",
        )
        # Age the event past TTL
        self.buffer._buffers["run_1"][0].created_at = (
            time.time() - EVENT_BUFFER_TTL_SECONDS - 10
        )

        self.buffer.cleanup_all_expired()
        assert "run_1" not in self.buffer._buffers

    def test_ttl_is_300_seconds(self):
        """EVENT_BUFFER_TTL_SECONDS should be 300."""
        assert EVENT_BUFFER_TTL_SECONDS == 300


# ---------------------------------------------------------------------------
# Firestore Persistence Tests (mocked)
# ---------------------------------------------------------------------------


class TestPersistEventToFirestore:
    """Tests for persist_event_to_firestore function."""

    @pytest.mark.asyncio
    @patch("apps.agents.event_store._get_firestore_client")
    async def test_persist_writes_to_correct_path(self, mock_get_client):
        """Should write event to tenants/{tid}/runs/{rid}/events/{eid}."""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_doc = MagicMock()
        mock_subcol = MagicMock()
        mock_run_doc = MagicMock()
        mock_events_col = MagicMock()
        mock_event_doc = MagicMock()

        mock_get_client.return_value = mock_client
        mock_client.collection.return_value = mock_collection
        mock_collection.document.return_value = mock_doc
        mock_doc.collection.return_value = mock_subcol
        mock_subcol.document.return_value = mock_run_doc
        mock_run_doc.collection.return_value = mock_events_col
        mock_events_col.document.return_value = mock_event_doc

        await persist_event_to_firestore(
            tenant_id="tenant_123",
            run_id="run_456",
            event_id="evt_001",
            event_type="activity",
            data={"agent": "director", "message": "Working..."},
        )

        mock_client.collection.assert_called_with("tenants")
        mock_collection.document.assert_called_with("tenant_123")
        mock_doc.collection.assert_called_with("runs")
        mock_subcol.document.assert_called_with("run_456")
        mock_run_doc.collection.assert_called_with("events")
        mock_events_col.document.assert_called_with("evt_001")
        mock_event_doc.set.assert_called_once()

        # Verify the document structure
        call_args = mock_event_doc.set.call_args[0][0]
        assert call_args["agent"] == "director"
        assert call_args["type"] == "activity"
        assert call_args["message"] == "Working..."
        assert "timestamp" in call_args

    @pytest.mark.asyncio
    @patch("apps.agents.event_store._get_firestore_client")
    async def test_persist_does_not_raise_on_failure(self, mock_get_client):
        """Firestore failure should be logged but not raised."""
        mock_get_client.side_effect = Exception("Firestore unavailable")

        # Should not raise
        await persist_event_to_firestore(
            tenant_id="tenant_123",
            run_id="run_456",
            event_id="evt_001",
            event_type="activity",
            data={"agent": "director", "message": "Test"},
        )


class TestEnsureRunDocument:
    """Tests for ensure_run_document function."""

    @pytest.mark.asyncio
    @patch("apps.agents.event_store._get_firestore_client")
    async def test_creates_run_document(self, mock_get_client):
        """Should create run document at tenants/{tid}/runs/{rid}."""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_doc = MagicMock()
        mock_subcol = MagicMock()
        mock_run_doc = MagicMock()

        mock_get_client.return_value = mock_client
        mock_client.collection.return_value = mock_collection
        mock_collection.document.return_value = mock_doc
        mock_doc.collection.return_value = mock_subcol
        mock_subcol.document.return_value = mock_run_doc

        await ensure_run_document(
            tenant_id="tenant_123",
            run_id="run_456",
            goal="Create a blog post about AI",
        )

        mock_run_doc.set.assert_called_once()
        call_args, call_kwargs = mock_run_doc.set.call_args
        doc_data = call_args[0]
        assert doc_data["goal"] == "Create a blog post about AI"
        assert doc_data["status"] == "running"
        assert "startedAt" in doc_data
        assert call_kwargs.get("merge") is True

    @pytest.mark.asyncio
    @patch("apps.agents.event_store._get_firestore_client")
    async def test_truncates_goal_to_500_chars(self, mock_get_client):
        """Goal should be truncated to 500 characters."""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_doc = MagicMock()
        mock_subcol = MagicMock()
        mock_run_doc = MagicMock()

        mock_get_client.return_value = mock_client
        mock_client.collection.return_value = mock_collection
        mock_collection.document.return_value = mock_doc
        mock_doc.collection.return_value = mock_subcol
        mock_subcol.document.return_value = mock_run_doc

        long_goal = "x" * 1000
        await ensure_run_document(
            tenant_id="tenant_123",
            run_id="run_456",
            goal=long_goal,
        )

        call_args = mock_run_doc.set.call_args[0][0]
        assert len(call_args["goal"]) == 500

    @pytest.mark.asyncio
    @patch("apps.agents.event_store._get_firestore_client")
    async def test_does_not_raise_on_failure(self, mock_get_client):
        """Firestore failure should be logged but not raised."""
        mock_get_client.side_effect = Exception("Firestore unavailable")

        # Should not raise
        await ensure_run_document(
            tenant_id="tenant_123",
            run_id="run_456",
            goal="Test goal",
        )
