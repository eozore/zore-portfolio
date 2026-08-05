/**
 * /api/csm/render-html-image
 *
 * Proxy para o endpoint Python /render-html-image que usa Playwright
 * para converter imageHtml (gerado pelo distribution_agent) em PNG.
 *
 * POST  — inicia o job, retorna { jobId }
 * GET   — poll de status: { status, progress, imageUrl?, error? }
 */
import { NextResponse } from 'next/server';
import { isCsmAuthenticated, csmUnauthorized } from '@/lib/csmAuth';

const CMO_AGENT_URL = process.env.CMO_AGENT_URL || 'http://localhost:8090';

export async function POST(request: Request): Promise<Response> {
  if (!isCsmAuthenticated(request)) return csmUnauthorized();
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  try {
    const res = await fetch(`${CMO_AGENT_URL}/render-html-image`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(15000),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'render-html-image unavailable';
    console.error('[render-html-image] proxy error:', err);
    return NextResponse.json({ error: msg }, { status: 502 });
  }
}

export async function GET(request: Request): Promise<Response> {
  if (!isCsmAuthenticated(request)) return csmUnauthorized();
  const { searchParams } = new URL(request.url);
  const jobId = searchParams.get('jobId');
  if (!jobId) {
    return NextResponse.json({ error: 'jobId required' }, { status: 400 });
  }

  try {
    const res = await fetch(`${CMO_AGENT_URL}/render-html-image?jobId=${encodeURIComponent(jobId)}`, {
      signal: AbortSignal.timeout(10000),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'poll failed';
    return NextResponse.json({ error: msg }, { status: 502 });
  }
}
