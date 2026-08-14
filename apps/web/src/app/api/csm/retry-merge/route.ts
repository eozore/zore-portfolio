import { NextRequest, NextResponse } from 'next/server';
import { isCsmAuthenticated, csmUnauthorized } from '@/lib/csmAuth';
import { cmoAgentHeaders } from '@/lib/cmoAgent';

export const dynamic = 'force-dynamic';

export async function POST(req: NextRequest) {
  if (!isCsmAuthenticated(req)) return csmUnauthorized();
  try {
    const body = await req.json();
    const cmoAgentUrl = process.env.CMO_AGENT_URL || 'http://localhost:8090';
    const res = await fetch(`${cmoAgentUrl}/retry-merge`, {
      method: 'POST',
      headers: cmoAgentHeaders(),
      body: JSON.stringify(body),
    });

    const data = await res.json();
    if (!res.ok) {
      return NextResponse.json({ error: data.detail || 'Erro ao chamar retry-merge do Python microservice' }, { status: res.status });
    }

    return NextResponse.json(data);
  } catch (error: any) {
    return NextResponse.json({ error: error.message || 'Erro ao conectar ao retry-merge microservice' }, { status: 500 });
  }
}

export async function GET(req: NextRequest) {
  if (!isCsmAuthenticated(req)) return csmUnauthorized();
  try {
    const { searchParams } = new URL(req.url);
    const jobId = searchParams.get('jobId');

    if (!jobId) {
      return NextResponse.json({ error: 'jobId é obrigatório.' }, { status: 400 });
    }

    const cmoAgentUrl = process.env.CMO_AGENT_URL || 'http://localhost:8090';
    const res = await fetch(`${cmoAgentUrl}/retry-merge?jobId=${jobId}`, { headers: cmoAgentHeaders() });
    const data = await res.json();
    if (!res.ok) {
      return NextResponse.json({ error: data.detail || 'Erro ao consultar status do retry-merge' }, { status: res.status });
    }

    return NextResponse.json(data);
  } catch (error: any) {
    return NextResponse.json({ error: error.message || 'Erro ao conectar ao retry-merge microservice' }, { status: 500 });
  }
}
