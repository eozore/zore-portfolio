import { NextResponse } from 'next/server';
import { getFirestoreDb } from '@/lib/firebase';
import { dbPaths } from '@/lib/dbPaths';

interface ScheduleItem {
  id?: string;
  platform: 'linkedin' | 'instagram' | 'threads' | 'facebook' | 'youtube';
  format: 'image' | 'carousel' | 'poll' | 'reel' | 'story' | 'video';
  title: string;
  copy: string;
  hashtags?: string[];
  scheduledAt: string; // ISO 8601
  assetUrls?: string[];
  slides?: { heading: string; body: string }[];
  status: 'em_revisao' | 'aprovado' | 'rejeitado';
}

interface SchedulePayload {
  articleSlug: string;
  articleTitle: string;
  items: ScheduleItem[];
}

export async function POST(request: Request): Promise<Response> {
  const db = getFirestoreDb();
  if (!db) {
    return NextResponse.json({ error: 'Firestore database unavailable' }, { status: 500 });
  }

  let body: SchedulePayload;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const { articleSlug, articleTitle, items } = body;
  if (!articleSlug || !items || !Array.isArray(items) || items.length === 0) {
    return NextResponse.json({ error: 'articleSlug and items array required' }, { status: 400 });
  }

  // Filtragem OBRIGATÓRIA: Apenas itens com status === 'aprovado'
  const approvedItems = items.filter((item) => item.status === 'aprovado');

  if (approvedItems.length === 0) {
    return NextResponse.json(
      { error: 'Nenhum conteúdo com status "Aprovado" foi selecionado. Avalie e aprove os cards antes de agendar.' },
      { status: 400 }
    );
  }

  const now = new Date().toISOString();
  const batch = db.batch();
  const tenantId = request.headers.get('x-tenant-id') || null;
  const createdIds: string[] = [];

  for (const item of approvedItems) {
    const docRef = item.id ? db.doc(dbPaths.socialQueueDoc(item.id, tenantId)) : db.collection(dbPaths.socialQueue(tenantId)).doc();
    const id = docRef.id;
    createdIds.push(id);

    let fullCopy = item.copy;
    if (item.format === 'carousel' && item.slides) {
      const slidesCopy = item.slides
        .map((s, idx) => `[Slide ${idx + 1}: ${s.heading}]\n${s.body}`)
        .join('\n\n');
      fullCopy = `${item.copy}\n\n=== SLIDES HTML ===\n\n${slidesCopy}`;
    }

    const docData = {
      id,
      cluster_id: articleSlug,
      platform: item.platform,
      format: item.format,
      archetype: 'educational',
      title: item.title || `${item.platform} post for ${articleSlug}`,
      copy: fullCopy,
      hashtags: item.hashtags || ['#ia', '#machinelearning', '#éozoré'],
      cta: `Confira no site: https://eozore.com/pt-BR/blog/${articleSlug}`,
      asset_urls: item.assetUrls || [],
      image_url: null,
      template_name: item.format === 'carousel' ? 'tech_carousel_v1' : item.format === 'reel' ? 'reel_script_v1' : 'promo_card_v1',
      scheduled_at: item.scheduledAt || now,
      status: 'planned', // status no Firestore para publicação automática pelo robô Python
      topic: articleTitle || articleSlug,
      created_at: now,
      updated_at: now,
      retry_count: 0,
      error_message: null,
      published_at: null,
      platform_post_id: null,
    };

    batch.set(docRef, docData);
  }

  try {
    await batch.commit();
    return NextResponse.json({
      success: true,
      message: `${approvedItems.length} conteúdos aprovados agendados na coleção social_queue com sucesso!`,
      ids: createdIds,
      totalReceived: items.length,
      totalApproved: approvedItems.length,
    });
  } catch (error: unknown) {
    console.error('[csm/schedule v2] Batch commit error:', error);
    const msg = error instanceof Error ? error.message : 'Database commit failed';
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
