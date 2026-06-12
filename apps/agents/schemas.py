"""
Pydantic v2 models for the Agentic Marketing Platform — Python backend.

These models mirror the TypeScript interfaces defined in packages/shared/types.ts
and enforce the validation constraints specified in requirements 4.1 and 4.5
(design.md §Data Models).

All field limits (max_length, max list sizes) match the Firestore document schemas
documented in the design document.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Base Types
# ---------------------------------------------------------------------------

Timestamp = int
"""
Generic timestamp — Unix epoch milliseconds (cross-platform compatible with
Firestore Timestamp on the frontend).
"""

PublishFormat = Literal[
    "blog",
    "linkedin_post",
    "youtube_video",
    "instagram_feed",
    "instagram_reel",
    "instagram_story",
]
"""Supported publishing formats across the platform."""


# ---------------------------------------------------------------------------
# Tenant
# ---------------------------------------------------------------------------


class TenantProfile(BaseModel):
    """
    Profile data for a tenant.

    Validates: Requirement 4.1
    - brandVoice: max 2000 chars
    - niche: max 100 chars
    - persona: max 2000 chars
    - languages: ISO 639-1 codes, max 10 items
    - links: URLs, max 20 items
    """

    brand_voice: str = Field(max_length=2000, alias="brandVoice")
    niche: str = Field(max_length=100)
    persona: str = Field(max_length=2000)
    languages: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)

    @field_validator("languages")
    @classmethod
    def validate_languages_length(cls, v: list[str]) -> list[str]:
        if len(v) > 10:
            raise ValueError("languages list must contain at most 10 items")
        return v

    @field_validator("links")
    @classmethod
    def validate_links_length(cls, v: list[str]) -> list[str]:
        if len(v) > 20:
            raise ValueError("links list must contain at most 20 items")
        return v

    model_config = {"populate_by_name": True}



class Subscription(BaseModel):
    """Subscription info for the tenant (Fase 2 placeholder)."""

    plan: str
    status: str
    stripe_customer_id: str = Field(alias="stripeCustomerId")
    entitlements: dict[str, int] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class TenantDoc(BaseModel):
    """
    Root tenant document stored at tenants/{tenantId}.

    Validates: Requirement 4.1
    """

    tenant_id: str = Field(alias="tenantId")
    name: str
    email: str
    auth_method: Literal["google", "email"] = Field(alias="authMethod")
    created_at: Timestamp = Field(alias="createdAt")
    profile: TenantProfile
    subscription: Subscription

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class FormatToggle(BaseModel):
    """Toggle for auto-publish per format."""

    auto_publish: bool = Field(default=False, alias="autoPublish")

    model_config = {"populate_by_name": True}


class PublishSettings(BaseModel):
    """
    Publishing settings per format.

    Validates: Requirement 4.2 — independent toggle per format.
    """

    publishing: dict[str, FormatToggle]


# ---------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------


class Connection(BaseModel):
    """
    OAuth connection document stored at tenants/{tenantId}/connections/{platform}.

    Validates: Requirement 4.4
    - scopes: max 30 items
    """

    status: Literal["connected", "disconnected", "expired", "revoked"]
    scopes: list[str] = Field(default_factory=list)
    external_account_id: str = Field(alias="externalAccountId")
    secret_ref: str = Field(alias="secretRef")
    expires_at: Optional[Timestamp] = Field(default=None, alias="expiresAt")

    @field_validator("scopes")
    @classmethod
    def validate_scopes_length(cls, v: list[str]) -> list[str]:
        if len(v) > 30:
            raise ValueError("scopes list must contain at most 30 items")
        return v

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Articles
# ---------------------------------------------------------------------------


class Article(BaseModel):
    """
    Article document stored at tenants/{tenantId}/articles/{articleId}.

    Validates: Requirement 4.5
    - title: max 200 chars
    - slug: max 200 chars
    - bodyMarkdown: max 100,000 chars
    - goal (Run): max 500 chars
    """

    title: str = Field(max_length=200)
    slug: str = Field(max_length=200)
    body_markdown: str = Field(max_length=100_000, alias="bodyMarkdown")
    status: Literal["draft", "in_review", "approved", "published", "failed"]
    canonical_url: str = Field(alias="canonicalUrl")
    targets: list[PublishFormat] = Field(default_factory=list)
    review_notes: Optional[str] = Field(default=None, alias="reviewNotes")
    created_by: str = Field(alias="createdBy")
    created_at: Timestamp = Field(alias="createdAt")
    updated_at: Timestamp = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Runs & Events
# ---------------------------------------------------------------------------


class Run(BaseModel):
    """
    Run document stored at tenants/{tenantId}/runs/{runId}.

    Validates: Requirement 4.6
    - goal: max 500 chars
    """

    goal: str = Field(max_length=500)
    status: Literal["queued", "running", "completed", "failed"]
    started_at: Timestamp = Field(alias="startedAt")
    finished_at: Optional[Timestamp] = Field(default=None, alias="finishedAt")

    model_config = {"populate_by_name": True}


class RunEvent(BaseModel):
    """
    Event document stored at tenants/{tenantId}/runs/{runId}/events/{eventId}.

    Validates: Requirement 4.6
    - message: max 5000 chars
    """

    agent: str
    type: str
    message: str = Field(max_length=5000)
    timestamp: Timestamp

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------


class Approval(BaseModel):
    """
    Approval document stored at tenants/{tenantId}/approvals/{approvalId}.

    Validates: Requirement 4.7
    """

    kind: Literal["article", "social_post", "video_script"]
    format: PublishFormat
    payload_ref: str = Field(alias="payloadRef")
    status: Literal["pending", "approved", "rejected"]
    decided_by: Optional[str] = Field(default=None, alias="decidedBy")
    decided_at: Optional[Timestamp] = Field(default=None, alias="decidedAt")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------


class CalendarItem(BaseModel):
    """Calendar item for the content planning schedule."""

    pillar: str
    platform: str
    format: PublishFormat
    planned_for: Timestamp = Field(alias="plannedFor")
    status: Literal[
        "proposed", "approved", "in_progress", "published", "cancelled"
    ]
    linked_article_id: Optional[str] = Field(
        default=None, alias="linkedArticleId"
    )

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------


class ModelUsage(BaseModel):
    """Token usage breakdown per model."""

    input_tokens: int = Field(alias="inputTokens")
    output_tokens: int = Field(alias="outputTokens")

    model_config = {"populate_by_name": True}


class UsageDoc(BaseModel):
    """
    Usage document stored at tenants/{tenantId}/usage/{yyyymm}.

    Tracks token consumption and publishing metrics.
    """

    total_input_tokens: int = Field(alias="totalInputTokens")
    total_output_tokens: int = Field(alias="totalOutputTokens")
    posts_published: int = Field(alias="postsPublished")
    by_platform: dict[str, int] = Field(default_factory=dict, alias="byPlatform")
    by_model: dict[str, ModelUsage] = Field(default_factory=dict, alias="byModel")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


class Template(BaseModel):
    """
    Template document stored at tenants/{tenantId}/templates/{templateId}.

    Validates: Design §Data Models
    - name: max 200 chars
    - htmlCss: max 500,000 chars
    - animationDuration: max 60 seconds
    """

    template_id: str = Field(alias="templateId")
    name: str = Field(max_length=200)
    category: Literal[
        "thumbnail", "feed_post", "reel", "story", "youtube_cover"
    ]
    html_css: str = Field(max_length=500_000, alias="htmlCss")
    width: int
    height: int
    target_platform: PublishFormat = Field(alias="targetPlatform")
    brand_colors: list[str] = Field(default_factory=list, alias="brandColors")
    font_families: list[str] = Field(default_factory=list, alias="fontFamilies")
    has_animation: bool = Field(alias="hasAnimation")
    animation_duration: Optional[int] = Field(
        default=None, alias="animationDuration"
    )
    created_at: Timestamp = Field(alias="createdAt")
    updated_at: Timestamp = Field(alias="updatedAt")
    created_by: str = Field(alias="createdBy")

    @field_validator("animation_duration")
    @classmethod
    def validate_animation_duration(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v > 60:
            raise ValueError("animationDuration must be at most 60 seconds")
        return v

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Content Versioning
# ---------------------------------------------------------------------------


class ContentVersion(BaseModel):
    """
    Version document stored at tenants/{tenantId}/articles/{articleId}/versions/{versionId}.

    Tracks iteration history from LoopAgent and manual edits.
    """

    version: int
    source: Literal["loop_agent", "manual_edit"]
    iteration: Optional[int] = None
    content: str
    created_by: str = Field(alias="createdBy")
    created_at: Timestamp = Field(alias="createdAt")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# SSE & Chat
# ---------------------------------------------------------------------------


class SSEEvent(BaseModel):
    """Server-Sent Event structure for real-time communication."""

    type: Literal["token", "activity", "done", "approval_ready", "error"]
    data: str
    id: Optional[str] = None


class ChatMessage(BaseModel):
    """Chat message exchanged between user and assistant."""

    role: Literal["user", "assistant"]
    content: str
    timestamp: int
    attachments: Optional[list[Deliverable]] = None


class Deliverable(BaseModel):
    """Content deliverable attached to a chat message."""

    kind: Literal["article", "social_post", "video_script", "media_asset"]
    format: PublishFormat
    preview: str
    approval_id: Optional[str] = Field(default=None, alias="approvalId")
    status: Literal["pending", "approved", "published", "failed"]

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Editor
# ---------------------------------------------------------------------------


class EditorState(BaseModel):
    """State of the content editor UI."""

    content_id: str = Field(alias="contentId")
    content_type: Literal["article", "template"] = Field(alias="contentType")
    current_version: int = Field(alias="currentVersion")
    is_dirty: bool = Field(alias="isDirty")
    last_saved_at: Optional[Timestamp] = Field(default=None, alias="lastSavedAt")

    model_config = {"populate_by_name": True}


class PlatformPreview(BaseModel):
    """Preview of content as it would appear on a specific platform."""

    platform: PublishFormat
    char_limit: int = Field(alias="charLimit")
    dimensions: Optional[dict[str, int]] = None
    truncated_content: str = Field(alias="truncatedContent")
    is_within_limits: bool = Field(alias="isWithinLimits")

    model_config = {"populate_by_name": True}
