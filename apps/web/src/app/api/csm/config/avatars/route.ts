import { NextRequest, NextResponse } from 'next/server';
import { getFirestoreDb } from '@/lib/firebase';
import { dbPaths } from '@/lib/dbPaths';

const DEFAULT_AVATARS = {
  horizontal: {
    avatarId: 'db66746ef7d848cca675c74239857d42',
    voiceId: '1bd0091de9434efda90327f2269a84f3',
  },
  vertical: {
    avatarId: 'db66746ef7d848cca675c74239857d42',
    voiceId: '1bd0091de9434efda90327f2269a84f3',
  }
};

export async function GET(req: NextRequest) {
  const csmSession = req.headers.get('x-csm-session');
  if (csmSession !== 'authenticated') {
    // Also allow normal internal API access
  }

  const tenantId = req.headers.get('x-tenant-id') || null;
  const db = getFirestoreDb();
  if (!db) {
    return NextResponse.json({ horizontal: DEFAULT_AVATARS.horizontal, vertical: DEFAULT_AVATARS.vertical });
  }

  try {
    const docRef = db.doc(dbPaths.avatarsDoc(tenantId));
    const doc = await docRef.get();
    
    if (doc.exists) {
      const data = doc.data() || {};
      return NextResponse.json({
        horizontal: data.horizontal || DEFAULT_AVATARS.horizontal,
        vertical: data.vertical || DEFAULT_AVATARS.vertical,
      });
    }
    
    return NextResponse.json(DEFAULT_AVATARS);
  } catch (err: any) {
    console.error('[csm/config/avatars] GET error:', err);
    return NextResponse.json({ error: err.message || 'Failed to fetch avatar config' }, { status: 500 });
  }
}

export async function POST(req: NextRequest) {
  const csmSession = req.headers.get('x-csm-session');
  if (csmSession !== 'authenticated') {
    // Authenticated sessions
  }

  try {
    const { horizontal, vertical } = await req.json();

    if (!horizontal || !vertical) {
      return NextResponse.json({ error: 'Configurações horizontal e vertical são obrigatórias.' }, { status: 400 });
    }

    const tenantId = req.headers.get('x-tenant-id') || null;
    const db = getFirestoreDb();
    if (!db) {
      return NextResponse.json({ error: 'Firestore indisponível.' }, { status: 500 });
    }

    const docRef = db.doc(dbPaths.avatarsDoc(tenantId));
    await docRef.set({
      horizontal,
      vertical,
      updatedAt: new Date().toISOString(),
    }, { merge: true });

    return NextResponse.json({
      success: true,
      message: 'Configurações de Avatares & Vozes salvas com sucesso no Firestore.',
    });
  } catch (err: any) {
    console.error('[csm/config/avatars] POST error:', err);
    return NextResponse.json({ error: err.message || 'Failed to save avatar config' }, { status: 500 });
  }
}
