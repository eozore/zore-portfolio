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
  const useGcs = process.env.NODE_ENV === 'production' || !!process.env.GOOGLE_APPLICATION_CREDENTIALS;

  if (!useGcs) {
    try {
      // Procura primeiro na raiz do projeto local ou no workspace
      let localPath = path.join(process.cwd(), 'public', fileName);
      if (!fs.existsSync(localPath)) {
        // Fallback para pasta de desenvolvimento da Cromex
        localPath = path.join(process.cwd(), '..', '..', 'tool-cromex', 'dataoutput', fileName);
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

  // 3. Modo Produção GCP: Faz download via stream do Cloud Storage
  try {
    const storage = new Storage();
    const BUCKET_NAME = process.env.CROMEX_BUCKET_NAME || process.env.GCP_STORAGE_BUCKET || 'vazfy-417019-assets';
    const filePath = `processed/${fileName}`;

    const file = storage.bucket(BUCKET_NAME).file(filePath);
    
    // Verifica se o arquivo existe antes de baixar
    const [exists] = await file.exists();
    if (!exists) {
      return NextResponse.json({ error: 'Arquivo não encontrado' }, { status: 404 });
    }

    // Faz o download do arquivo em memória (bom para pequenos relatórios de BI Excel, limitados a algumas dezenas de MB)
    const [buffer] = await file.download();

    return new NextResponse(buffer, {
      headers: {
        'Content-Disposition': `attachment; filename="${fileName}"`,
        'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      },
    });
  } catch (error: any) {
    console.error('Erro ao ler arquivo do GCS:', error);
    return NextResponse.json({ error: 'Erro ao gerar download do arquivo' }, { status: 500 });
  }
}
