import type { CreateArticlePayload, ArticleCategory } from '@/types/article';

export interface ValidationSuccess {
  valid: true;
  data: CreateArticlePayload;
}

export interface ValidationError {
  valid: false;
  errors: Array<{ field: string; reason: string }>;
}

export type ValidationResult = ValidationSuccess | ValidationError;

const VALID_CATEGORIES: ArticleCategory[] = ['estatistica', 'ml', 'ia'];
const VALID_LANGUAGES = ['pt-BR', 'en'] as const;
const SLUG_REGEX = /^[a-z0-9-]+$/;
const ISO_8601_REGEX = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/;

/**
 * Validates an article creation payload.
 * Returns { valid: true, data } if all fields pass constraints,
 * or { valid: false, errors } with a list of field-level errors.
 */
export function validateArticlePayload(body: unknown): ValidationResult {
  const errors: Array<{ field: string; reason: string }> = [];

  if (!body || typeof body !== 'object') {
    return { valid: false, errors: [{ field: 'body', reason: 'must be an object' }] };
  }

  const payload = body as Record<string, unknown>;

  // title
  if (typeof payload.title !== 'string' || payload.title.length === 0) {
    errors.push({ field: 'title', reason: 'must be a non-empty string' });
  } else if (payload.title.length > 150) {
    errors.push({ field: 'title', reason: 'must not exceed 150 characters' });
  }

  // slug
  if (typeof payload.slug !== 'string' || payload.slug.length === 0) {
    errors.push({ field: 'slug', reason: 'must be a non-empty string' });
  } else if (!SLUG_REGEX.test(payload.slug)) {
    errors.push({ field: 'slug', reason: 'must match pattern /^[a-z0-9-]+$/' });
  } else if (payload.slug.length > 100) {
    errors.push({ field: 'slug', reason: 'must not exceed 100 characters' });
  }

  // content
  if (typeof payload.content !== 'string' || payload.content.length === 0) {
    errors.push({ field: 'content', reason: 'must be a non-empty string' });
  } else if (payload.content.length > 100000) {
    errors.push({ field: 'content', reason: 'must not exceed 100000 characters' });
  }

  // category
  if (!VALID_CATEGORIES.includes(payload.category as ArticleCategory)) {
    errors.push({
      field: 'category',
      reason: `must be one of: ${VALID_CATEGORIES.join(', ')}`,
    });
  }

  // language
  if (!VALID_LANGUAGES.includes(payload.language as (typeof VALID_LANGUAGES)[number])) {
    errors.push({ field: 'language', reason: "must be 'pt-BR' or 'en'" });
  }

  // publishedAt
  if (typeof payload.publishedAt !== 'string') {
    errors.push({ field: 'publishedAt', reason: 'must be a string in ISO 8601 format' });
  } else if (!ISO_8601_REGEX.test(payload.publishedAt)) {
    errors.push({ field: 'publishedAt', reason: 'must be a valid ISO 8601 datetime' });
  }

  // readTime
  if (typeof payload.readTime !== 'number') {
    errors.push({ field: 'readTime', reason: 'must be a number' });
  } else if (!Number.isInteger(payload.readTime) || payload.readTime < 1 || payload.readTime > 120) {
    errors.push({ field: 'readTime', reason: 'must be an integer between 1 and 120' });
  }

  // coverImage
  if (typeof payload.coverImage !== 'string') {
    errors.push({ field: 'coverImage', reason: 'must be a string' });
  } else if (!payload.coverImage.startsWith('https://')) {
    errors.push({ field: 'coverImage', reason: 'must start with https://' });
  }

  if (errors.length > 0) {
    return { valid: false, errors };
  }

  return {
    valid: true,
    data: {
      title: payload.title as string,
      slug: payload.slug as string,
      content: payload.content as string,
      category: payload.category as ArticleCategory,
      language: payload.language as 'pt-BR' | 'en',
      publishedAt: payload.publishedAt as string,
      readTime: payload.readTime as number,
      coverImage: payload.coverImage as string,
    },
  };
}
