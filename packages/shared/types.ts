/**
 * Shared types for the Agentic Marketing Platform.
 *
 * These types define all Firestore document schemas, SSE event structures,
 * and UI state interfaces used across the Next.js frontend and Python agents.
 */

// ---------------------------------------------------------------------------
// Base Types
// ---------------------------------------------------------------------------

/**
 * Generic timestamp type — compatible with both Firestore Timestamp (frontend)
 * and Unix epoch milliseconds (cross-platform).
 */
export type Timestamp = number;

/**
 * Supported publishing formats across the platform.
 */
export type PublishFormat =
  | 'blog'
  | 'linkedin_post'
  | 'youtube_video'
  | 'instagram_feed'
  | 'instagram_reel'
  | 'instagram_story';

// ---------------------------------------------------------------------------
// Tenant
// ---------------------------------------------------------------------------

export interface TenantProfile {
  brandVoice: string;       // max 2000 chars
  niche: string;            // max 100 chars
  persona: string;          // max 2000 chars
  languages: string[];      // ISO 639-1, max 10
  links: string[];          // URLs, max 20
}

export interface TenantDoc {
  tenantId: string;
  name: string;
  email: string;
  authMethod: 'google' | 'email';
  createdAt: Timestamp;
  profile: TenantProfile;
  subscription: {
    plan: string;
    status: string;
    stripeCustomerId: string;
    entitlements: Record<string, number>;
  };
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

export interface PublishSettings {
  publishing: {
    blog: { autoPublish: boolean };
    linkedin_post: { autoPublish: boolean };
    youtube_video: { autoPublish: boolean };
    instagram_feed: { autoPublish: boolean };
    instagram_reel: { autoPublish: boolean };
    instagram_story: { autoPublish: boolean };
  };
}

// ---------------------------------------------------------------------------
// Connections
// ---------------------------------------------------------------------------

export interface Connection {
  status: 'connected' | 'disconnected' | 'expired' | 'revoked';
  scopes: string[];
  externalAccountId: string;
  secretRef: string;
  expiresAt?: Timestamp;
}

// ---------------------------------------------------------------------------
// Articles
// ---------------------------------------------------------------------------

export interface Article {
  title: string;
  slug: string;
  bodyMarkdown: string;
  status: 'draft' | 'in_review' | 'approved' | 'published' | 'failed';
  canonicalUrl: string;
  targets: PublishFormat[];
  reviewNotes?: string;
  createdBy: string;
  createdAt: Timestamp;
  updatedAt: Timestamp;
}

// ---------------------------------------------------------------------------
// Runs & Events
// ---------------------------------------------------------------------------

export interface Run {
  goal: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  startedAt: Timestamp;
  finishedAt?: Timestamp;
}

export interface RunEvent {
  agent: string;
  type: string;
  message: string;
  timestamp: Timestamp;
}

// ---------------------------------------------------------------------------
// Approvals
// ---------------------------------------------------------------------------

export interface Approval {
  kind: 'article' | 'social_post' | 'video_script';
  format: PublishFormat;
  payloadRef: string;
  status: 'pending' | 'approved' | 'rejected';
  decidedBy?: string;
  decidedAt?: Timestamp;
}

// ---------------------------------------------------------------------------
// Calendar
// ---------------------------------------------------------------------------

export interface CalendarItem {
  pillar: string;
  platform: string;
  format: PublishFormat;
  plannedFor: Timestamp;
  status: 'proposed' | 'approved' | 'in_progress' | 'published' | 'cancelled';
  linkedArticleId?: string;
}

// ---------------------------------------------------------------------------
// Usage
// ---------------------------------------------------------------------------

export interface UsageDoc {
  totalInputTokens: number;
  totalOutputTokens: number;
  postsPublished: number;
  byPlatform: Record<string, number>;
  byModel: Record<string, { inputTokens: number; outputTokens: number }>;
}

// ---------------------------------------------------------------------------
// Templates
// ---------------------------------------------------------------------------

export interface Template {
  templateId: string;
  name: string;
  category: 'thumbnail' | 'feed_post' | 'reel' | 'story' | 'youtube_cover';
  htmlCss: string;
  width: number;
  height: number;
  targetPlatform: PublishFormat;
  brandColors: string[];
  fontFamilies: string[];
  hasAnimation: boolean;
  animationDuration?: number;
  createdAt: Timestamp;
  updatedAt: Timestamp;
  createdBy: string;
}

// ---------------------------------------------------------------------------
// Content Versioning
// ---------------------------------------------------------------------------

export interface ContentVersion {
  version: number;
  source: 'loop_agent' | 'manual_edit';
  iteration?: number;
  content: string;
  createdBy: string;
  createdAt: Timestamp;
}

// ---------------------------------------------------------------------------
// SSE & Chat
// ---------------------------------------------------------------------------

export interface SSEEvent {
  type: 'token' | 'activity' | 'done' | 'approval_ready' | 'error';
  data: string;
  id?: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  attachments?: Deliverable[];
}

export interface Deliverable {
  kind: 'article' | 'social_post' | 'video_script' | 'media_asset';
  format: PublishFormat;
  preview: string;
  approvalId?: string;
  status: 'pending' | 'approved' | 'published' | 'failed';
}

// ---------------------------------------------------------------------------
// Editor
// ---------------------------------------------------------------------------

export interface EditorState {
  contentId: string;
  contentType: 'article' | 'template';
  currentVersion: number;
  isDirty: boolean;
  lastSavedAt: Timestamp | null;
}

export interface PlatformPreview {
  platform: PublishFormat;
  charLimit: number;
  dimensions: { width: number; height: number } | null;
  truncatedContent: string;
  isWithinLimits: boolean;
}
