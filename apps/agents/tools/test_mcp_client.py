"""
Unit tests for apps/agents/tools/mcp_client.py

Tests cover:
- Rejection of operations without tenant_id or platform
- Clean abort when token is not found
- Clean abort when Secret Manager is unavailable/timeout
- Successful toolset creation with valid credentials
- Handling of missing POSTIZ_BASE_URL
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from apps.agents.tools.mcp_client import (
    McpCredentialError,
    McpToolsetResult,
    SecretManagerClient,
    SecretManagerUnavailableError,
    get_mcp_toolset,
    set_secret_manager_client,
)


# ---------------------------------------------------------------------------
# Test fixtures and helpers
# ---------------------------------------------------------------------------


class MockSecretManagerClient(SecretManagerClient):
    """Mock Secret Manager client for testing."""

    def __init__(
        self,
        tokens: dict[tuple[str, str], str] | None = None,
        raise_unavailable: bool = False,
        raise_not_found: bool = False,
    ) -> None:
        super().__init__(project_id="test-project")
        self._tokens = tokens or {}
        self._raise_unavailable = raise_unavailable
        self._raise_not_found = raise_not_found

    def read_secret(self, tenant_id: str, platform: str) -> str:
        if self._raise_unavailable:
            raise SecretManagerUnavailableError(
                tenant_id=tenant_id,
                platform=platform,
                reason="Secret Manager unavailable (simulated)",
            )
        if self._raise_not_found:
            raise McpCredentialError(
                tenant_id=tenant_id,
                platform=platform,
                reason="Secret not found (simulated)",
            )
        key = (tenant_id, platform)
        if key not in self._tokens:
            raise McpCredentialError(
                tenant_id=tenant_id,
                platform=platform,
                reason=f"Secret not found for {tenant_id}/{platform}",
            )
        return self._tokens[key]


# ---------------------------------------------------------------------------
# Tests: Rejection of operations without credentials
# ---------------------------------------------------------------------------


class TestRejectWithoutCredentials:
    """Requirement 14.4: Reject operations without tenant-specific credential."""

    @pytest.mark.asyncio
    async def test_rejects_empty_tenant_id(self) -> None:
        """Operations with empty tenant_id are rejected immediately."""
        result = await get_mcp_toolset(tenant_id="", platform="linkedin")

        assert result.success is False
        assert "tenant_id is required" in result.error
        assert result.toolset is None

    @pytest.mark.asyncio
    async def test_rejects_empty_platform(self) -> None:
        """Operations with empty platform are rejected immediately."""
        result = await get_mcp_toolset(tenant_id="tenant-123", platform="")

        assert result.success is False
        assert "platform is required" in result.error
        assert result.toolset is None

    @pytest.mark.asyncio
    async def test_rejects_missing_postiz_url(self) -> None:
        """Operations without POSTIZ_BASE_URL configured are rejected."""
        mock_client = MockSecretManagerClient(
            tokens={("tenant-123", "linkedin"): "valid-token"}
        )
        set_secret_manager_client(mock_client)

        with patch("apps.agents.tools.mcp_client.POSTIZ_BASE_URL", ""):
            result = await get_mcp_toolset(
                tenant_id="tenant-123", platform="linkedin"
            )

        assert result.success is False
        assert "POSTIZ_BASE_URL not configured" in result.error
        assert result.toolset is None


# ---------------------------------------------------------------------------
# Tests: Abort on token not found (Requirement 14.5)
# ---------------------------------------------------------------------------


class TestAbortTokenNotFound:
    """Requirement 14.5: Abort without partial effects when token not found."""

    @pytest.mark.asyncio
    async def test_abort_when_secret_not_found(self) -> None:
        """Aborts cleanly when the tenant's secret doesn't exist."""
        mock_client = MockSecretManagerClient(raise_not_found=True)
        set_secret_manager_client(mock_client)

        with patch(
            "apps.agents.tools.mcp_client.POSTIZ_BASE_URL",
            "https://postiz.example.com",
        ):
            result = await get_mcp_toolset(
                tenant_id="tenant-404", platform="youtube"
            )

        assert result.success is False
        assert "Credential error" in result.error
        assert result.is_temporary_failure is False
        assert result.toolset is None

    @pytest.mark.asyncio
    async def test_abort_when_token_for_different_platform(self) -> None:
        """Aborts when token exists for one platform but not the requested one."""
        mock_client = MockSecretManagerClient(
            tokens={("tenant-123", "linkedin"): "linkedin-token"}
        )
        set_secret_manager_client(mock_client)

        with patch(
            "apps.agents.tools.mcp_client.POSTIZ_BASE_URL",
            "https://postiz.example.com",
        ):
            result = await get_mcp_toolset(
                tenant_id="tenant-123", platform="youtube"
            )

        assert result.success is False
        assert "Credential error" in result.error
        assert result.is_temporary_failure is False


# ---------------------------------------------------------------------------
# Tests: Abort on Secret Manager unavailable (Requirement 14.6)
# ---------------------------------------------------------------------------


class TestAbortSecretManagerUnavailable:
    """Requirement 14.6: Abort with temporary failure indication."""

    @pytest.mark.asyncio
    async def test_abort_on_secret_manager_unavailable(self) -> None:
        """Aborts with temporary failure when Secret Manager is unavailable."""
        mock_client = MockSecretManagerClient(raise_unavailable=True)
        set_secret_manager_client(mock_client)

        with patch(
            "apps.agents.tools.mcp_client.POSTIZ_BASE_URL",
            "https://postiz.example.com",
        ):
            result = await get_mcp_toolset(
                tenant_id="tenant-123", platform="instagram"
            )

        assert result.success is False
        assert "Temporary failure" in result.error
        assert result.is_temporary_failure is True
        assert result.toolset is None


# ---------------------------------------------------------------------------
# Tests: Successful toolset creation (Requirement 14.2)
# ---------------------------------------------------------------------------


class TestSuccessfulToolsetCreation:
    """Requirement 14.2: Connect via McpToolset with credential per call."""

    @pytest.mark.asyncio
    async def test_creates_toolset_with_valid_token(self) -> None:
        """Creates McpToolset when a valid token is available."""
        import sys

        mock_client = MockSecretManagerClient(
            tokens={("tenant-abc", "linkedin"): "oauth-token-xyz"}
        )
        set_secret_manager_client(mock_client)

        mock_toolset_instance = MagicMock()
        mock_mcp_module = MagicMock()
        mock_mcp_module.McpToolset = MagicMock(
            return_value=mock_toolset_instance
        )

        with patch(
            "apps.agents.tools.mcp_client.POSTIZ_BASE_URL",
            "https://postiz.example.com",
        ), patch.dict(
            sys.modules, {"google.adk.tools.mcp_tool": mock_mcp_module}
        ):
            result = await get_mcp_toolset(
                tenant_id="tenant-abc", platform="linkedin"
            )

        assert result.success is True
        assert result.toolset is mock_toolset_instance
        assert result.error is None

    @pytest.mark.asyncio
    async def test_reads_fresh_token_every_call(self) -> None:
        """Token is read from Secret Manager on every call (never cached)."""
        import sys

        call_count = 0
        original_tokens = {("tenant-abc", "linkedin"): "token-v1"}

        class CountingClient(MockSecretManagerClient):
            def read_secret(self, tenant_id: str, platform: str) -> str:
                nonlocal call_count
                call_count += 1
                return super().read_secret(tenant_id, platform)

        mock_client = CountingClient(tokens=original_tokens)
        set_secret_manager_client(mock_client)

        mock_mcp_module = MagicMock()
        mock_mcp_module.McpToolset = MagicMock(return_value=MagicMock())

        with patch(
            "apps.agents.tools.mcp_client.POSTIZ_BASE_URL",
            "https://postiz.example.com",
        ), patch.dict(
            sys.modules, {"google.adk.tools.mcp_tool": mock_mcp_module}
        ):
            await get_mcp_toolset(tenant_id="tenant-abc", platform="linkedin")
            await get_mcp_toolset(tenant_id="tenant-abc", platform="linkedin")
            await get_mcp_toolset(tenant_id="tenant-abc", platform="linkedin")

        # Token read 3 times — one per call, never cached
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_toolset_receives_correct_credentials(self) -> None:
        """McpToolset is instantiated with the correct tenant_id and token."""
        import sys

        mock_client = MockSecretManagerClient(
            tokens={("tenant-xyz", "instagram"): "insta-token-123"}
        )
        set_secret_manager_client(mock_client)

        mock_mcp_module = MagicMock()
        mock_toolset_cls = MagicMock(return_value=MagicMock())
        mock_mcp_module.McpToolset = mock_toolset_cls

        with patch(
            "apps.agents.tools.mcp_client.POSTIZ_BASE_URL",
            "https://postiz.internal.com",
        ), patch.dict(
            sys.modules, {"google.adk.tools.mcp_tool": mock_mcp_module}
        ):
            await get_mcp_toolset(
                tenant_id="tenant-xyz", platform="instagram"
            )

            mock_toolset_cls.assert_called_once_with(
                endpoint="https://postiz.internal.com",
                credentials={
                    "tenant_id": "tenant-xyz",
                    "token": "insta-token-123",
                },
            )


# ---------------------------------------------------------------------------
# Tests: ADK import failure handling
# ---------------------------------------------------------------------------


class TestAdkImportFailure:
    """Handles gracefully when google.adk is not installed."""

    @pytest.mark.asyncio
    async def test_handles_missing_adk_module(self) -> None:
        """Returns failure when google.adk.tools.mcp_tool is not importable."""
        mock_client = MockSecretManagerClient(
            tokens={("tenant-abc", "linkedin"): "valid-token"}
        )
        set_secret_manager_client(mock_client)

        with patch(
            "apps.agents.tools.mcp_client.POSTIZ_BASE_URL",
            "https://postiz.example.com",
        ), patch(
            "builtins.__import__",
            side_effect=_import_blocker("google.adk.tools.mcp_tool"),
        ):
            result = await get_mcp_toolset(
                tenant_id="tenant-abc", platform="linkedin"
            )

        assert result.success is False
        assert "not available" in result.error


# ---------------------------------------------------------------------------
# Tests: Error classes
# ---------------------------------------------------------------------------


class TestErrorClasses:
    """Tests for custom exception classes."""

    def test_mcp_credential_error_fields(self) -> None:
        err = McpCredentialError(
            tenant_id="t1", platform="linkedin", reason="not found"
        )
        assert err.tenant_id == "t1"
        assert err.platform == "linkedin"
        assert err.reason == "not found"
        assert "t1" in str(err)
        assert "linkedin" in str(err)

    def test_secret_manager_unavailable_error_fields(self) -> None:
        err = SecretManagerUnavailableError(
            tenant_id="t2", platform="youtube", reason="timeout"
        )
        assert err.tenant_id == "t2"
        assert err.platform == "youtube"
        assert err.reason == "timeout"
        assert "t2" in str(err)


# ---------------------------------------------------------------------------
# Tests: McpToolsetResult dataclass
# ---------------------------------------------------------------------------


class TestMcpToolsetResult:
    """Tests for the result dataclass."""

    def test_default_values(self) -> None:
        result = McpToolsetResult(success=False)
        assert result.toolset is None
        assert result.error is None
        assert result.is_temporary_failure is False

    def test_success_result(self) -> None:
        result = McpToolsetResult(success=True, toolset="mock")
        assert result.success is True
        assert result.toolset == "mock"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _import_blocker(blocked_module: str):
    """Create an import side_effect that blocks a specific module."""
    import builtins

    original_import = builtins.__import__

    def custom_import(name, *args, **kwargs):
        if name == blocked_module:
            raise ImportError(f"Simulated: {name} not available")
        return original_import(name, *args, **kwargs)

    return custom_import
