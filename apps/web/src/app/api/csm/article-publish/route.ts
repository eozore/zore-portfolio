/**
 * POST /api/csm/article-publish  { slug, language? }
 *
 * Promove um artigo de `draft` para `published`.
 *
 * O gate do Studio grava o artigo como RASCUNHO: o documento passa a existir —
 * e por isso a URL é real, que é o que as peças sociais precisam para resolver
 * `[LINK_ARTIGO]` — mas `getAllArticles` filtra por `status == 'published'`,
 * então nada aparece no blog. Faltava o outro lado dessa decisão: uma forma de
 * publicar de fato. Sem ela o artigo ficava preso em rascunho, e a semana
 * inteira de posts apontava para uma página que o visitante não via.
 *
 * Idempotente: promover algo já publicado devolve 200 sem escrever.
 */

import { NextResponse } from 'next/server';
import { getFirestoreDb } from '@/lib/firebase';
import { dbPaths } from '@/lib/dbPaths';
import { isCsmAuthenticated, csmUnauthorized } from '@/lib/csmAuth';
import { requireTenantId } from '@/lib/tenancy';

export async function POST(request: Request): Promise<Response> {
  if (!isCsmAuthenticated(request)) return csmUnauthorized();

  const tenant = await requireTenantId(request);
  if ('response' in tenant) return tenant.response;

  let body: { slug?: string; language?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'JSON inválido' }, { status: 400 });
  }

  const slug = String(body.slug || '').trim();
  if (!slug) return NextResponse.json({ error: 'slug obrigatório' }, { status: 400 });
  const language = body.language === 'en' ? 'en' : 'pt-BR';

  const db = getFirestoreDb();
  if (!db) return NextResponse.json({ error: 'Firestore indisponível' }, { status: 503 });

  try {
    const snap = await db
      .collection(dbPaths.articles(tenant.tenantId))
      .where('slug', '==', slug)
      .where('language', '==', language)
      .limit(1)
      .get();

    if (snap.empty) {
      return NextResponse.json(
        { error: `Nenhum artigo com slug '${slug}' em ${language}` },
        { status: 404 },
      );
    }

    const doc = snap.docs[0];
    const jaPublicado = doc.data().status === 'published';

    if (!jaPublicado) {
      await doc.ref.update({
        status: 'published',
        // `publishedAt` é o que ordena o índice do blog. Vale a data em que o
        // artigo REALMENTE foi ao ar, não a da criação do rascunho, que pode
        // ser de dias antes.
        publishedAt: new Date().toISOString(),
      });
    }

    const base = (process.env.NEXT_PUBLIC_BASE_URL || 'https://eozore.com').replace(/\/$/, '');
    return NextResponse.json({
      ok: true,
      jaPublicado,
      slug,
      url: `${base}/${language}/blog/${slug}`,
    });
  } catch (err) {
    console.error('[article-publish] falhou:', err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : String(err) },
      { status: 500 },
    );
  }
}


/**
 * GET /api/csm/article-publish?slug=…&language=…
 *
 * Diz se o artigo já está no ar. A tela precisa saber disso ao recarregar —
 * o estado do grafo guarda a URL, não o status do documento.
 */
export async function GET(request: Request): Promise<Response> {
  if (!isCsmAuthenticated(request)) return csmUnauthorized();

  const tenant = await requireTenantId(request);
  if ('response' in tenant) return tenant.response;

  const params   = new URL(request.url).searchParams;
  const slug     = String(params.get('slug') || '').trim();
  const language = params.get('language') === 'en' ? 'en' : 'pt-BR';
  if (!slug) return NextResponse.json({ error: 'slug obrigatório' }, { status: 400 });

  const db = getFirestoreDb();
  if (!db) return NextResponse.json({ error: 'Firestore indisponível' }, { status: 503 });

  const snap = await db
    .collection(dbPaths.articles(tenant.tenantId))
    .where('slug', '==', slug)
    .where('language', '==', language)
    .limit(1)
    .get()
    .catch(() => null);

  if (!snap || snap.empty) return NextResponse.json({ existe: false, status: null });
  return NextResponse.json({ existe: true, status: snap.docs[0].data().status ?? null });
}
