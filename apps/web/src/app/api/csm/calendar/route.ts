/**
 * /api/csm/calendar
 *
 * GET  ?from=ISO&to=ISO&sessionId=...
 *   → Lista todos os CalendarItem do período combinando:
 *     - social_queue (LinkedIn, Threads, Reels, Shorts, Carrosséis…)
 *     - content_projects (YouTube longo, pipeline TTS→Avatar→Editor)
 *
 * PUT  body: { id, collection, updates: { scheduled_at?, copy?, hashtags?, title? } }
 *   → Atualiza campos editáveis de um item.
 *     Não permite alterar video_url, image_url, asset_urls (mídia já produzida).
 */

import { NextResponse } from 'next/server';
import { getFirestoreDb } from '@/lib/firebase';
import { isCsmAuthenticated, csmUnauthorized } from '@/lib/csmAuth';
import { dbPaths } from '@/lib/dbPaths';

// ── Tipos exportados (consumidos pelo CalendarTab) ────────────────────────────

export type CalendarItemStatus =
  | 'planned'         // agendado, aguardando publisher-scheduled
  | 'published'       // publicado com sucesso
  | 'failed'          // falhou na publicação
  | 'generating_media' // vídeo ainda em pipeline
  | 'awaiting_publication'
  | 'archived';

export type CalendarPlatform =
  | 'linkedin' | 'instagram' | 'threads' | 'facebook'
  | 'youtube'  | 'youtube_community' | 'youtube_shorts';

export interface CalendarItem {
  id:           string;
  collection:   'social_queue' | 'content_projects';
  platform:     CalendarPlatform;
  format:       string;        // text | reel | shorts | video | carousel | image | thread
  title:        string;
  copy:         string;
  hashtags:     string[];
  scheduled_at: string;        // ISO 8601
  status:       CalendarItemStatus;
  /** URL de prévia (imagem de capa, thumbnail ou frame do vídeo) */
  preview_url?: string;
  /** URL do vídeo final (imutável após geração) */
  video_url?:   string;
  /** Se true, copy/hashtags/scheduled_at podem ser editados */
  editable:     boolean;
  article_slug?: string;
  article_title?: string;
  /** Estágios do pipeline de vídeo (só para content_projects) */
  pipeline_stages?: Record<string, { status: string }>;
}

// ── Campos que NÃO podem ser alterados via API ────────────────────────────────
const IMMUTABLE_FIELDS = new Set([
  'video_url', 'image_url', 'asset_urls', 'platform_post_id',
  'id', 'collection', 'created_at', 'published_at',
]);

// ── Helpers ───────────────────────────────────────────────────────────────────

function toCalendarItem(
  doc: FirebaseFirestore.DocumentSnapshot,
  collection: 'social_queue' | 'content_projects',
): CalendarItem | null {
  const d = doc.data();
  if (!d) return null;

  if (collection === 'social_queue') {
    const scheduled = d.scheduled_at || d.scheduledAt || '';
    return {
      id:           doc.id,
      collection:   'social_queue',
      platform:     (d.platform as CalendarPlatform) || 'linkedin',
      format:       d.format || 'text',
      title:        d.title || d.copy?.slice(0, 80) || '',
      copy:         d.copy || '',
      hashtags:     Array.isArray(d.hashtags) ? d.hashtags : [],
      scheduled_at: scheduled,
      status:       (d.status as CalendarItemStatus) || 'planned',
      preview_url:  d.image_url || undefined,
      video_url:    d.video_url || undefined,
      editable:     d.status !== 'published' && d.status !== 'archived',
      article_slug: d.article_slug || d.cluster_id,
      article_title: d.article_title || d.topic,
    };
  }

  // content_projects — pipeline de vídeo
  const scheduled = d.scheduled_at || d.created_at || '';
  return {
    id:           doc.id,
    collection:   'content_projects',
    platform:     'youtube',
    format:       'video',
    title:        d.title || '',
    copy:         '',
    hashtags:     [],
    scheduled_at: scheduled,
    status:       (d.status as CalendarItemStatus) || 'generating_media',
    preview_url:  d.thumbnail_url || undefined,
    video_url:    d.stages?.editor?.horizontal_url || undefined,
    editable:     !['published', 'archived'].includes(d.status),
    article_slug: d.article_slug,
    article_title: d.title,
    pipeline_stages: d.stages,
  };
}

