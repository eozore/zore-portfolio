/**
 * /api/csm/publish-queue
 *
 * Gerencia a fila de publicação de conteúdo aprovado.
 *
 * Schema Firestore (coleção `publish_queue`):
 * {
 *   id:           string   — gerado automaticamente
 *   sessionId:    string
 *   articleSlug:  string
 *   articleTitle: string
 *   platform:     'linkedin' | 'youtube_community' | 'instagram' | 'threads' | 'youtube_shorts'
 *   format:       'post' | 'reel' | 'shorts' | 'carousel' | 'story' | 'thread' | 'community_post' | 'image_post'
 *   title:        string
 *   copy:         string
 *   imageUrl:     string | null    — URL da imagem gerada (LinkedIn, Instagram)
 *   imageHtml:    string | null    — HTML original para regerar imagem
 *   videoUrl:     string | null    — URL do vídeo (Reels, Shorts)
 *   slides:       object[] | null  — Slides do carrossel
 *   scheduledAt:  string (ISO)
 *   status:       'pending' | 'publishing' | 'published' | 'failed' | 'cancelled'
 *   error:        string | null    — mensagem de erro de token/API
 *   errorCode:    string | null    — código técnico do erro (TOKEN_EXPIRED, RATE_LIMIT, etc.)
 *   attempts:     number           — número de tentativas de publicação
 *   publishedAt:  string | null    — ISO quando foi publicado com sucesso
 *   createdAt:    string (ISO)
 *   updatedAt:    string (ISO)
 * }
 *
 * Endpoints:
 *   POST  /api/csm/publish-queue         — adiciona itens à fila
 *   GET   /api/csm/publish-queue         — lista fila (filtros: status, platform, sessionId)
 *   PATCH /api/csm/publish-queue         — atualiza item (cancelar, retentar, editar copy)
 *   DELETE /api/csm/publish-queue        — remove item da fila
 */

import { NextResponse } from 'next/server';
import { getFirestoreDb } from '@/lib/firebase';
import type { Firestore } from 'firebase-admin/firestore';
import { isCsmAuthenticated, csmUnauthorized } from '@/lib/csmAuth';

// ── Tipos ─────────────────────────────────────────────────────────────────────

export type QueueItemStatus =
  | 'pending'      // aguardando publicação
  | 'publishing'   // em processo de publicação
  | 'published'    // publicado com sucesso
  | 'failed'       // falhou — ver campo error
  | 'cancelled';   // cancelado manualmente pelo usuário

export type QueueItemPlatform =
  | 'linkedin'
  | 'youtube_community'
  | 'instagram'
  | 'threads'
  | 'youtube_shorts';

export type QueueItemFormat =
  | 'post'
  | 'reel'
  | 'shorts'
  | 'carousel'
  | 'story'
  | 'thread'
  | 'community_post'
  | 'image_post';

