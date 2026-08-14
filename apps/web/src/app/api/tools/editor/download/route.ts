import { NextRequest, NextResponse } from 'next/server';
import { Storage } from '@google-cloud/storage';
import fs from 'fs';
import path from 'path';

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const session = searchParams.get('session');
  const file = searchParams.get('file');

  if (!session || !file) {
    return NextResponse.json({ error: 'Parâmetros de download ausentes' }, { status: 400 });
  }

  // 1. Tentar leitura direta do disco local (para desenvolvimento local rápido)
  try {
    const localPath = path.join(process.cwd(), '..', '..', 'tool-videoyoutube', 'downloads', session, file);
    if (fs.existsSync(localPath)) {
      const fileBuffer = fs.readFileSync(localPath);
      return new NextResponse(fileBuffer, {
        headers: {
          'Content-Disposition': `attachment; filename="${file}"`,
          'Content-Type': 'video/mp4',
        },
      });
    }
  } catch (err) {
    console.error('Erro na verificação do arquivo local de vídeo:', err);
  }

  // 2. Fallback local: fazer proxy para a porta 4000 do microserviço
  try {
    const res = await fetch(`http://localhost:4000/download/${session}/${file}`);
    if (res.ok) {
      return new NextResponse(res.body as any, {
        headers: {
          'Content-Disposition': `attachment; filename="${file}"`,
          'Content-Type': 'video/mp4',
        },
      });
    }
  } catch (err) {
    console.error('Falha no proxy de download com porta 4000:', err);
  }

  // 3. Produção/GCP: Baixar via stream do Google Cloud Storage
  try {
    const storage = new Storage();
    const BUCKET_NAME = process.env.EDITOR_BUCKET_NAME || 'ainewz-public';
    const baseName = path.parse(file).name.replace('_final', '');
    
    const bucket = storage.bucket(BUCKET_NAME);
    const [files] = await bucket.getFiles({ prefix: `editor-outputs/${baseName}` });
    
    if (files.length > 0) {
      // Pega o arquivo mais recente gerado para esse vídeo
      const latestFile = files[files.length - 1];
      const stream = latestFile.createReadStream();
      
      return new NextResponse(stream as any, {
        headers: {
          'Content-Disposition': `attachment; filename="${file}"`,
          'Content-Type': 'video/mp4',
        },
      });
    }
  } catch (err) {
    console.error('Falha ao baixar vídeo do GCS:', err);
  }

  return NextResponse.json({ error: 'Vídeo não encontrado ou expirado no storage.' }, { status: 404 });
}
