"""
Unit tests for apps/agents/usage_tracker.py — token usage and publication tracking.

Validates Requirements 5.5, 5.7:
- 5.5: After agent execution, record usage in usage/{yyyymm}
- 5.7: If tracking fails, execution continues (no exception raised)
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.agents.usage_tracker import (
    _get_current_period,
    record_publication,
    record_token_usage,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_firestore() -> MagicMock:
    """Create a mock Firestore async client with chained collection/document.

    collection() and document() are synchronous on AsyncClient (return refs),
    while set() is async.
    """
    mock_db = MagicMock()
    mock_usage_ref = MagicMock()
    mock_usage_ref.set = AsyncMock()

    # Chain: db.collection("tenants").document(tid).collection("usage").document(period)
    mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value = (
        mock_usage_ref
    )
    return mock_db


# ---------------------------------------------------------------------------
# Tests: _get_current_period
# ---------------------------------------------------------------------------


class TestGetCurrentPeriod:
    """Period key is in YYYYMM format from UTC time."""

    def test_format_length(self):
        period = _get_current_period()
        assert len(period) == 6

    def test_format_is_digits(self):
        period = _get_current_period()
        assert period.isdigit()

    def test_format_with_frozen_time(self):
        from datetime import datetime, timezone

        fixed_dt = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        with patch("apps.agents.usage_tracker.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_dt
            # datetime.now(tz).strftime(...) is called on the return value
            period = _get_current_period()
            assert period == "202501"


# ---------------------------------------------------------------------------
# Tests: record_token_usage — success path
# ---------------------------------------------------------------------------


class TestRecordTokenUsageSuccess:
    """Happy path: token usage is recorded in Firestore."""

    @pytest.mark.asyncio
    async def test_calls_firestore_set_with_merge(self):
        """Firestore set is called with merge=True."""
        mock_db = _make_mock_firestore()
        mock_ref = mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value

        await record_token_usage(
            tenant_id="tenant-123",
            agent_name="writer",
            model_id="gemini-2.5-pro",
            input_tokens=500,
            output_tokens=200,
            firestore_client=mock_db,
        )

        mock_ref.set.assert_called_once()
        call_args = mock_ref.set.call_args
        assert call_args[1] == {"merge": True}

    @pytest.mark.asyncio
    async def test_uses_correct_document_path(self):
        """Usage is written to tenants/{tenantId}/usage/{yyyymm}."""
        mock_db = _make_mock_firestore()

        await record_token_usage(
            tenant_id="tenant-abc",
            agent_name="director",
            model_id="gemini-2.5-pro",
            input_tokens=100,
            output_tokens=50,
            firestore_client=mock_db,
        )

        # Verify collection/document chain
        mock_db.collection.assert_called_with("tenants")
        mock_db.collection.return_value.document.assert_called_with("tenant-abc")
        mock_db.collection.return_value.document.return_value.collection.assert_called_with("usage")
        # Period document is called with a 6-digit string
        period_call = mock_db.collection.return_value.document.return_value.collection.return_value.document.call_args
        assert len(period_call[0][0]) == 6
        assert period_call[0][0].isdigit()

    @pytest.mark.asyncio
    async def test_update_data_contains_token_increments(self):
        """Update data includes FieldValue increments for tokens."""
        mock_db = _make_mock_firestore()
        mock_ref = mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value

        await record_token_usage(
            tenant_id="t1",
            agent_name="researcher",
            model_id="gemini-2.5-flash",
            input_tokens=300,
            output_tokens=150,
            firestore_client=mock_db,
        )

        call_args = mock_ref.set.call_args[0][0]
        # Check all expected keys are present
        assert "totalInputTokens" in call_args
        assert "totalOutputTokens" in call_args
        assert "byModel.gemini-2.5-flash.inputTokens" in call_args
        assert "byModel.gemini-2.5-flash.outputTokens" in call_args
        assert "lastUpdated" in call_args

    @pytest.mark.asyncio
    async def test_logs_success(self, caplog):
        """Successful recording logs an info message."""
        mock_db = _make_mock_firestore()

        with caplog.at_level(logging.INFO):
            await record_token_usage(
                tenant_id="t1",
                agent_name="writer",
                model_id="gemini-2.5-pro",
                input_tokens=100,
                output_tokens=50,
                firestore_client=mock_db,
            )

        assert "Token usage recorded" in caplog.text


# ---------------------------------------------------------------------------
# Tests: record_token_usage — failure path (Req 5.7)
# ---------------------------------------------------------------------------


class TestRecordTokenUsageFailure:
    """When Firestore write fails, execution continues without raising."""

    @pytest.mark.asyncio
    async def test_does_not_raise_on_firestore_error(self):
        """Exception from Firestore is swallowed — no exception propagated."""
        mock_db = _make_mock_firestore()
        mock_ref = mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value
        mock_ref.set.side_effect = Exception("Firestore unavailable")

        # Should NOT raise
        await record_token_usage(
            tenant_id="t1",
            agent_name="director",
            model_id="gemini-2.5-pro",
            input_tokens=100,
            output_tokens=50,
            firestore_client=mock_db,
        )

    @pytest.mark.asyncio
    async def test_logs_failure(self, caplog):
        """Failure is logged for later reconciliation."""
        mock_db = _make_mock_firestore()
        mock_ref = mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value
        mock_ref.set.side_effect = Exception("Network error")

        with caplog.at_level(logging.ERROR):
            await record_token_usage(
                tenant_id="t1",
                agent_name="analyst",
                model_id="gemini-2.5-flash",
                input_tokens=200,
                output_tokens=100,
                firestore_client=mock_db,
            )

        assert "Failed to record token usage" in caplog.text

    @pytest.mark.asyncio
    async def test_does_not_raise_on_connection_refused(self):
        """ConnectionRefusedError from Firestore is handled gracefully."""
        mock_db = _make_mock_firestore()
        mock_ref = mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value
        mock_ref.set.side_effect = ConnectionRefusedError("Connection refused")

        await record_token_usage(
            tenant_id="t1",
            agent_name="writer",
            model_id="gemini-2.5-pro",
            input_tokens=50,
            output_tokens=25,
            firestore_client=mock_db,
        )


# ---------------------------------------------------------------------------
# Tests: record_publication — success path
# ---------------------------------------------------------------------------


class TestRecordPublicationSuccess:
    """Happy path: publication event is recorded."""

    @pytest.mark.asyncio
    async def test_calls_firestore_set_with_merge(self):
        """Firestore set is called with merge=True."""
        mock_db = _make_mock_firestore()
        mock_ref = mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value

        await record_publication(
            tenant_id="tenant-123",
            platform="linkedin_post",
            firestore_client=mock_db,
        )

        mock_ref.set.assert_called_once()
        call_args = mock_ref.set.call_args
        assert call_args[1] == {"merge": True}

    @pytest.mark.asyncio
    async def test_update_data_contains_publication_increments(self):
        """Update data includes postsPublished and byPlatform increments."""
        mock_db = _make_mock_firestore()
        mock_ref = mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value

        await record_publication(
            tenant_id="t1",
            platform="blog",
            firestore_client=mock_db,
        )

        call_args = mock_ref.set.call_args[0][0]
        assert "postsPublished" in call_args
        assert "byPlatform.blog" in call_args
        assert "lastUpdated" in call_args

    @pytest.mark.asyncio
    async def test_logs_success(self, caplog):
        """Successful recording logs an info message."""
        mock_db = _make_mock_firestore()

        with caplog.at_level(logging.INFO):
            await record_publication(
                tenant_id="t1",
                platform="instagram_feed",
                firestore_client=mock_db,
            )

        assert "Publication recorded" in caplog.text


# ---------------------------------------------------------------------------
# Tests: record_publication — failure path
# ---------------------------------------------------------------------------


class TestRecordPublicationFailure:
    """When Firestore write fails, no exception is raised."""

    @pytest.mark.asyncio
    async def test_does_not_raise_on_firestore_error(self):
        """Exception from Firestore is swallowed."""
        mock_db = _make_mock_firestore()
        mock_ref = mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value
        mock_ref.set.side_effect = Exception("Timeout")

        await record_publication(
            tenant_id="t1",
            platform="youtube_video",
            firestore_client=mock_db,
        )

    @pytest.mark.asyncio
    async def test_logs_failure(self, caplog):
        """Failure is logged for reconciliation."""
        mock_db = _make_mock_firestore()
        mock_ref = mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value
        mock_ref.set.side_effect = RuntimeError("Quota exceeded")

        with caplog.at_level(logging.ERROR):
            await record_publication(
                tenant_id="t1",
                platform="blog",
                firestore_client=mock_db,
            )

        assert "Failed to record publication" in caplog.text
