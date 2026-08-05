import { NextResponse } from 'next/server';
import { validateArticlePayload } from '@/lib/validation';
import { createArticle, slugExists } from '@/lib/articles';
import { getFirestoreDb } from '@/lib/firebase';
import type { CreateArticlePayload } from '@/types/article';
import { isCsmAuthenticated, csmUnauthorized } from '@/lib/csmAuth';

/**
 * POST /api/csm/publish
 * Internal route for publishing articles from the CSM Tool.
 * Validates payload and writes directly to Firestore (same as /api/articles).
 * Protected by CSM_PASSWORD_HASH env var check via session token.
 */
export async function POST(request: Request): Promise<Response> {
  // Auth check — require same session-level marker
  if (!isCsmAuthenticated(request)) return csmUnauthorized();

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  // Validate using the shared validation library
  const validation = validateArticlePayload(body);
  if (!validation.valid) {
    return NextResponse.json({ errors: validation.errors }, { status: 400 });
  }

  const db = getFirestoreDb();
  if (!db) {
    return NextResponse.json({ error: 'Firestore unavailable' }, { status: 500 });
  }

  const { data } = validation;

  // Check slug uniqueness
  const exists = await slugExists(data.slug, data.language);
  if (exists) {
    return NextResponse.json(
      { error: 'Conflict: slug already exists', slug: data.slug },
      { status: 409 }
    );
  }

  try {
    const docId = await createArticle(data as CreateArticlePayload);
    if (!docId) {
      return NextResponse.json({ error: 'Failed to create article' }, { status: 500 });
    }

    const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || 'https://eozore.com';
    const url = `${baseUrl}/${data.language}/blog/${data.slug}`;

    return NextResponse.json({ slug: data.slug, url, id: docId }, { status: 201 });
  } catch (err) {
    console.error('[csm/publish] Error:', err);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
