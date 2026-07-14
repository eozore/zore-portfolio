import { NextRequest, NextResponse } from 'next/server';
import { Storage } from '@google-cloud/storage';
import fs from 'fs';
import path from 'path';
import staticDashboardData from '@/data/cromex_dashboard.json';

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

  const useGcs = process.env.NODE_ENV === 'production' || !!process.env.GOOGLE_APPLICATION_CREDENTIALS;

  if (!useGcs) {
    try {
      const localPath = path.join(process.cwd(), '..', '..', 'tool-cromex', 'dataoutput', 'cromex_dashboard.json');
      if (fs.existsSync(localPath)) {
        const fileContent = fs.readFileSync(localPath, 'utf8');
        return NextResponse.json(JSON.parse(fileContent));
      }
    } catch (err) {
      console.warn('[CROMEX DASHBOARD] Erro ao carregar arquivo local:', err);
    }
    return NextResponse.json(staticDashboardData);
  }

  try {
    const storage = new Storage();
    const BUCKET_NAME = process.env.CROMEX_BUCKET_NAME || process.env.GCP_STORAGE_BUCKET || 'zore-portfolio-cromex';
    const file = storage.bucket(BUCKET_NAME).file('processed/cromex_dashboard.json');

    const [exists] = await file.exists();
    if (exists) {
      const [buffer] = await file.download();
      const content = buffer.toString('utf8');
      return NextResponse.json(JSON.parse(content));
    }
  } catch (error: any) {
    console.error('[CROMEX DASHBOARD] Erro ao carregar json do GCS:', error);
  }

  return NextResponse.json(staticDashboardData);
}
