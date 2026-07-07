import { NextRequest, NextResponse } from 'next/server';
import { Storage } from '@google-cloud/storage';
import fs from 'fs';
import path from 'path';

export async function GET(request: NextRequest) {
  // 1. Valida o cookie de sessão do portfólio
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
  const fileName = searchParams.get('file') || 'input_julho_2026.xlsx';

  // 2. Modo Desenvolvimento Local: lê e envia o arquivo do disco local sem expô-lo no public/
  const isDev = process.env.NODE_ENV === 'development';
  const hasGcpCreds = !!process.env.GOOGLE_APPLICATION_CREDENTIALS;

  if (isDev || !hasGcpCreds) {
    try {
      // Procura primeiro na raiz do projeto local ou no workspace
      let localPath = path.join(process.cwd(), 'public', 'input_julho_2026.xlsx');
      if (!fs.existsSync(localPath)) {
        // Fallback para pasta de desenvolvimento da Cromex
        localPath = path.join(process.cwd(), '..', '..', 'tool-cromex', 'dataoutput', 'input_julho_2026.xlsx');
      }

      if (fs.existsSync(localPath)) {
        const fileBuffer = fs.readFileSync(localPath);
        return new NextResponse(fileBuffer, {
          headers: {
            'Content-Disposition': `attachment; filename="${fileName}"`,
            'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          },
        });
      }
    } catch (err) {
      console.error('Erro no download local:', err);
    }
  }

  // 3. Modo Produção GCP: gera uma Signed URL temporária no Cloud Storage
  try {
    const storage = new Storage();
    const BUCKET_NAME = process.env.CROMEX_BUCKET_NAME || 'zore-portfolio-cromex';
    const filePath = `processed/${fileName}`;

    const [signedUrl] = await storage
      .bucket(BUCKET_NAME)
      .file(filePath)
      .getSignedUrl({
        version: 'v4',
        action: 'read',
        expires: Date.now() + 5 * 60 * 1000, // Link expira em 5 minutos
      });

    return NextResponse.redirect(signedUrl);
  } catch (error: any) {
    console.error('Erro ao gerar URL assinada do GCS:', error);
    return NextResponse.json({ error: 'Erro ao gerar link de download seguro' }, { status: 500 });
  }
}
