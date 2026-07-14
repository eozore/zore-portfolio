import { NextRequest, NextResponse } from 'next/server';
import { Storage } from '@google-cloud/storage';
import fs from 'fs';
import path from 'path';

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
    const formData = await request.formData();
    const file = formData.get('file') as File;
    const fileType = formData.get('type') as string; // 'vendas' | 'aderencia_mi' | 'aderencia_me'

    if (!file || !fileType) {
      return NextResponse.json({ error: 'Arquivo ou tipo ausente' }, { status: 400 });
    }

    // Map to standard internal filename
    let standardName = '';
    if (fileType === 'vendas') {
      standardName = 'vendas.xlsx';
    } else if (fileType === 'aderencia_mi') {
      standardName = 'aderencia_mi.xlsx';
    } else if (fileType === 'aderencia_me') {
      standardName = 'aderencia_me.xlsx';
    } else {
      return NextResponse.json({ error: 'Tipo de arquivo inválido' }, { status: 400 });
    }

    const bytes = await file.arrayBuffer();
    const buffer = Buffer.from(bytes);

    const isDev = process.env.NODE_ENV === 'development';
    const hasGcpCreds = !!process.env.GOOGLE_APPLICATION_CREDENTIALS;

    if (isDev || !hasGcpCreds) {
      // Save locally to datainput folder
      const targetDir = path.join(process.cwd(), '..', '..', 'tool-cromex', 'datainput');
      if (!fs.existsSync(targetDir)) {
        fs.mkdirSync(targetDir, { recursive: true });
      }
      const targetPath = path.join(targetDir, standardName);
      fs.writeFileSync(targetPath, buffer);
      console.log(`[CROMEX UPLOAD LOCAL] Salvo em: ${targetPath}`);
    } else {
      // Production GCP: Upload to Cloud Storage
      const storage = new Storage();
      const BUCKET_NAME = process.env.CROMEX_BUCKET_NAME || process.env.GCP_STORAGE_BUCKET || 'zore-portfolio-cromex';
      const blob = storage.bucket(BUCKET_NAME).file(`raw/${standardName}`);
      
      // Save buffer to GCS
      await blob.save(buffer, {
        contentType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        resumable: false
      });
      console.log(`[CROMEX UPLOAD GCS] Enviado para gs://${BUCKET_NAME}/raw/${standardName}`);
    }

    return NextResponse.json({ success: true, filename: standardName });
  } catch (error: any) {
    console.error('Erro no upload de planilha Cromex:', error);
    return NextResponse.json({ error: 'Falha ao salvar arquivo no servidor' }, { status: 500 });
  }
}
