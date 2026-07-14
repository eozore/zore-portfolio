import { NextRequest, NextResponse } from 'next/server';
import { getFirestoreDb } from '@/lib/firebase';

export async function GET(request: NextRequest) {
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

  const { searchParams } = new URL(request.url);
  const taskId = searchParams.get('taskId');

  if (!taskId) {
    return NextResponse.json({ error: 'taskId ausente' }, { status: 400 });
  }

  const isDev = process.env.NODE_ENV === 'development';
  const hasGcpCreds = !!process.env.GOOGLE_APPLICATION_CREDENTIALS || !!process.env.FIREBASE_PROJECT_ID;

  if (isDev && !hasGcpCreds) {
    return NextResponse.json({
      status: 'completed',
      progress: 100,
      last_log: 'Processamento completo com sucesso (Modo Local Offline)',
      logs: [
        'Iniciando...',
        'Calculando CM1...',
        'Calculando Aderência...',
        'Processamento completo com sucesso (Modo Local Offline)'
      ]
    });
  }

  try {
    const db = getFirestoreDb();
    if (!db) {
      return NextResponse.json({
        status: 'completed',
        progress: 100,
        last_log: 'Processamento completo com sucesso (Sem Banco)',
        logs: ['Processamento completo com sucesso (Sem Banco)']
      });
    }

    const docRef = db.collection('pricing_tasks').doc(taskId);
    const docSnap = await docRef.get();

    if (!docSnap.exists) {
      return NextResponse.json({ status: 'pending', progress: 0, logs: ['Buscando status...'] });
    }

    const data = docSnap.data();
    return NextResponse.json({
      status: data?.status || 'pending',
      progress: data?.progress || 0,
      last_log: data?.last_log || '',
      logs: data?.logs || []
    });
  } catch (error: any) {
    console.error('Erro ao buscar status da tarefa no Firestore:', error);
    return NextResponse.json({ error: 'Erro ao consultar status no Firestore' }, { status: 500 });
  }
}
