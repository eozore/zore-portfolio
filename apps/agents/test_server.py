"""
Tests for the FastAPI agents server (apps/agents/server.py).

Tests cover:
- Health check endpoint (public, no auth)
- POST /chat validation (message length, empty message)
- POST /chat SSE streaming (token, activity, done events)
- POST /chat auth rejection (missing/invalid token)
- SSE event formatting

Requirements tested: 8.1, 8.2, 8.3, 8.4
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from apps.agents.server import app, _sse_event, ChatRequest, MAX_MESSAGE_LENGTH


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# Health Check Tests
# ---------------------------------------------------------------------------


class TestHealthCheck:
    """Tests for GET /health (public endpoint)."""

    def test_health_returns_200(self, client: TestClient):
        """Health check should return 200 with service info."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "agents"
        assert "timestamp" in data

    def test_health_no_auth_required(self, client: TestClient):
        """Health check should not require authentication."""
        # No Authorization header
        response = client.get("/health")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# ChatRequest Validation Tests
# ---------------------------------------------------------------------------


class TestChatRequestValidation:
    """Tests for ChatRequest Pydantic model validation."""

    def test_valid_message(self):
        """Valid message within limits should be accepted."""
        req = ChatRequest(message="Hello Director", session_id=None)
        assert req.message == "Hello Director"
        assert req.session_id is None

    def test_message_with_session_id(self):
        """Message with a session_id should be accepted."""
        req = ChatRequest(message="Follow up", session_id="sess_abc123")
        assert req.session_id == "sess_abc123"

    def test_message_at_max_length(self):
        """Message exactly at 4000 chars should be accepted."""
        req = ChatRequest(message="a" * 4000, session_id=None)
        assert len(req.message) == 4000

    def test_message_exceeds_max_length(self):
        """Message exceeding 4000 chars should be rejected."""
        with pytest.raises(Exception):
            ChatRequest(message="a" * 4001, session_id=None)

    def test_empty_message_rejected(self):
        """Empty message should be rejected."""
        with pytest.raises(Exception):
            ChatRequest(message="", session_id=None)

    def test_max_message_length_constant(self):
        """MAX_MESSAGE_LENGTH should be 4000."""
        assert MAX_MESSAGE_LENGTH == 4000


# ---------------------------------------------------------------------------
# SSE Event Formatting Tests
# ---------------------------------------------------------------------------


class TestSSEEventFormatting:
    """Tests for the _sse_event helper function."""

    def test_token_event_format(self):
        """Token event should have proper SSE format."""
        event = _sse_event("token", {"text": "hello"}, "evt_001")
        lines = event.split("\n")
        assert lines[0] == "event: token"
        assert lines[1] == 'data: {"text": "hello"}'
        assert lines[2] == "id: evt_001"
        # Must end with double newline
        assert event.endswith("\n\n")

    def test_activity_event_format(self):
        """Activity event should contain agent info."""
        data = {"agent": "director", "status": "working", "message": "Processing"}
        event = _sse_event("activity", data, "evt_002")
        assert "event: activity" in event
        assert '"agent": "director"' in event
        assert '"status": "working"' in event
        assert "id: evt_002" in event

    def test_done_event_format(self):
        """Done event should contain run_id."""
        event = _sse_event("done", {"run_id": "run_123"}, "evt_003")
        assert "event: done" in event
        assert '"run_id": "run_123"' in event

    def test_error_event_format(self):
        """Error event should contain error message."""
        event = _sse_event("error", {"message": "Something failed"}, "evt_err")
        assert "event: error" in event
        assert '"message": "Something failed"' in event

    def test_event_without_id(self):
        """Event without ID should not include id line."""
        event = _sse_event("token", {"text": "hi"}, None)
        assert "id:" not in event
        assert "event: token" in event

    def test_event_utf8_characters(self):
        """Event data should handle UTF-8 characters correctly."""
        event = _sse_event("token", {"text": "Olá, como está?"}, "evt_utf")
        parsed_data = json.loads(event.split("\n")[1].replace("data: ", ""))
        assert parsed_data["text"] == "Olá, como está?"


# ---------------------------------------------------------------------------
# POST /chat Endpoint Tests (with mocked auth)
# ---------------------------------------------------------------------------


