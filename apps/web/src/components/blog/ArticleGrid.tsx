'use client';

import { useState } from 'react';
import type { Article, ArticleCategory } from '@/types/article';
import type { Locale, Dictionary } from '@/types/i18n';
import ArticleCard from './ArticleCard';
import FilterButtons from './FilterButtons';

// Inline pure groupByBlock to avoid importing from lib/articles (which imports firebase-admin)
interface ArticleBlock {
  name: string;
  category: ArticleCategory;
  articles: Article[];
}

function groupByBlock(articles: Article[]): ArticleBlock[] {
  const blockMap: Record<ArticleCategory, { name: string; articles: Article[] }> = {
    estatistica: { name: 'Fundação', articles: [] },
    ml: { name: 'Modelos', articles: [] },
    ia: { name: 'IA', articles: [] },
  };

  for (const article of articles) {
    const block = blockMap[article.category];
    if (block) {
      block.articles.push(article);
    }
  }

  return Object.entries(blockMap)
    .filter(([, block]) => block.articles.length > 0)
    .map(([category, block]) => ({
      name: block.name,
      category: category as ArticleCategory,
      articles: block.articles,
    }));
}

interface ArticleGridProps {
  articles: Article[];
  locale: Locale;
  dictionary: Dictionary['blog'];
}

export default function ArticleGrid({ articles, locale, dictionary }: ArticleGridProps) {
  const [filter, setFilter] = useState<ArticleCategory | 'all'>('all');

  const filteredArticles =
    filter === 'all'
      ? articles
      : articles.filter((a) => a.category === filter);

  const blocks = groupByBlock(filteredArticles);

  return (
    <>
      <FilterButtons filters={dictionary.filters} onFilterChange={setFilter} />

      {blocks.length === 0 && (
        <p className="text-center text-text-light py-8">
          {locale === 'pt-BR' ? 'Nenhum artigo encontrado.' : 'No articles found.'}
        </p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredArticles.map((article) => (
          <ArticleCard
            key={article.id}
            article={article}
            locale={locale}
            dictionary={dictionary}
          />
        ))}
      </div>
    </>
  );
}
