import type { Article, ArticleCategory, CreateArticlePayload } from '@/types/article';
import type { Locale } from '@/types/i18n';
import { getFirestoreDb } from './firebase';
import { dbPaths } from './dbPaths';

/**
 * Título → slug de URL: sem acento, sem pontuação, hifenizado, teto de 100
 * caracteres (o limite que `validateArticlePayload` impõe).
 *
 * Vivia copiada em seis componentes do CSM. Fica aqui porque é regra do
 * domínio do artigo, e é daqui que o Studio a consome.
 */
export function slugify(str: string): string {
  return str
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9\s-]/g, '')
    .trim()
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .slice(0, 100);
}

/**
 * Fetches all published articles for a given locale, ordered by publishedAt DESC.
 * Returns empty array if Firestore is unavailable.
 */
export async function getAllArticles(locale: Locale, tenantId: string | null = null): Promise<Article[]> {
  const db = getFirestoreDb();
  if (!db) return [];

  try {
    const snapshot = await db
      .collection(dbPaths.articles(tenantId))
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
 *
 * `incluirRascunho` existe só para quem já está autenticado no Studio. O site
 * público NUNCA passa true.
 *
 * Por que importa: o gate do Studio grava o artigo como `draft` e essa era a
 * única barreira. Mas o filtro de status vivia apenas em `getAllArticles` — o
 * índice escondia o post e a URL direta o servia inteiro, com 200 e 64KB de
 * conteúdo. Ou seja, "rascunho" não escondia de ninguém que tivesse o
 * endereço, e o endereço vai em toda peça social agendada.
 */
export async function getArticleBySlug(
  slug: string,
  locale: Locale,
  tenantId: string | null = null,
  incluirRascunho = false
): Promise<Article | null> {
  const db = getFirestoreDb();
  if (!db) return null;

  try {
    const snapshot = await db
      .collection(dbPaths.articles(tenantId))
      .where('slug', '==', slug)
      .where('language', '==', locale)
      .limit(1)
      .get();

    if (snapshot.empty) return null;

    const doc = snapshot.docs[0];
    const article = { id: doc.id, ...doc.data() } as Article;
    if (!incluirRascunho && article.status !== 'published') return null;
    return article;
  } catch (error) {
    console.error('[articles] Failed to fetch article by slug:', error);
    return null;
  }
}

/**
 * Creates a new article in Firestore.
 * Returns the created article ID or null on failure.
 *
 * `status` defaults to 'published' — o comportamento de sempre, usado pelas
 * rotas de publicação manual. O Studio grava como 'draft': o documento já
 * existe (e portanto a URL do artigo é real, o que as peças sociais precisam
 * para resolver [LINK_ARTIGO]), mas `getAllArticles` filtra por
 * status='published' e o post só aparece no blog quando for promovido.
 */
export async function createArticle(
  payload: CreateArticlePayload,
  tenantId: string | null = null,
  status: 'published' | 'draft' = 'published'
): Promise<string | null> {
  const db = getFirestoreDb();
  if (!db) return null;

  try {
    const docRef = await db.collection(dbPaths.articles(tenantId)).add({
      ...payload,
      status,
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
export async function slugExists(slug: string, locale: Locale, tenantId: string | null = null): Promise<boolean> {
  const db = getFirestoreDb();
  if (!db) return false;

  try {
    const snapshot = await db
      .collection(dbPaths.articles(tenantId))
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
