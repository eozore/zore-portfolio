import { NextResponse } from 'next/server';
import { getAllArticles } from '@/lib/articles';
import { isCsmAuthenticated, csmUnauthorized } from '@/lib/csmAuth';

export async function GET(request: Request): Promise<Response> {
  if (!isCsmAuthenticated(request)) return csmUnauthorized();

  const url = new URL(request.url);
  const language = (url.searchParams.get('language') || 'pt-BR') as 'pt-BR' | 'en';
  const tenantId = request.headers.get('x-tenant-id') || null;
  const articles = await getAllArticles(language, tenantId);

  return NextResponse.json({
    articles: articles.map((article) => ({
      id: article.id,
      title: article.title,
      slug: article.slug,
      content: article.content,
      category: article.category,
      language: article.language,
      publishedAt: article.publishedAt,
      coverImage: article.coverImage,
    })),
  });
}
