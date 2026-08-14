/**
 * channelToggles.ts — Leitura server-side dos toggles de canal (Firestore),
 * para uso dentro de rotas que geram ou aprovam conteúdo. Ver `lib/channels.ts`
 * para o registro canônico e `api/csm/config/channels/route.ts` para o CRUD via UI.
 */

import { getFirestoreDb } from '@/lib/firebase';
import { dbPaths } from '@/lib/dbPaths';
import { normalizeChannelToggles, type ChannelToggles } from '@/lib/channels';

export async function getEnabledChannelToggles(tenantId: string | null): Promise<ChannelToggles> {
  const db = getFirestoreDb();
  if (!db) return normalizeChannelToggles(null);

  try {
    const doc = await db.doc(dbPaths.configDoc('channels', tenantId)).get();
    return normalizeChannelToggles(doc.exists ? doc.data()?.toggles : null);
  } catch (err) {
    console.error('[channelToggles] failed to load, using defaults:', err);
    return normalizeChannelToggles(null);
  }
}
