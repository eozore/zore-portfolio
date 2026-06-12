"""
Tests for the tenant creation service.

Tests cover:
- Successful tenant creation with all required fields
- Idempotent behavior (no error if tenant already exists)
- Atomic batch write structure (all docs or none)
- Graceful error handling on Firestore failure
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch, call

import pytest

from apps.agents.tenant_service import (
    TenantCreationError,
    TenantCreationResult,
    create_tenant_for_user,
)


@pytest.fixture
def mock_firestore():
    """Create a mock Firestore client with proper collection/document structure."""
    with patch("apps.agents.tenant_service._get_firestore_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Set up the collection chain
        mock_collection = MagicMock()
        mock_client.collection.return_value = mock_collection

        # Tenant document reference
        mock_tenant_ref = MagicMock()
        mock_collection.document.return_value = mock_tenant_ref

        # Subcollection references
        mock_settings_collection = MagicMock()
        mock_members_collection = MagicMock()
        mock_settings_ref = MagicMock()
        mock_member_ref = MagicMock()

        def subcollection_side_effect(name):
            if name == "settings":
                return mock_settings_collection
            elif name == "members":
                return mock_members_collection
            return MagicMock()

        mock_tenant_ref.collection.side_effect = subcollection_side_effect
        mock_settings_collection.document.return_value = mock_settings_ref
        mock_members_collection.document.return_value = mock_member_ref

        # Batch
        mock_batch = MagicMock()
        mock_client.batch.return_value = mock_batch

        yield {
            "client": mock_client,
            "tenant_ref": mock_tenant_ref,
            "settings_ref": mock_settings_ref,
            "member_ref": mock_member_ref,
            "batch": mock_batch,
        }


class TestCreateTenantForUser:
    """Tests for create_tenant_for_user function."""

    def test_successful_creation(self, mock_firestore):
        """Test that a new tenant is created with all required fields."""
        # Tenant does not exist yet
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_firestore["tenant_ref"].get.return_value = mock_doc

        result = create_tenant_for_user(
            uid="user123",
            name="John Doe",
            email="john@example.com",
            auth_method="google",
        )

        assert result.success is True
        assert result.tenant_id == "user123"
        assert result.error is None

    def test_tenant_document_has_required_fields(self, mock_firestore):
        """Test that the tenant document contains all specified fields."""
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_firestore["tenant_ref"].get.return_value = mock_doc

        create_tenant_for_user(
            uid="user123",
            name="John Doe",
            email="john@example.com",
            auth_method="google",
        )

        # Get the first call to batch.set (tenant document)
        batch_set_calls = mock_firestore["batch"].set.call_args_list
        assert len(batch_set_calls) == 3  # tenant, settings, member

        tenant_data = batch_set_calls[0][0][1]
        assert tenant_data["tenantId"] == "user123"
        assert tenant_data["name"] == "John Doe"
        assert tenant_data["email"] == "john@example.com"
        assert tenant_data["authMethod"] == "google"
        assert "createdAt" in tenant_data
        assert isinstance(tenant_data["createdAt"], int)

    def test_tenant_profile_initialized(self, mock_firestore):
        """Test that the tenant profile is initialized with empty defaults."""
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_firestore["tenant_ref"].get.return_value = mock_doc

        create_tenant_for_user(
            uid="user123",
            name="John Doe",
            email="john@example.com",
            auth_method="email",
        )

        batch_set_calls = mock_firestore["batch"].set.call_args_list
        tenant_data = batch_set_calls[0][0][1]

        profile = tenant_data["profile"]
        assert profile["brandVoice"] == ""
        assert profile["niche"] == ""
        assert profile["persona"] == ""
        assert profile["languages"] == []
        assert profile["links"] == []

    def test_subscription_placeholder_initialized(self, mock_firestore):
        """Test that subscription is initialized with free plan placeholder."""
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_firestore["tenant_ref"].get.return_value = mock_doc

        create_tenant_for_user(
            uid="user123",
            name="John Doe",
            email="john@example.com",
            auth_method="google",
        )

        batch_set_calls = mock_firestore["batch"].set.call_args_list
        tenant_data = batch_set_calls[0][0][1]

        subscription = tenant_data["subscription"]
        assert subscription["plan"] == "free"
        assert subscription["status"] == "active"
        assert subscription["stripeCustomerId"] == ""
        assert subscription["entitlements"] == {}

    def test_settings_all_autopublish_false(self, mock_firestore):
        """Test that all autoPublish toggles are initialized to false."""
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_firestore["tenant_ref"].get.return_value = mock_doc

        create_tenant_for_user(
            uid="user123",
            name="John Doe",
            email="john@example.com",
            auth_method="google",
        )

        batch_set_calls = mock_firestore["batch"].set.call_args_list
        settings_data = batch_set_calls[1][0][1]

        publishing = settings_data["publishing"]
        expected_formats = [
            "blog",
            "linkedin_post",
            "youtube_video",
            "instagram_feed",
            "instagram_reel",
            "instagram_story",
        ]
        for fmt in expected_formats:
            assert fmt in publishing
            assert publishing[fmt]["autoPublish"] is False

    def test_member_created_with_owner_role(self, mock_firestore):
        """Test that the member document is created with role=owner."""
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_firestore["tenant_ref"].get.return_value = mock_doc

        create_tenant_for_user(
            uid="user123",
            name="John Doe",
            email="john@example.com",
            auth_method="google",
        )

        batch_set_calls = mock_firestore["batch"].set.call_args_list
        member_data = batch_set_calls[2][0][1]

        assert member_data["uid"] == "user123"
        assert member_data["role"] == "owner"

    def test_batch_commit_called(self, mock_firestore):
        """Test that the batch is committed (atomicity)."""
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_firestore["tenant_ref"].get.return_value = mock_doc

        create_tenant_for_user(
            uid="user123",
            name="John Doe",
            email="john@example.com",
            auth_method="google",
        )

        mock_firestore["batch"].commit.assert_called_once()

    def test_idempotent_when_tenant_exists(self, mock_firestore):
        """Test that existing tenant is returned without modifications."""
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_firestore["tenant_ref"].get.return_value = mock_doc

        result = create_tenant_for_user(
            uid="existing_user",
            name="John Doe",
            email="john@example.com",
            auth_method="google",
        )

        assert result.success is True
        assert result.tenant_id == "existing_user"
        # Batch should NOT be created/committed
        mock_firestore["client"].batch.assert_not_called()

    def test_firestore_failure_returns_error(self, mock_firestore):
        """Test that Firestore failures are handled gracefully."""
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_firestore["tenant_ref"].get.return_value = mock_doc

        # Simulate batch commit failure
        mock_firestore["batch"].commit.side_effect = Exception(
            "Firestore unavailable"
        )

        result = create_tenant_for_user(
            uid="user123",
            name="John Doe",
            email="john@example.com",
            auth_method="google",
        )

        assert result.success is False
        assert result.tenant_id is None
        assert "Firestore batch write failed" in result.error
        assert "Firestore unavailable" in result.error

    def test_email_auth_method(self, mock_firestore):
        """Test creation with email auth method."""
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_firestore["tenant_ref"].get.return_value = mock_doc

        result = create_tenant_for_user(
            uid="user456",
            name="Jane Doe",
            email="jane@example.com",
            auth_method="email",
        )

        assert result.success is True
        batch_set_calls = mock_firestore["batch"].set.call_args_list
        tenant_data = batch_set_calls[0][0][1]
        assert tenant_data["authMethod"] == "email"
