import type { Metadata } from 'next';
import type { Locale } from '@/types/i18n';
import type { Article } from '@/types/article';
import { getDictionary } from '@/lib/i18n';
import { getAllArticles } from '@/lib/articles';
import ArticleGrid from '@/components/blog/ArticleGrid';

export const revalidate = 60;

interface BlogPageProps {
  params: { locale: Locale };
}

// Static fallback data when Firestore is unavailable
const staticFallbackArticles: Article[] = [
  {
    id: 'static-1',
    title: 'Variáveis Aleatórias',
    slug: 'exemplo',
    content: 'X: Ω → ℝ',
    category: 'estatistica',
    language: 'pt-BR',
    publishedAt: '2025-06-01T00:00:00Z',
    readTime: 12,
    coverImage: '',
    createdAt: '2025-06-01T00:00:00Z',
    status: 'published',
  },
];

export async function generateMetadata({
  params,
}: {
  params: { locale: Locale };
}): Promise<Metadata> {
  const { locale } = params;

  const title = locale === 'pt-BR' ? 'Blog | Victor Zoré' : 'Blog | Victor Zoré';
  const description =
    locale === 'pt-BR'
      ? 'Artigos sobre estatística, machine learning e inteligência artificial.'
      : 'Articles about statistics, machine learning, and artificial intelligence.';

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      url: `https://eozore.com/${locale}/blog`,
      type: 'website',
    },
    twitter: {
      card: 'summary',
      title,
      description,
    },
    alternates: {
      canonical: `/${locale}/blog`,
      languages: {
        'pt-BR': '/pt-BR/blog',
        en: '/en/blog',
        'x-default': '/pt-BR/blog',
      },
    },
  };
}

export default async function BlogPage({ params }: BlogPageProps) {
  const { locale } = params;
  const dictionary = getDictionary(locale);

  // Fetch articles from Firestore; fall back to static data if unavailable
  let articles = await getAllArticles(locale);
  if (articles.length === 0) {
    articles = staticFallbackArticles.filter((a) => a.language === locale || locale === 'pt-BR');
  }

  return (
    <section className="py-16">
      <div className="max-w-container mx-auto px-4">
        {/* Section Header */}
        <div className="text-center mb-10">
          <h1 className="text-2xl md:text-3xl font-bold text-text-main">
            {dictionary.blog.title}
          </h1>
          <p className="mt-2 text-text-light">{dictionary.blog.subtitle}</p>
        </div>

        {/* Articles Grid with Client-side Filtering */}
        <ArticleGrid articles={articles} locale={locale} dictionary={dictionary.blog} />
      </div>
    </section>
  );
}
