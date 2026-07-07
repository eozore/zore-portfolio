import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const res = await fetch('http://localhost:8090/merge-video', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    const data = await res.json();
    if (!res.ok) {
      return NextResponse.json({ error: data.detail || 'Erro ao chamar merge-video do Python microservice' }, { status: res.status });
    }

    return NextResponse.json(data);
  } catch (error: any) {
    return NextResponse.json({ error: error.message || 'Erro ao conectar ao merge-video microservice' }, { status: 500 });
  }
}

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const jobId = searchParams.get('jobId');

    if (!jobId) {
      return NextResponse.json({ error: 'jobId é obrigatório.' }, { status: 400 });
    }

    const res = await fetch(`http://localhost:8090/merge-video?jobId=${jobId}`);
    const data = await res.json();
    if (!res.ok) {
      return NextResponse.json({ error: data.detail || 'Erro ao consultar status do merge-video' }, { status: res.status });
    }

    return NextResponse.json(data);
  } catch (error: any) {
    return NextResponse.json({ error: error.message || 'Erro ao conectar ao merge-video microservice' }, { status: 500 });
  }
}
