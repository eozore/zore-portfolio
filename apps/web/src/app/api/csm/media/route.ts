/**
 * GET /api/csm/media?src=<gs:// ou https://storage.googleapis.com/...>
 *
 * Serve objetos dos buckets do CSM para a aba de revisão.
 *
 * Por que existe: as imagens das derivações (carrossel, stories, posts) são
 * renderizadas pelo package-job em `vazfy-417019-pipeline-media`, que é um
 * bucket privado com uniform bucket-level access. Um <img src="https://
 * storage.googleapis.com/..."> no navegador recebe 403, então a revisão
 * visual era impossível — o usuário aprovaria 13 imagens sem ver nenhuma.
 *
 * Streaming em vez de redirect para Signed URL: evita depender da permissão
 * de signBlob da service account, não expõe URL assinada no HTML, e deixa o
 * cache sob nosso controle.
 */

import { NextResponse } from 'next/server';
import { Storage } from '@google-cloud/storage';
import { isCsmAuthenticated, csmUnauthorized } from '@/lib/csmAuth';

/**
 * Allowlist de buckets. Sem isto o parâmetro `src` viraria leitura arbitrária
 * de qualquer objeto que a service account do Cloud Run alcança — incluindo
 * buckets de outros projetos e de outras ferramentas.
 */
const ALLOWED_BUCKETS = new Set([
  process.env.GCS_PIPELINE_BUCKET || 'vazfy-417019-pipeline-media',
  process.env.GCP_STORAGE_BUCKET  || 'vazfy-417019-assets',
]);

const CONTENT_TYPES: Record<string, string> = {
  png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg',
  webp: 'image/webp', gif: 'image/gif', mp4: 'video/mp4',
};

/** Extrai {bucket, path} de gs:// ou https://storage.googleapis.com/. */
function parseGcs(src: string): { bucket: string; path: string } | null {
  if (src.startsWith('gs://')) {
    const [bucket, ...rest] = src.slice(5).split('/');
    return rest.length ? { bucket, path: rest.join('/') } : null;
  }
  const match = src.match(/^https:\/\/storage\.googleapis\.com\/([^/]+)\/(.+)$/);
  return match ? { bucket: match[1], path: match[2] } : null;
}

export async function GET(request: Request): Promise<Response> {
  if (!isCsmAuthenticated(request)) return csmUnauthorized();

  const src = new URL(request.url).searchParams.get('src');
  if (!src) return NextResponse.json({ error: 'src required' }, { status: 400 });

  const parsed = parseGcs(src);
  if (!parsed) {
    return NextResponse.json({ error: 'src precisa ser gs:// ou storage.googleapis.com' }, { status: 400 });
  }
  if (!ALLOWED_BUCKETS.has(parsed.bucket)) {
    console.warn(`[csm/media] bucket recusado: ${parsed.bucket}`);
    return NextResponse.json({ error: 'bucket não permitido' }, { status: 403 });
  }
  // Path traversal não faz sentido no GCS (chaves são planas), mas `..` num
  // path indica entrada malformada ou tentativa de abuso — recusa explícita.
  if (parsed.path.includes('..')) {
    return NextResponse.json({ error: 'path inválido' }, { status: 400 });
  }

  try {
    const file = new Storage().bucket(parsed.bucket).file(parsed.path);
    const [exists] = await file.exists();
    if (!exists) return NextResponse.json({ error: 'objeto não encontrado' }, { status: 404 });

    const [buffer] = await file.download();
    const ext = parsed.path.split('.').pop()?.toLowerCase() ?? '';
    return new Response(new Uint8Array(buffer), {
      headers: {
        'Content-Type': CONTENT_TYPES[ext] ?? 'application/octet-stream',
        // Imutável: cada render grava um caminho novo, então o conteúdo de um
        // path nunca muda. Evita rebaixar as mesmas 13 imagens a cada render
        // da grade de revisão.
        'Cache-Control': 'private, max-age=3600, immutable',
      },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error('[csm/media] falha ao servir', parsed.path, message);
    return NextResponse.json({ error: `Falha ao carregar mídia: ${message}` }, { status: 502 });
  }
}
