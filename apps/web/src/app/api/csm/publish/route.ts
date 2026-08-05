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

    // ── Disparo assíncrono: geração do pacote de conteúdo completo ──────────
    // Roda em background sem bloquear a resposta ao usuário.
    // O pacote inclui: roteiro, manifesto v2, thumbnails, copies (LinkedIn/Threads).
    // Extrai pauta e sessionId do body original (enviados pelo ArticleTab)
    const bodyRaw = body as Record<string, unknown>;
    const pauta   = bodyRaw.pauta   as Record<string, unknown> | null | undefined;
    const sId     = bodyRaw.sessionId as string | undefined;

    if (pauta?.titulo) {
      // Chamada ao /api/csm/package do próprio Next.js (inclui scriptwriter+thumbnail+copy)
      const host = process.env.NEXTAUTH_URL ||
        (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : 'http://localhost:3000');

      const chatTranscript = (bodyRaw.chatTranscript as string) || `Artigo: ${data.title}`;

      console.log(`[csm/publish] Disparando geração do pacote de conteúdo em background para: ${data.slug}`);
      fetch(`${host}/api/csm/package`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Cookie: request.headers.get('cookie') || '',
          ...(request.headers.get('x-tenant-id')
            ? { 'x-tenant-id': request.headers.get('x-tenant-id') as string }
            : {}),
        },
        body: JSON.stringify({
          pauta,
          chatTranscript,
          category:  data.category,
          language:  data.language,
          sessionId: sId,
          // Passa artigo já gerado para evitar regerar
          articleContent: data.content,
        }),
      }).then(async (pkgRes) => {
        if (pkgRes.ok) {
          console.log(`[csm/publish] Pacote gerado com sucesso para: ${data.slug}`);
        } else {
          const errText = await pkgRes.text().catch(() => pkgRes.statusText);
          console.error(`[csm/publish] Falha ao gerar pacote: ${pkgRes.status} — ${errText.slice(0, 200)}`);
        }
      }).catch((err) => {
        console.error('[csm/publish] Erro ao disparar geração do pacote:', err);
      });
    }

    return NextResponse.json({ slug: data.slug, url, id: docId }, { status: 201 });
  } catch (err) {
    console.error('[csm/publish] Error:', err);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
