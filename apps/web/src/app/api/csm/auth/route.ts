import { NextResponse } from 'next/server';

/**
 * POST /api/csm/auth
 * Validates the SHA-256 hash of the CSM password.
 * Body: { hash: string }
 */
export async function POST(request: Request): Promise<Response> {
  try {
    const body = await request.json();
    const { hash } = body as { hash: string };

    if (!hash || typeof hash !== 'string') {
      return NextResponse.json({ error: 'Bad request' }, { status: 400 });
    }

    const expectedHash = process.env.CSM_PASSWORD_HASH;
    if (!expectedHash) {
      console.error('[csm/auth] CSM_PASSWORD_HASH env var not set');
      return NextResponse.json({ error: 'Server configuration error' }, { status: 500 });
    }

    if (hash.toLowerCase() !== expectedHash.toLowerCase()) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    return NextResponse.json({ ok: true }, { status: 200 });
  } catch {
    return NextResponse.json({ error: 'Bad request' }, { status: 400 });
  }
}
