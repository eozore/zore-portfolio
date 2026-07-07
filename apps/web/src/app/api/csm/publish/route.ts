import { NextResponse } from 'next/server';
import { validateArticlePayload } from '@/lib/validation';
import { createArticle, slugExists } from '@/lib/articles';
import { getFirestoreDb } from '@/lib/firebase';
import type { CreateArticlePayload } from '@/types/article';

/**
 * POST /api/csm/publish
 * Internal route for publishing articles from the CSM Tool.
 * Validates payload and writes directly to Firestore (same as /api/articles).
 * Protected by CSM_PASSWORD_HASH env var check via session token.
 */
export async function POST(request: Request): Promise<Response> {
  // Auth check — require same session-level marker
  const csmSession = request.headers.get('x-csm-session');
  if (csmSession !== 'authenticated') {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

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

    // ── Asynchronous Pub/Sub Campaign Derivation Trigger ──
    const cmoAgentUrl = process.env.CMO_AGENT_URL || 'http://localhost:8090';
    const payload = {
      title: data.title,
      slug: data.slug,
      content: data.content,
      category: data.category,
      language: data.language,
    };

    const base64Data = Buffer.from(JSON.stringify(payload)).toString('base64');
    const pubsubBody = {
      message: {
        data: base64Data,
        messageId: `msg-${Date.now()}`,
      },
    };

    console.log(`[csm/publish] Triggering asynchronous campaign derivation via: ${cmoAgentUrl}/pubsub/subscription`);
    fetch(`${cmoAgentUrl}/pubsub/subscription`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(pubsubBody),
    }).catch((err) => {
      console.error('[csm/publish] Failed to trigger background Pub/Sub subscription repurpose:', err);
    });

    return NextResponse.json({ slug: data.slug, url, id: docId }, { status: 201 });
  } catch (err) {
    console.error('[csm/publish] Error:', err);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