class TestChatEndpoint:
    """Tests for POST /chat endpoint."""

    def test_chat_missing_auth_returns_401(self, client: TestClient):
        """Chat without Authorization header should return 401."""
        response = client.post(
            "/chat",
            json={"message": "Hello", "session_id": None},
        )
        assert response.status_code == 401

    @patch("apps.agents.middleware.verify_firebase_token")
    def test_chat_invalid_token_returns_401(
        self,
        mock_verify_token: MagicMock,
        client: TestClient,
    ):
        """Chat with invalid token should return 401."""
        from firebase_admin import auth as firebase_auth

        mock_verify_token.side_effect = firebase_auth.InvalidIdTokenError("bad")

        response = client.post(
            "/chat",
            json={"message": "Hello", "session_id": None},
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert response.status_code == 401

    @patch("apps.agents.middleware.get_tenant_id_for_user", new_callable=AsyncMock)
    @patch("apps.agents.middleware.verify_firebase_token")
    def test_chat_streams_sse_events(
        self,
        mock_verify_token: MagicMock,
        mock_get_tenant: AsyncMock,
        client: TestClient,
    ):
        """Valid chat request should stream SSE events."""
        mock_verify_token.return_value = {"uid": "user_123"}
        mock_get_tenant.return_value = "tenant_123"

        response = client.post(
            "/chat",
            json={"message": "Create a blog post", "session_id": None},
            headers={"Authorization": "Bearer valid_token"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        # Parse SSE events from response body
        body = response.text
        assert "event: token" in body
        assert "event: activity" in body
        assert "event: done" in body

    @patch("apps.agents.middleware.get_tenant_id_for_user", new_callable=AsyncMock)
    @patch("apps.agents.middleware.verify_firebase_token")
    def test_chat_message_too_long_returns_422(
        self,
        mock_verify_token: MagicMock,
        mock_get_tenant: AsyncMock,
        client: TestClient,
    ):
        """Message exceeding 4000 chars should return 422."""
        mock_verify_token.return_value = {"uid": "user_123"}
        mock_get_tenant.return_value = "tenant_123"

        response = client.post(
            "/chat",
            json={"message": "x" * 4001, "session_id": None},
            headers={"Authorization": "Bearer valid_token"},
        )
        assert response.status_code == 422

    @patch("apps.agents.middleware.get_tenant_id_for_user", new_callable=AsyncMock)
    @patch("apps.agents.middleware.verify_firebase_token")
    def test_chat_empty_message_returns_422(
        self,
        mock_verify_token: MagicMock,
        mock_get_tenant: AsyncMock,
        client: TestClient,
    ):
        """Empty message should return 422."""
        mock_verify_token.return_value = {"uid": "user_123"}
        mock_get_tenant.return_value = "tenant_123"

        response = client.post(
            "/chat",
            json={"message": "", "session_id": None},
            headers={"Authorization": "Bearer valid_token"},
        )
        assert response.status_code == 422

    @patch("apps.agents.middleware.get_tenant_id_for_user", new_callable=AsyncMock)
    @patch("apps.agents.middleware.verify_firebase_token")
    def test_chat_done_event_contains_run_id(
        self,
        mock_verify_token: MagicMock,
        mock_get_tenant: AsyncMock,
        client: TestClient,
    ):
        """Done event should contain a valid run_id."""
        mock_verify_token.return_value = {"uid": "user_123"}
        mock_get_tenant.return_value = "tenant_123"

        response = client.post(
            "/chat",
            json={"message": "Hello", "session_id": None},
            headers={"Authorization": "Bearer valid_token"},
        )
        assert response.status_code == 200

        # Find the done event and verify it has a run_id
        events = response.text.split("\n\n")
        done_events = [e for e in events if "event: done" in e]
        assert len(done_events) == 1

        # Parse the data from the done event
        done_lines = done_events[0].strip().split("\n")
        data_line = [l for l in done_lines if l.startswith("data:")][0]
        data = json.loads(data_line.replace("data: ", ""))
        assert "run_id" in data
        assert len(data["run_id"]) > 0

    @patch("apps.agents.middleware.get_tenant_id_for_user", new_callable=AsyncMock)
    @patch("apps.agents.middleware.verify_firebase_token")
    def test_chat_with_existing_session_id(
        self,
        mock_verify_token: MagicMock,
        mock_get_tenant: AsyncMock,
        client: TestClient,
    ):
        """Chat with an existing session_id should work."""
        mock_verify_token.return_value = {"uid": "user_123"}
        mock_get_tenant.return_value = "tenant_123"

        response = client.post(
            "/chat",
            json={"message": "Continue", "session_id": "sess_existing_123"},
            headers={"Authorization": "Bearer valid_token"},
        )
        assert response.status_code == 200
        assert "event: done" in response.text

    @patch("apps.agents.middleware.get_tenant_id_for_user", new_callable=AsyncMock)
    @patch("apps.agents.middleware.verify_firebase_token")
    def test_chat_response_headers(
        self,
        mock_verify_token: MagicMock,
        mock_get_tenant: AsyncMock,
        client: TestClient,
    ):
        """SSE response should have correct headers."""
        mock_verify_token.return_value = {"uid": "user_123"}
        mock_get_tenant.return_value = "tenant_123"

        response = client.post(
            "/chat",
            json={"message": "Hello", "session_id": None},
            headers={"Authorization": "Bearer valid_token"},
        )
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        assert response.headers["cache-control"] == "no-cache"
