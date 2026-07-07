import { getFirestoreDb } from './firebase';
import { dbPaths } from './dbPaths';

export interface HistoricalMemory {
  recentArticles: { title: string; slug: string; excerpt: string }[];
  recentSocialHooks: { platform: string; hookOrTitle: string }[];
}

export async function getEcosystemMemory(
  limitArticles = 4,
  limitSocial = 8,
  tenantId: string | null = null
): Promise<HistoricalMemory> {
  const db = getFirestoreDb();
  if (!db) {
    return { recentArticles: [], recentSocialHooks: [] };
  }

  const memory: HistoricalMemory = { recentArticles: [], recentSocialHooks: [] };

  try {
    const artSnapshot = await db
      .collection(dbPaths.articles(tenantId))
      .orderBy('publishedAt', 'desc')
      .limit(limitArticles)
      .get();

    artSnapshot.forEach((doc) => {
      const d = doc.data();
      memory.recentArticles.push({
        title: d.title || doc.id,
        slug: d.slug || doc.id,
        excerpt: d.excerpt || (typeof d.content === 'string' ? d.content.slice(0, 150) : ''),
      });
    });
  } catch (err) {
    console.warn('[retrieval] Error fetching articles memory:', err);
  }

  try {
    const socSnapshot = await db
      .collection(dbPaths.socialQueue(tenantId))
      .orderBy('scheduled_at', 'desc')
      .limit(limitSocial)
      .get();

    socSnapshot.forEach((doc) => {
      const d = doc.data();
      memory.recentSocialHooks.push({
        platform: d.platform || 'linkedin',
        hookOrTitle: d.title || (typeof d.copy === 'string' ? d.copy.slice(0, 60) : ''),
      });
    });
  } catch (err) {
    console.warn('[retrieval] Error fetching social queue memory:', err);
  }

  return memory;
}

export function formatMemoryForPrompt(memory: HistoricalMemory): string {
  if (memory.recentArticles.length === 0 && memory.recentSocialHooks.length === 0) {
    return 'Nenhum histórico prévio registrado no banco.';
  }

  const artText = memory.recentArticles
    .map((a, i) => `${i + 1}) TÍTULO: "${a.title}" (slug: ${a.slug})`)
    .join('\n');

  const socText = memory.recentSocialHooks
    .map((s, i) => `${i + 1}) [${s.platform.toUpperCase()}] "${s.hookOrTitle}"`)
    .join('\n');

  return `=== MEMÓRIA HISTÓRICA DO ECOSSISTEMA ÉOZORÉ ===\n\n[ÚLTIMOS ARTIGOS PUBLICADOS]\n${artText || 'Nenhum'}\n\n[ÚLTIMAS PEÇAS SOCIAIS GERADAS]\n${socText || 'Nenhum'}\n\nINSTRUÇÃO ESPECIAL DE MARKETING: Mantenha a continuidade didática e filosófica com os temas acima, mas NUNCA repita os mesmos ganchos exatos ou analogias superficiais já ensinados prévias.`;
}
