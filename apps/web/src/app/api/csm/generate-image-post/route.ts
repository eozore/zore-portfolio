import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const cmoAgentUrl = process.env.CMO_AGENT_URL || 'http://localhost:8090';
    const res = await fetch(`${cmoAgentUrl}/generate-image-post`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    const data = await res.json();
    if (!res.ok) {
      return NextResponse.json({ error: data.detail || 'Erro ao chamar generate-image-post do Python microservice' }, { status: res.status });
    }

    return NextResponse.json(data);
  } catch (error: any) {
    return NextResponse.json({ error: error.message || 'Erro ao conectar ao generate-image-post microservice' }, { status: 500 });
  }
}

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const jobId = searchParams.get('jobId');

    if (!jobId) {
      return NextResponse.json({ error: 'jobId é obrigatório.' }, { status: 400 });
    }

    const cmoAgentUrl = process.env.CMO_AGENT_URL || 'http://localhost:8090';
    const res = await fetch(`${cmoAgentUrl}/generate-image-post?jobId=${jobId}`);
    const data = await res.json();
    if (!res.ok) {
      return NextResponse.json({ error: data.detail || 'Erro ao consultar status do generate-image-post' }, { status: res.status });
    }

    return NextResponse.json(data);
  } catch (error: any) {
    return NextResponse.json({ error: error.message || 'Erro ao conectar ao generate-image-post microservice' }, { status: 500 });
  }
}