export interface QueueItem {
  id?: string;
  sessionId: string;
  articleSlug: string;
  articleTitle: string;
  platform: QueueItemPlatform;
  format: QueueItemFormat;
  title: string;
  copy: string;
  imageUrl?: string | null;
  imageHtml?: string | null;
  videoUrl?: string | null;
  slides?: Array<{ slideNumber: number; heading: string; body: string }> | null;
  scheduledAt: string;
  status: QueueItemStatus;
  error?: string | null;
  errorCode?: string | null;
  attempts: number;
  publishedAt?: string | null;
  createdAt: string;
  updatedAt: string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const COLLECTION = 'publish_queue';

function getDb(): Firestore {
  const db = getFirestoreDb();
  if (!db) throw new Error('Firestore unavailable');
  return db;
}

function now(): string {
  return new Date().toISOString();
}

// Mapeia erros de API de plataformas para códigos legíveis
function classifyError(errorMsg: string): string {
  const msg = errorMsg.toLowerCase();
  if (msg.includes('token') && (msg.includes('expired') || msg.includes('invalid'))) return 'TOKEN_EXPIRED';
  if (msg.includes('token') && msg.includes('missing')) return 'TOKEN_MISSING';
  if (msg.includes('rate limit') || msg.includes('too many requests') || msg.includes('429')) return 'RATE_LIMIT';
  if (msg.includes('unauthorized') || msg.includes('401') || msg.includes('403')) return 'UNAUTHORIZED';
  if (msg.includes('network') || msg.includes('econnrefused') || msg.includes('timeout')) return 'NETWORK_ERROR';
  if (msg.includes('quota')) return 'QUOTA_EXCEEDED';
  if (msg.includes('duplicate') || msg.includes('already exists')) return 'DUPLICATE_CONTENT';
  return 'UNKNOWN_ERROR';
}

// ── POST — adiciona itens à fila ──────────────────────────────────────────────

interface AddQueueRequest {
  sessionId: string;
  articleSlug: string;
  articleTitle: string;
  items: Omit<QueueItem, 'id' | 'status' | 'attempts' | 'createdAt' | 'updatedAt'>[];
}

export async function POST(request: Request): Promise<Response> {
  if (!isCsmAuthenticated(request)) return csmUnauthorized();
  let body: AddQueueRequest;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const { sessionId, articleSlug, articleTitle, items } = body;
  if (!items?.length) {
    return NextResponse.json({ error: 'items array required' }, { status: 400 });
  }

  try {
    const db = getDb();
    const ts = now();
    const batch = db.batch();
    const ids: string[] = [];

    for (const item of items) {
      const ref = db.collection(COLLECTION).doc();
      ids.push(ref.id);
      const doc: QueueItem = {
        ...item,
        id: ref.id,
        sessionId: sessionId || item.sessionId,
        articleSlug: articleSlug || item.articleSlug,
        articleTitle: articleTitle || item.articleTitle,
        status: 'pending',
        attempts: 0,
        error: null,
        errorCode: null,
        publishedAt: null,
        createdAt: ts,
        updatedAt: ts,
      };
      batch.set(ref, doc);
    }

    await batch.commit();

    return NextResponse.json({ success: true, ids, count: ids.length }, { status: 201 });
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Failed to add to queue';
    console.error('[publish-queue] POST error:', err);
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}

// ── GET — lista fila ──────────────────────────────────────────────────────────

export async function GET(request: Request): Promise<Response> {
  if (!isCsmAuthenticated(request)) return csmUnauthorized();
  const { searchParams } = new URL(request.url);
  const sessionId  = searchParams.get('sessionId');
  const status     = searchParams.get('status');          // ex: pending,failed
  const platform   = searchParams.get('platform');
  const limitParam = searchParams.get('limit');
  const limit      = limitParam ? parseInt(limitParam, 10) : 100;

  try {
    const db = getDb();
    let query = db.collection(COLLECTION).orderBy('scheduledAt', 'asc') as FirebaseFirestore.Query;

    if (sessionId) query = query.where('sessionId', '==', sessionId);
    if (platform)  query = query.where('platform',  '==', platform);

    // Múltiplos status: status=pending,failed → filtro client-side
    const statusFilter = status ? status.split(',') : null;

    const snap = await query.limit(limit).get();
    let items = snap.docs.map((d) => ({ id: d.id, ...d.data() })) as QueueItem[];

    if (statusFilter) {
      items = items.filter((i) => statusFilter.includes(i.status));
    }

    // Agrupa notificações de erro por plataforma para o banner de alerta do UI
    const errors = items
      .filter((i) => i.status === 'failed')
      .map((i) => ({
        id: i.id,
        platform: i.platform,
        title: i.title,
        errorCode: i.errorCode,
        error: i.error,
        scheduledAt: i.scheduledAt,
      }));

    return NextResponse.json({ items, errors, total: items.length });
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Failed to list queue';
    console.error('[publish-queue] GET error:', err);
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}

// ── PATCH — atualiza item (cancelar, retentar, editar, marcar como falho) ─────

interface PatchQueueRequest {
  id: string;
  action: 'cancel' | 'retry' | 'update' | 'mark_failed';
  copy?: string;
  scheduledAt?: string;
  error?: string;
}

export async function PATCH(request: Request): Promise<Response> {
  if (!isCsmAuthenticated(request)) return csmUnauthorized();
  let body: PatchQueueRequest;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const { id, action, copy, scheduledAt, error: errorMsg } = body;
  if (!id || !action) {
    return NextResponse.json({ error: 'id and action required' }, { status: 400 });
  }

  try {
    const db = getDb();
    const ref = db.collection(COLLECTION).doc(id);
    const snap = await ref.get();

    if (!snap.exists) {
      return NextResponse.json({ error: 'Item not found' }, { status: 404 });
    }

    const ts = now();
    let update: Partial<QueueItem> = { updatedAt: ts };

    switch (action) {
      case 'cancel':
        update.status = 'cancelled';
        break;

      case 'retry':
        update.status = 'pending';
        update.error = null;
        update.errorCode = null;
        break;

      case 'update':
        if (copy !== undefined)        update.copy = copy;
        if (scheduledAt !== undefined) update.scheduledAt = scheduledAt;
        break;

      case 'mark_failed':
        update.status    = 'failed';
        update.error     = errorMsg || 'Marked as failed manually';
        update.errorCode = classifyError(errorMsg || '');
        update.attempts  = (snap.data()?.attempts || 0) + 1;
        break;

      default:
        return NextResponse.json({ error: `Unknown action: ${action}` }, { status: 400 });
    }

    await ref.update(update);
    return NextResponse.json({ success: true, id, action });
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Failed to update item';
    console.error('[publish-queue] PATCH error:', err);
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}

// ── DELETE — remove item da fila ──────────────────────────────────────────────

export async function DELETE(request: Request): Promise<Response> {
  if (!isCsmAuthenticated(request)) return csmUnauthorized();
  const { searchParams } = new URL(request.url);
  const id = searchParams.get('id');

  if (!id) {
    return NextResponse.json({ error: 'id required' }, { status: 400 });
  }

  try {
    const db = getDb();
    await db.collection(COLLECTION).doc(id).delete();
    return NextResponse.json({ success: true, id });
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Failed to delete item';
    console.error('[publish-queue] DELETE error:', err);
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
