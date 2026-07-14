import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  // Validate session
  const sessionCookie = request.cookies.get('eozore_session')?.value;
  if (!sessionCookie) {
    return NextResponse.json({ error: 'Não autorizado' }, { status: 401 });
  }

  let userSession: any = null;
  try {
    userSession = JSON.parse(decodeURIComponent(sessionCookie));
  } catch (e) {
    return NextResponse.json({ error: 'Sessão inválida' }, { status: 400 });
  }

  const isAuthorized = userSession && (userSession.companyId === 'cromex' || userSession.role === 'admin');
  if (!isAuthorized) {
    return NextResponse.json({ error: 'Acesso negado' }, { status: 403 });
  }

  try {
    const body = await request.json();
    const { peLinear, peBaixa, pp, monthRef } = body;

    // Use environment variable, fallback to localhost:8080
    const pricingApiUrl = process.env.NEXT_PUBLIC_PRICING_API_URL || 'http://localhost:8080';
    console.log(`[CROMEX PROCESS] Enviando requisição para API Python: ${pricingApiUrl}/run-all`);

    const pythonRes = await fetch(`${pricingApiUrl}/run-all`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        pe_linear: parseFloat(peLinear) || 202.0,
        pe_baixa: parseFloat(peBaixa) || 217.0,
        pp: parseFloat(pp) || 184.0,
        month_ref: monthRef || "2026-07"
      })
    });

    if (!pythonRes.ok) {
      const errText = await pythonRes.text();
      console.error(`[CROMEX PROCESS] Erro da API Python: ${errText}`);
      return NextResponse.json({ error: 'Falha no processamento do microserviço' }, { status: 500 });
    }

    const data = await pythonRes.json();
    return NextResponse.json(data);
  } catch (error: any) {
    console.error('Erro ao disparar pipeline Cromex:', error);
    return NextResponse.json({ error: 'Erro ao disparar pipeline' }, { status: 500 });
  }
}
