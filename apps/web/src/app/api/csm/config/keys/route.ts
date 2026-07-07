import { NextResponse } from 'next/server';
import { getFirestoreDb } from '@/lib/firebase';
import { SecretManagerServiceClient } from '@google-cloud/secret-manager';
import { dbPaths } from '@/lib/dbPaths';
import { encrypt, decrypt } from '@/lib/crypto';

const KEY_MAPPING: Record<string, { label: string; secretName: string }> = {
  HEYGEN_API_KEY: { label: 'HeyGen API Key', secretName: 'heygen-api-key' },
};

// Mask helper to protect keys in the UI
function maskKey(val: string | undefined): string {
  if (!val) return '';
  if (val.length <= 8) return '•'.repeat(val.length);
  return val.slice(0, 4) + '•'.repeat(val.length - 8) + val.slice(-4);
}

// Detect if we should use GCP Secret Manager
function isGcpProduction(): boolean {
  return !!(process.env.GOOGLE_CLOUD_PROJECT || process.env.GCP_PROJECT || process.env.VERCEL);
}

export async function GET(request: Request): Promise<Response> {
  const csmSession = request.headers.get('x-csm-session');
  if (csmSession !== 'authenticated') {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const tenantId = request.headers.get('x-tenant-id') || null;
  const useGcp = isGcpProduction() && !tenantId;
  const projectId = process.env.GOOGLE_CLOUD_PROJECT || process.env.GCP_PROJECT || 'studious-hydra-303815';

  const responseKeys: any[] = [];

  if (useGcp) {
    try {
      const client = new SecretManagerServiceClient();
      for (const [key, meta] of Object.entries(KEY_MAPPING)) {
        try {
          const [version] = await client.accessSecretVersion({
            name: `projects/${projectId}/secrets/${meta.secretName}/versions/latest`,
          });
          const rawValue = version.payload?.data?.toString();
          responseKeys.push({
            name: key,
            label: meta.label,
            maskedValue: maskKey(rawValue),
            isSet: !!rawValue,
          });
        } catch (err: any) {
          // Secret or version might not exist yet
          responseKeys.push({
            name: key,
            label: meta.label,
            maskedValue: '',
            isSet: false,
          });
        }
      }
      return NextResponse.json({ keys: responseKeys, environment: 'production' });
    } catch (err: any) {
      console.warn('[csm/keys] GCP Secret Manager access failed, falling back to local mode:', err.message);
    }
  }

  // Local Dev Fallback (Firestore Local + Env variables)
  const db = getFirestoreDb();
  if (!db) {
    return NextResponse.json({ error: 'Firestore unavailable' }, { status: 500 });
  }

  try {
    const docRef = db.doc(dbPaths.apiKeysDoc(tenantId));
    const doc = await docRef.get();
    const firestoreKeys = doc.exists ? doc.data() || {} : {};

    for (const key of Object.keys(KEY_MAPPING)) {
      // Check Firestore, then check process.env as fallback
      let rawValue = firestoreKeys[key] || process.env[key] || '';
      if (firestoreKeys[key]) {
        rawValue = await decrypt(firestoreKeys[key]);
      }
      responseKeys.push({
        name: key,
        label: KEY_MAPPING[key].label,
        maskedValue: maskKey(rawValue),
        isSet: !!rawValue,
      });
    }

    return NextResponse.json({ keys: responseKeys, environment: tenantId ? 'production-tenant' : 'development' });
  } catch (err: any) {
    console.error('[csm/keys] Local GET error:', err);
    return NextResponse.json({ error: err.message || 'Failed to fetch local keys' }, { status: 500 });
  }
}

export async function POST(request: Request): Promise<Response> {
  const csmSession = request.headers.get('x-csm-session');
  if (csmSession !== 'authenticated') {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  let body: any;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const { keyName, keyValue } = body;

  if (!keyName || !KEY_MAPPING[keyName]) {
    return NextResponse.json({ error: 'Chave inválida ou não suportada.' }, { status: 400 });
  }

  // If the user sent a masked value, it means they did not edit it - skip write
  if (keyValue.includes('•') || keyValue.includes('*')) {
    return NextResponse.json({ success: true, message: 'Nenhuma alteração detectada.' });
  }

  const tenantId = request.headers.get('x-tenant-id') || null;
  const useGcp = isGcpProduction() && !tenantId;
  const projectId = process.env.GOOGLE_CLOUD_PROJECT || process.env.GCP_PROJECT || 'studious-hydra-303815';

  if (useGcp) {
    try {
      const client = new SecretManagerServiceClient();
      const secretName = KEY_MAPPING[keyName].secretName;
      const secretParent = `projects/${projectId}`;
      const secretPath = `${secretParent}/secrets/${secretName}`;

      // 1. Ensure the secret resource exists in GCP, if not, create it
      try {
        await client.getSecret({ name: secretPath });
      } catch (err: any) {
        if (err.code === 5 || err.message.includes('Not Found')) {
          console.info(`[csm/keys] Secret ${secretName} not found. Creating resource...`);
          await client.createSecret({
            parent: secretParent,
            secretId: secretName,
            secret: {
              replication: {
                automatic: {},
              },
            },
          });
        } else {
          throw err;
        }
      }

      // 2. Add a new version with the new value
      await client.addSecretVersion({
        parent: secretPath,
        payload: {
          data: Buffer.from(keyValue, 'utf8'),
        },
      });

      return NextResponse.json({
        success: true,
        message: `Chave ${keyName} gravada com sucesso como nova versão no GCP Secret Manager.`,
      });
    } catch (err: any) {
      console.error('[csm/keys] GCP Secret Manager write failed:', err);
      return NextResponse.json({
        error: `Falha ao salvar no GCP Secret Manager: ${err.message}. Certifique-se de que a conta de serviço possui a role Secret Manager Admin ou Secret Manager Developer.`,
      }, { status: 500 });
    }
  }

  // Local Dev (Firestore Local)
  const db = getFirestoreDb();
  if (!db) {
    return NextResponse.json({ error: 'Firestore unavailable' }, { status: 500 });
  }

  try {
    const encryptedValue = await encrypt(keyValue);
    const docRef = db.doc(dbPaths.apiKeysDoc(tenantId));
    await docRef.set({
      [keyName]: encryptedValue,
      updated_at: new Date().toISOString(),
    }, { merge: true });

    return NextResponse.json({
      success: true,
      message: `Chave ${keyName} gravada no Firestore local com sucesso.`,
    });
  } catch (err: any) {
    console.error('[csm/keys] Local POST error:', err);
    return NextResponse.json({ error: err.message || 'Failed to save local key' }, { status: 500 });
  }
}
