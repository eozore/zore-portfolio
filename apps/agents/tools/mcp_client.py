"""
MCP Client — Per-tenant credential integration with Postiz via McpToolset.

Provides `get_mcp_toolset(tenant_id, platform)` which:
1. Reads the tenant's OAuth token from Secret Manager on every call (never cached)
2. Rejects operations without a tenant-specific credential
3. Aborts cleanly if the token is not found or Secret Manager is unavailable

Requirements: 14.2, 14.3, 14.4, 14.5, 14.6
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Environment configuration
POSTIZ_BASE_URL = os.environ.get("POSTIZ_BASE_URL", "")
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")
SECRET_MANAGER_TIMEOUT_SECONDS = 5.0


class McpCredentialError(Exception):
    """Raised when a tenant credential cannot be retrieved or is invalid."""

    def __init__(self, tenant_id: str, platform: str, reason: str) -> None:
        self.tenant_id = tenant_id
        self.platform = platform
        self.reason = reason
        super().__init__(
            f"MCP credential error for tenant={tenant_id}, "
            f"platform={platform}: {reason}"
        )


class SecretManagerUnavailableError(Exception):
    """Raised when Secret Manager is unreachable or times out (> 5s)."""

    def __init__(self, tenant_id: str, platform: str, reason: str) -> None:
        self.tenant_id = tenant_id
        self.platform = platform
        self.reason = reason
        super().__init__(
            f"Secret Manager unavailable for tenant={tenant_id}, "
            f"platform={platform}: {reason}"
        )


@dataclass
class McpToolsetResult:
    """Result of an MCP toolset creation attempt."""

    success: bool
    toolset: Any | None = None
    error: str | None = None
    is_temporary_failure: bool = False


class SecretManagerClient:
    """
    Wrapper around Google Cloud Secret Manager for testability.

    This client reads OAuth tokens from Secret Manager using the path format:
    projects/{project_id}/secrets/social-tokens-{tenant_id}-{platform}/versions/latest
    """

    def __init__(self, project_id: str | None = None) -> None:
        self._project_id = project_id or GCP_PROJECT_ID
        self._client = None

    def _get_client(self) -> Any:
        """Lazy-initialize the Secret Manager client."""
        if self._client is None:
            from google.cloud import secretmanager

            self._client = secretmanager.SecretManagerServiceClient()
        return self._client

    def read_secret(self, tenant_id: str, platform: str) -> str:
        """
        Read the OAuth token for a tenant/platform from Secret Manager.

        Parameters
        ----------
        tenant_id : str
            The tenant identifier.
        platform : str
            The target platform (e.g., 'linkedin', 'youtube', 'instagram').

        Returns
        -------
        str
            The OAuth token value.

        Raises
        ------
        McpCredentialError
            If the secret is not found or the payload is empty.
        SecretManagerUnavailableError
            If Secret Manager is unreachable or times out (> 5s).
        """
        import signal
        from google.api_core import exceptions as gcp_exceptions

        secret_name = (
            f"projects/{self._project_id}/secrets/"
            f"social-tokens-{tenant_id}-{platform}/versions/latest"
        )

        try:
            client = self._get_client()

            # Set a timeout handler for the 5-second limit
            def _timeout_handler(signum: int, frame: Any) -> None:
                raise TimeoutError("Secret Manager read exceeded 5s timeout")

            # Use alarm-based timeout on Unix systems
            old_handler = None
            try:
                old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
                signal.alarm(SECRET_MANAGER_TIMEOUT_SECONDS_INT)
            except (ValueError, OSError):
                # signal.alarm not available (e.g., non-main thread or Windows)
                pass

            try:
                response = client.access_secret_version(
                    request={"name": secret_name}
                )
            finally:
                # Reset alarm
                try:
                    signal.alarm(0)
                    if old_handler is not None:
                        signal.signal(signal.SIGALRM, old_handler)
                except (ValueError, OSError):
                    pass

            payload = response.payload.data.decode("UTF-8")
            if not payload:
                raise McpCredentialError(
                    tenant_id=tenant_id,
                    platform=platform,
                    reason="Secret payload is empty",
                )
            return payload

        except TimeoutError:
            raise SecretManagerUnavailableError(
                tenant_id=tenant_id,
                platform=platform,
                reason="Secret Manager read timed out (> 5s)",
            )
        except gcp_exceptions.NotFound:
            raise McpCredentialError(
                tenant_id=tenant_id,
                platform=platform,
                reason=f"Secret not found: {secret_name}",
            )
        except gcp_exceptions.PermissionDenied:
            raise McpCredentialError(
                tenant_id=tenant_id,
                platform=platform,
                reason="Permission denied accessing Secret Manager",
            )
        except (
            gcp_exceptions.ServiceUnavailable,
            gcp_exceptions.DeadlineExceeded,
            ConnectionError,
            OSError,
        ) as e:
            raise SecretManagerUnavailableError(
                tenant_id=tenant_id,
                platform=platform,
                reason=f"Secret Manager unavailable: {str(e)}",
            )


# Module-level default client (can be replaced for testing)
_secret_manager_client: SecretManagerClient | None = None

# Integer version for signal.alarm (must be int)
SECRET_MANAGER_TIMEOUT_SECONDS_INT = int(SECRET_MANAGER_TIMEOUT_SECONDS)


def _get_secret_manager_client() -> SecretManagerClient:
    """Return the module-level Secret Manager client (lazy singleton)."""
    global _secret_manager_client
    if _secret_manager_client is None:
        _secret_manager_client = SecretManagerClient()
    return _secret_manager_client


def set_secret_manager_client(client: SecretManagerClient) -> None:
    """
    Replace the module-level Secret Manager client (for testing).

    Parameters
    ----------
    client : SecretManagerClient
        A mock or custom client instance.
    """
    global _secret_manager_client
    _secret_manager_client = client


async def get_mcp_toolset(
    tenant_id: str, platform: str
) -> McpToolsetResult:
    """
    Create an McpToolset with per-tenant credentials for the Postiz MCP server.

    This function:
    1. Validates that tenant_id and platform are provided (rejects empty values)
    2. Reads the OAuth token from Secret Manager on every call (never cached)
    3. Creates an McpToolset instance with the tenant credential
    4. Aborts cleanly on any credential failure

    Parameters
    ----------
    tenant_id : str
        The tenant identifier from the session context.
    platform : str
        The target social platform (e.g., 'linkedin', 'youtube', 'instagram').

    Returns
    -------
    McpToolsetResult
        Result with success=True and toolset on success,
        or success=False with error details on failure.
    """
    # Requirement 14.4: Reject operations without tenant-specific credential
    if not tenant_id:
        logger.error("MCP operation rejected: no tenant_id provided")
        return McpToolsetResult(
            success=False,
            error="Operation rejected: tenant_id is required",
        )

    if not platform:
        logger.error(
            "MCP operation rejected: no platform provided "
            f"(tenant_id={tenant_id})"
        )
        return McpToolsetResult(
            success=False,
            error="Operation rejected: platform is required",
        )

    if not POSTIZ_BASE_URL:
        logger.error(
            "MCP operation rejected: POSTIZ_BASE_URL not configured "
            f"(tenant_id={tenant_id}, platform={platform})"
        )
        return McpToolsetResult(
            success=False,
            error="Operation rejected: POSTIZ_BASE_URL not configured",
        )

    # Requirement 14.3: Read token from Secret Manager on every call
    secret_client = _get_secret_manager_client()

    try:
        token = secret_client.read_secret(tenant_id, platform)
    except McpCredentialError as e:
        # Requirement 14.5: Abort without partial effects, log error
        logger.error(
            "MCP credential error — aborting publication. "
            f"tenant_id={tenant_id}, platform={platform}, reason={e.reason}"
        )
        return McpToolsetResult(
            success=False,
            error=f"Credential error: {e.reason}",
            is_temporary_failure=False,
        )
    except SecretManagerUnavailableError as e:
        # Requirement 14.6: Abort, register temporary failure
        logger.error(
            "Secret Manager unavailable — aborting publication. "
            f"tenant_id={tenant_id}, platform={platform}, reason={e.reason}"
        )
        return McpToolsetResult(
            success=False,
            error=f"Temporary failure: {e.reason}",
            is_temporary_failure=True,
        )

    # Requirement 14.2: Connect via McpToolset with credential per call
    try:
        from google.adk.tools.mcp_tool import McpToolset
    except ImportError:
        logger.error(
            "google.adk.tools.mcp_tool not available — "
            "cannot create McpToolset"
        )
        return McpToolsetResult(
            success=False,
            error="McpToolset not available (google-adk not installed)",
        )

    try:
        toolset = McpToolset(
            endpoint=POSTIZ_BASE_URL,
            credentials={"tenant_id": tenant_id, "token": token},
        )
        return McpToolsetResult(success=True, toolset=toolset)
    except Exception as e:
        logger.error(
            f"Failed to create McpToolset: {str(e)} "
            f"(tenant_id={tenant_id}, platform={platform})"
        )
        return McpToolsetResult(
            success=False,
            error=f"Failed to create McpToolset: {str(e)}",
        )
