import { NextResponse } from 'next/server';
import { validateArticlePayload } from '@/lib/validation';
import { createArticle, slugExists } from '@/lib/articles';
import { getFirestoreDb } from '@/lib/firebase';

export async function POST(request: Request): Promise<Response> {
  // 1. Check Authorization header
  const apiKey = process.env.ARTICLE_API_KEY;
  const authHeader = request.headers.get('authorization');

  if (!apiKey || !authHeader || authHeader !== `Bearer ${apiKey}`) {
    return NextResponse.json(
      { error: 'Unauthorized: invalid or missing API key' },
      { status: 401 }
    );
  }

  // 2. Check Content-Type
  const contentType = request.headers.get('content-type');
  if (!contentType || !contentType.includes('application/json')) {
    return NextResponse.json(
      { error: 'Unsupported Media Type: expected application/json' },
      { status: 415 }
    );
  }

  // 3. Parse body
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error: 'Invalid JSON body' },
      { status: 400 }
    );
  }

  // 4. Validate payload
  const validation = validateArticlePayload(body);
  if (!validation.valid) {
    return NextResponse.json(
      { errors: validation.errors },
      { status: 400 }
    );
  }

  // 5. Check Firestore availability
  const db = getFirestoreDb();
  if (!db) {
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }

  // 6. Check slug uniqueness
  const { data } = validation;
  const exists = await slugExists(data.slug, data.language);
  if (exists) {
    return NextResponse.json(
      { error: 'Conflict: slug already exists', slug: data.slug },
      { status: 409 }
    );
  }

  // 7. Create article
  try {
    const docId = await createArticle(data);
    if (!docId) {
      return NextResponse.json(
        { error: 'Internal server error' },
        { status: 500 }
      );
    }

    const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || 'https://eozore.com';
    const url = `${baseUrl}/${data.language}/blog/${data.slug}`;

    return NextResponse.json(
      { slug: data.slug, url },
      { status: 201 }
    );
  } catch (error) {
    console.error('[api/articles] Failed to create article:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
