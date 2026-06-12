"""
Produtor de Mídia sub-agent — generates HTML/CSS templates for visual assets.

The Produtor generates self-contained HTML/CSS templates that respect the tenant's
brand identity (colors, typography, layout patterns) and submits them to the
Renderizador service (Puppeteer) for conversion to image (PNG/JPEG) or video (MP4).

It can select existing templates from the tenant's library or create new ones,
always matching the target platform's dimensions.

Requirements: 10.1, 10.5, 19.1, 19.2, 19.4, 19.5, 22.1, 22.3
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

try:
    from google.adk.agents import LlmAgent
except ImportError:  # pragma: no cover
    LlmAgent = None  # type: ignore[assignment, misc]

from apps.agents.models import get_model_for_role
from apps.agents.team.prompts import PRODUTOR_PROMPT

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

# ---------------------------------------------------------------------------
# Platform specifications — dimensions per target format
# ---------------------------------------------------------------------------

PLATFORM_SPECS: dict[str, dict[str, int]] = {
    "instagram_feed": {"width": 1080, "height": 1080},
    "instagram_reel": {"width": 1080, "height": 1920},
    "instagram_story": {"width": 1080, "height": 1920},
    "youtube_video": {"width": 1920, "height": 1080},
    "linkedin_post": {"width": 1200, "height": 627},
}

# Render timeout per asset type (seconds)
RENDER_TIMEOUTS: dict[str, int] = {
    "image": 30,
    "video": 120,
}

# Maximum video duration in seconds
MAX_VIDEO_DURATION: int = 60

# Renderer service base URL (internal Cloud Run)
RENDERER_BASE_URL: str = os.environ.get(
    "RENDERER_BASE_URL", "http://localhost:3001"
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class MediaRequest:
    """Request to render an HTML/CSS template into a media asset."""

    type: str  # "image" | "video"
    template_html: str
    target_platform: str  # PublishFormat value
    article_id: str
    tenant_id: str
    template_id: str | None = None


@dataclass
class MediaAsset:
    """Result of a successful media render."""

    url: str  # URL in Cloud Storage
    type: str  # "image/png" | "image/jpeg" | "video/mp4"
    width: int
    height: int
    duration: int | None = None  # seconds (video only, max 60)
    template_id: str | None = None


@dataclass
class RenderRequest:
    """Payload sent to the Renderizador's /render endpoint."""

    html: str
    width: int
    height: int
    output_format: str  # "png" | "jpeg" | "mp4"
    duration: int | None = None  # video duration in seconds (max 60)


@dataclass
class RenderResult:
    """Response from the Renderizador's /render endpoint."""

    success: bool
    url: str | None = None  # Cloud Storage URL on success
    error: str | None = None  # error message on failure
    error_line: int | None = None  # line of HTML/CSS error if applicable


# ---------------------------------------------------------------------------
# Renderer integration
# ---------------------------------------------------------------------------


async def render_media(request: MediaRequest) -> RenderResult:
    """
    Submit a MediaRequest to the Renderizador service and return the result.

    Makes an HTTP POST to the /render endpoint with the template HTML and
    platform-specific dimensions. Handles timeouts per asset type.

    Returns:
        RenderResult with success=True and url on success, or error details
        on failure.
    """
    try:
        import httpx
    except ImportError:  # pragma: no cover
        return RenderResult(
            success=False,
            error="httpx not installed — cannot reach Renderizador",
        )

    specs = PLATFORM_SPECS.get(request.target_platform)
    if not specs:
        return RenderResult(
            success=False,
            error=f"Unknown platform: {request.target_platform}",
        )

    output_format = "mp4" if request.type == "video" else "png"
    duration = min(MAX_VIDEO_DURATION, 30) if request.type == "video" else None

    render_req = RenderRequest(
        html=request.template_html,
        width=specs["width"],
        height=specs["height"],
        output_format=output_format,
        duration=duration,
    )

    timeout = RENDER_TIMEOUTS.get(request.type, 30)

    # Retry up to 2 additional attempts (3 total)
    max_attempts = 3
    last_error: str | None = None

    for attempt in range(max_attempts):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{RENDERER_BASE_URL}/render",
                    json={
                        "html": render_req.html,
                        "width": render_req.width,
                        "height": render_req.height,
                        "output_format": render_req.output_format,
                        "duration": render_req.duration,
                    },
                )

            if response.status_code == 200:
                data = response.json()
                return RenderResult(
                    success=data.get("success", False),
                    url=data.get("url") or data.get("storage_url"),
                    error=data.get("error"),
                    error_line=data.get("error_line"),
                )
            else:
                last_error = (
                    f"Renderer returned status {response.status_code}: "
                    f"{response.text[:200]}"
                )
        except httpx.TimeoutException:
            last_error = (
                f"Render timeout after {timeout}s "
                f"(attempt {attempt + 1}/{max_attempts})"
            )
        except Exception as exc:  # noqa: BLE001
            last_error = f"Render error (attempt {attempt + 1}): {exc}"

    return RenderResult(success=False, error=last_error)


def build_media_request(
    *,
    media_type: str,
    template_html: str,
    target_platform: str,
    article_id: str,
    tenant_id: str,
    template_id: str | None = None,
) -> MediaRequest:
    """Helper to construct a validated MediaRequest."""
    if media_type not in ("image", "video"):
        raise ValueError(f"media_type must be 'image' or 'video', got: {media_type}")
    if target_platform not in PLATFORM_SPECS:
        raise ValueError(
            f"target_platform must be one of {list(PLATFORM_SPECS.keys())}, "
            f"got: {target_platform}"
        )
    return MediaRequest(
        type=media_type,
        template_html=template_html,
        target_platform=target_platform,
        article_id=article_id,
        tenant_id=tenant_id,
        template_id=template_id,
    )


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------

if LlmAgent is not None:
    produtor_agent = LlmAgent(
        name="produtor_de_midia",
        model=get_model_for_role("producer"),
        instruction=PRODUTOR_PROMPT,
        sub_agents=[],
    )
else:
    produtor_agent = None  # type: ignore[assignment]
