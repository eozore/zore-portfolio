import { Locale } from './i18n';

export interface Article {
  id: string;
  title: string;           // max 150 chars
  slug: string;            // [a-z0-9-], max 100 chars
  content: string;         // Markdown, max 100,000 chars
  category: ArticleCategory;
  language: Locale;        // 'pt-BR' | 'en'
  publishedAt: string;     // ISO 8601
  readTime: number;        // 1-120 min
  coverImage: string;      // HTTPS URL
  createdAt: string;       // ISO 8601
  status: 'published' | 'draft';
}

export type ArticleCategory = 'estatistica' | 'ml' | 'ia';

export interface CreateArticlePayload {
  title: string;
  slug: string;
  content: string;
  category: ArticleCategory;
  language: 'pt-BR' | 'en';
  publishedAt: string;
  readTime: number;
  coverImage: string;
}
