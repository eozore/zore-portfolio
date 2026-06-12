import type { MetadataRoute } from 'next';
import { LOCALES } from '@/lib/i18n';
import { getAllArticles } from '@/lib/articles';

const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL || 'https://eozore.com';

// Static pages that exist in every locale
const STATIC_PATHS = ['', '/blog', '/tools'];

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const entries: MetadataRoute.Sitemap = [];

  // Static pages × both locales
  for (const path of STATIC_PATHS) {
    for (const locale of LOCALES) {
      entries.push({
        url: `${BASE_URL}/${locale}${path}`,
        lastModified: new Date(),
        changeFrequency: path === '' ? 'weekly' : 'daily',
        priority: path === '' ? 1 : 0.8,
      });
    }
  }

  // Dynamic article pages from Firestore
  for (const locale of LOCALES) {
    try {
      const articles = await getAllArticles(locale);
      for (const article of articles) {
        entries.push({
          url: `${BASE_URL}/${locale}/blog/${article.slug}`,
          lastModified: new Date(article.publishedAt),
          changeFrequency: 'monthly',
          priority: 0.6,
        });
      }
    } catch (error) {
      console.error(`[sitemap] Failed to fetch articles for ${locale}:`, error);
    }
  }

  return entries;
}
