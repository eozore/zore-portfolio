import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import type { Locale } from '@/types/i18n';
import { getArticleBySlug } from '@/lib/articles';
import MarkdownRenderer from '@/components/blog/MarkdownRenderer';

export const revalidate = 60;

interface ArticlePageProps {
  params: { locale: Locale; slug: string };
}

export async function generateMetadata({
  params,
}: {
  params: { locale: Locale; slug: string };
}): Promise<Metadata> {
  const { locale, slug } = params;
  const article = await getArticleBySlug(slug, locale);

  if (!article) {
    return { title: 'Article Not Found' };
  }

  const title = `${article.title} | Victor Zoré`;
  const description = article.content.slice(0, 160).replace(/[#*_`]/g, '');

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      url: `https://eozore.com/${locale}/blog/${slug}`,
      type: 'article',
      publishedTime: article.publishedAt,
      images: [{ url: article.coverImage, width: 1200, height: 630 }],
    },
    twitter: {
      card: 'summary_large_image',
      title,
      description,
      images: [article.coverImage],
    },
    alternates: {
      canonical: `/${locale}/blog/${slug}`,
      languages: {
        'pt-BR': `/pt-BR/blog/${slug}`,
        en: `/en/blog/${slug}`,
        'x-default': `/pt-BR/blog/${slug}`,
      },
    },
  };
}

export default async function ArticlePage({ params }: ArticlePageProps) {
  const { locale, slug } = params;
  const article = await getArticleBySlug(slug, locale);

  if (!article) {
    notFound();
  }

  const date = new Date(article.publishedAt).toLocaleDateString(
    locale === 'pt-BR' ? 'pt-BR' : 'en-US',
    { day: '2-digit', month: 'long', year: 'numeric' }
  );

  const categoryLabels: Record<string, string> = {
    estatistica: 'Estatística',
    ml: 'Machine Learning',
    ia: 'Inteligência Artificial',
  };

  return (
    <article className="py-16">
      <div className="max-w-3xl mx-auto px-4">
        {/* Article Header */}
        <header className="mb-8">
          <span className="inline-block px-3 py-1 text-xs font-semibold rounded bg-primary/10 text-primary mb-4">
            {categoryLabels[article.category] || article.category}
          </span>
          <h1 className="text-3xl md:text-4xl font-bold text-text-main">
            {article.title}
          </h1>
          <div className="mt-4 flex items-center gap-4 text-sm text-text-light">
            <span>{date}</span>
            <span>
              {article.readTime}{' '}
              {locale === 'pt-BR' ? 'min de leitura' : 'min read'}
            </span>
          </div>
        </header>

        {/* Cover Image */}
        {article.coverImage && (
          <div className="mb-8 rounded-card overflow-hidden">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={article.coverImage}
              alt={article.title}
              className="w-full h-auto object-cover"
            />
          </div>
        )}

        {/* Article Content */}
        <MarkdownRenderer content={article.content} />

        {/* Back link */}
        <div className="mt-12 pt-6 border-t border-border">
          <a
            href={`/${locale}/blog`}
            className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:text-primary/80 transition-colors"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10 19l-7-7m0 0l7-7m-7 7h18"
              />
            </svg>
            {locale === 'pt-BR' ? 'Voltar ao blog' : 'Back to blog'}
          </a>
        </div>
      </div>
    </article>
  );
}
