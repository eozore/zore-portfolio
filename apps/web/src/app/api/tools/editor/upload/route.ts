import { NextRequest, NextResponse } from 'next/server';

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    
    // Proxy para a nova API FastAPI na porta 4000
    const res = await fetch('http://localhost:4000/api/projects', {
      method: 'POST',
      body: formData,
      // @ts-ignore
      duplex: 'half'
    });

    if (!res.ok) {
      const error = await res.text();
      return NextResponse.json(
        { error: `Erro no microserviço de vídeo: ${error}` },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data, { status: 201 });
  } catch (err: any) {
    console.error('Erro no encaminhamento para o microserviço de vídeo (porta 4000):', err);
    return NextResponse.json(
      { error: `Falha ao conectar com o motor de edição de vídeo: ${err.message}` },
      { status: 500 }
    );
  }
}
