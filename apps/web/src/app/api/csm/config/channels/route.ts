/**
 * GET/POST /api/csm/config/channels
 *
 * Liga/desliga cada canal (mídia/posicionamento) de distribuição de conteúdo.
 * Um canal desligado:
 *   - some das sub-abas de revisão (ReviewTab)
 *   - tem seus itens zerados na resposta de /api/csm/package e /api/csm/derivatives
 *   - nunca é enfileirado em /api/csm/approve-package, mesmo que o client envie o item
 *
 * Persistência: Firestore, doc único por tenant (`agent_configurations/channels`),
 * mesmo padrão usado pelos prompts de agente — não há segredo aqui, só booleans.
 */

import { NextResponse } from 'next/server';
import { getFirestoreDb } from '@/lib/firebase';
import { dbPaths } from '@/lib/dbPaths';
import { isCsmAuthenticated, csmUnauthorized } from '@/lib/csmAuth';
import { CHANNEL_REGISTRY, CHANNEL_GROUPS, normalizeChannelToggles } from '@/lib/channels';

function channelsDocPath(tenantId: string | null): string {
  // Reaproveita o mesmo namespace de configurações de agente (agent_configurations/channels)
  return dbPaths.configDoc('channels', tenantId);
}

export async function GET(request: Request): Promise<Response> {
  if (!isCsmAuthenticated(request)) return csmUnauthorized();

  const tenantId = request.headers.get('x-tenant-id') || null;
  const db = getFirestoreDb();

  let saved: unknown = null;
  if (db) {
    try {
      const doc = await db.doc(channelsDocPath(tenantId)).get();
      if (doc.exists) saved = doc.data()?.toggles ?? null;
    } catch (err) {
      console.error('[csm/config/channels] GET error:', err);
    }
  }

  const toggles = normalizeChannelToggles(saved);

  return NextResponse.json({
    toggles,
    groups: CHANNEL_GROUPS,
    channels: CHANNEL_REGISTRY.map((c) => ({ ...c, enabled: toggles[c.id] ?? false })),
  });
}

export async function POST(request: Request): Promise<Response> {
  if (!isCsmAuthenticated(request)) return csmUnauthorized();

  let body: { toggles?: Record<string, boolean> };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }
  if (!body.toggles || typeof body.toggles !== 'object') {
    return NextResponse.json({ error: 'toggles (object) required' }, { status: 400 });
  }

  const tenantId = request.headers.get('x-tenant-id') || null;
  const db = getFirestoreDb();
  if (!db) return NextResponse.json({ error: 'Firestore unavailable' }, { status: 500 });

  // Nunca aceita ligar um canal ainda não implementado, mesmo que o client mande true.
  const toggles = normalizeChannelToggles(body.toggles);

  try {
    await db.doc(channelsDocPath(tenantId)).set(
      { toggles, updated_at: new Date().toISOString() },
      { merge: true },
    );
    return NextResponse.json({ success: true, toggles });
  } catch (err: unknown) {
    console.error('[csm/config/channels] POST error:', err);
    const message = err instanceof Error ? err.message : 'Failed to save channels';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