function isInRange(isoDate: string, from: Date, to: Date): boolean {
  if (!isoDate) return false;
  try {
    const d = new Date(isoDate);
    return d >= from && d <= to;
  } catch {
    return false;
  }
}

// ── GET ───────────────────────────────────────────────────────────────────────

export async function GET(request: Request): Promise<Response> {
  if (!isCsmAuthenticated(request)) return csmUnauthorized();
  const db = getFirestoreDb();
  if (!db) return NextResponse.json({ error: 'Firestore unavailable' }, { status: 500 });

  const url  = new URL(request.url);
  const from = url.searchParams.get('from');
  const to   = url.searchParams.get('to');
  const tenantId = request.headers.get('x-tenant-id') || null;

  // Default: semana atual
  const fromDate = from ? new Date(from) : (() => {
    const d = new Date(); d.setHours(0, 0, 0, 0);
    d.setDate(d.getDate() - d.getDay()); return d;
  })();
  const toDate = to ? new Date(to) : (() => {
    const d = new Date(fromDate); d.setDate(d.getDate() + 90); // 90 dias forward
    return d;
  })();

  try {
    const [sqSnap, cpSnap] = await Promise.all([
      // social_queue: lê todos não-arquivados num batch generoso
      db.collection(dbPaths.socialQueue(tenantId))
        .where('status', 'not-in', ['archived'])
        .limit(500)
        .get(),
      // content_projects: projetos com status ativo
      db.collection(dbPaths.contentProjects(tenantId))
        .where('status', 'not-in', ['archived'])
        .limit(100)
        .get(),
    ]);

    const items: CalendarItem[] = [];

    sqSnap.docs.forEach((doc) => {
      const item = toCalendarItem(doc, 'social_queue');
      if (item && isInRange(item.scheduled_at, fromDate, toDate)) {
        items.push(item);
      }
    });

    cpSnap.docs.forEach((doc) => {
      const item = toCalendarItem(doc, 'content_projects');
      if (item) items.push(item); // sempre inclui projetos de vídeo
    });

    // Ordena por scheduled_at asc
    items.sort((a, b) => {
      if (!a.scheduled_at) return 1;
      if (!b.scheduled_at) return -1;
      return new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime();
    });

    return NextResponse.json({ items, from: fromDate.toISOString(), to: toDate.toISOString() });
  } catch (err) {
    console.error('[calendar] GET error:', err);
    return NextResponse.json({ error: (err as Error).message }, { status: 500 });
  }
}

// ── PUT ───────────────────────────────────────────────────────────────────────

export async function PUT(request: Request): Promise<Response> {
  if (!isCsmAuthenticated(request)) return csmUnauthorized();
  const db = getFirestoreDb();
  if (!db) return NextResponse.json({ error: 'Firestore unavailable' }, { status: 500 });

  let body: { id: string; collection: 'social_queue' | 'content_projects'; updates: Record<string, unknown> };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 });
  }

  const { id, collection, updates } = body;
  const tenantId = request.headers.get('x-tenant-id') || null;
  if (!id || !collection || !updates) {
    return NextResponse.json({ error: 'id, collection and updates required' }, { status: 400 });
  }

  // Filtra campos imutáveis
  const safeUpdates: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(updates)) {
    if (!IMMUTABLE_FIELDS.has(key)) {
      safeUpdates[key] = value;
    }
  }

  if (!Object.keys(safeUpdates).length) {
    return NextResponse.json({ error: 'No editable fields in updates' }, { status: 400 });
  }

  safeUpdates['updated_at'] = new Date().toISOString();

  try {
    const collectionPath = collection === 'social_queue'
      ? dbPaths.socialQueue(tenantId)
      : dbPaths.contentProjects(tenantId);
    const ref = db.collection(collectionPath).doc(id);
    const snap = await ref.get();
    if (!snap.exists) {
      return NextResponse.json({ error: `Document ${id} not found in ${collection}` }, { status: 404 });
    }

    const data = snap.data()!;
    if (['published', 'archived'].includes(data.status)) {
      return NextResponse.json(
        { error: `Cannot edit item with status="${data.status}"` },
        { status: 409 },
      );
    }

    await ref.update(safeUpdates);
    const updated = await ref.get();
    const item = toCalendarItem(updated, collection as 'social_queue' | 'content_projects');

    return NextResponse.json({ success: true, item });
  } catch (err) {
    console.error('[calendar] PUT error:', err);
    return NextResponse.json({ error: (err as Error).message }, { status: 500 });
  }
}
