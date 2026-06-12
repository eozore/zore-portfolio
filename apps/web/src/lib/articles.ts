import type { Article, ArticleCategory, CreateArticlePayload } from '@/types/article';
import type { Locale } from '@/types/i18n';
import { getFirestoreDb } from './firebase';

const COLLECTION = 'articles';

/**
 * Fetches all published articles for a given locale, ordered by publishedAt DESC.
 * Returns empty array if Firestore is unavailable.
 */
export async function getAllArticles(locale: Locale): Promise<Article[]> {
  const db = getFirestoreDb();
  if (!db) return [];

  try {
    const snapshot = await db
      .collection(COLLECTION)
      .where('language', '==', locale)
      .where('status', '==', 'published')
      .orderBy('publishedAt', 'desc')
      .get();

    return snapshot.docs.map((doc) => ({
      id: doc.id,
      ...doc.data(),
    })) as Article[];
  } catch (error) {
    console.error('[articles] Failed to fetch articles:', error);
    return [];
  }
}

/**
 * Fetches a single article by slug and locale.
 * Returns null if not found or Firestore is unavailable.
 */
export async function getArticleBySlug(
  slug: string,
  locale: Locale
): Promise<Article | null> {
  const db = getFirestoreDb();
  if (!db) return null;

  try {
    const snapshot = await db
      .collection(COLLECTION)
      .where('slug', '==', slug)
      .where('language', '==', locale)
      .limit(1)
      .get();

    if (snapshot.empty) return null;

    const doc = snapshot.docs[0];
    return { id: doc.id, ...doc.data() } as Article;
  } catch (error) {
    console.error('[articles] Failed to fetch article by slug:', error);
    return null;
  }
}

/**
 * Creates a new article in Firestore.
 * Returns the created article ID or null on failure.
 */
export async function createArticle(
  payload: CreateArticlePayload
): Promise<string | null> {
  const db = getFirestoreDb();
  if (!db) return null;

  try {
    const docRef = await db.collection(COLLECTION).add({
      ...payload,
      status: 'published',
      createdAt: new Date().toISOString(),
    });

    return docRef.id;
  } catch (error) {
    console.error('[articles] Failed to create article:', error);
    return null;
  }
}

/**
 * Checks if a slug already exists in Firestore.
 */
export async function slugExists(slug: string, locale: Locale): Promise<boolean> {
  const db = getFirestoreDb();
  if (!db) return false;

  try {
    const snapshot = await db
      .collection(COLLECTION)
      .where('slug', '==', slug)
      .where('language', '==', locale)
      .limit(1)
      .get();

    return !snapshot.empty;
  } catch (error) {
    console.error('[articles] Failed to check slug:', error);
    return false;
  }
}

/**
 * Groups articles by category into named blocks.
 * - Fundação = estatistica
 * - Modelos = ml
 * - IA = ia
 *
 * No article is omitted or duplicated.
 */
export interface ArticleBlock {
  name: string;
  category: ArticleCategory;
  articles: Article[];
}

export function groupByBlock(articles: Article[]): ArticleBlock[] {
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
