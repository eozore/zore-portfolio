import { NextResponse } from 'next/server';
import { loadSession, saveDraftToSession } from '@/lib/session';

export async function GET(request: Request): Promise<Response> {
  const { searchParams } = new URL(request.url);
  const sessionId = searchParams.get('id');

  if (!sessionId) {
    return NextResponse.json({ error: 'Missing session ID' }, { status: 400 });
  }

  const tenantId = request.headers.get('x-tenant-id') || null;
  try {
    const session = await loadSession(sessionId, tenantId);
    if (!session) {
      return NextResponse.json({ error: 'Session not found' }, { status: 404 });
    }
    return NextResponse.json(session);
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : 'Failed to load session';
    console.error('[csm/session] GET error:', error);
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}

export async function POST(request: Request): Promise<Response> {
  let body: any;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const { sessionId, draft } = body;

  if (!sessionId || !draft) {
    return NextResponse.json({ error: 'Missing sessionId or draft' }, { status: 400 });
  }

  const tenantId = request.headers.get('x-tenant-id') || null;
  try {
    await saveDraftToSession(sessionId, draft, tenantId);
    return NextResponse.json({ success: true });
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : 'Failed to save draft';
    console.error('[csm/session] POST error:', error);
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
