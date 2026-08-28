import { getApps } from 'firebase-admin/app';
import { getFirestoreDb } from './firebase';

export const VERTEX_REGION = 'us-central1';
export const VERTEX_MODEL = 'gemini-3.7-flash';

export function getVertexStreamEndpoint(projectId: string): string {
  return (
    `https://${VERTEX_REGION}-aiplatform.googleapis.com/v1/projects/${projectId}` +
    `/locations/${VERTEX_REGION}/publishers/google/models/${VERTEX_MODEL}:streamGenerateContent?alt=sse`
  );
}

export function getVertexGenerateEndpoint(projectId: string): string {
  return (
    `https://${VERTEX_REGION}-aiplatform.googleapis.com/v1/projects/${projectId}` +
    `/locations/${VERTEX_REGION}/publishers/google/models/${VERTEX_MODEL}:generateContent`
  );
}

/**
 * Gets a Google OAuth2 access token using the Firebase Admin credential (ADC).
 */
export async function getVertexAccessToken(): Promise<string> {
  getFirestoreDb(); // triggers Firebase Admin initialization

  const app = getApps()[0];
  if (!app) {
    throw new Error('Firebase Admin not initialized — check FIREBASE_PROJECT_ID env var');
  }

  const credential = app.options.credential;
  if (!credential) {
    throw new Error('No credential found on Firebase Admin app');
  }

  const tokenResult = await credential.getAccessToken();
  return tokenResult.access_token;
}

export interface GenerateContentOptions {
  prompt: string;
  systemInstruction?: string;
  responseSchema?: Record<string, unknown>;
  temperature?: number;
}

/**
 * Executes a non-streaming structured or text completion against Vertex AI.
 */
export async function generateContent(options: GenerateContentOptions): Promise<string> {
  const projectId = process.env.FIREBASE_PROJECT_ID;
  if (!projectId) {
    throw new Error('FIREBASE_PROJECT_ID not set — required for Vertex AI');
  }

  const accessToken = await getVertexAccessToken();

  const payload: Record<string, unknown> = {
    contents: [
      {
        role: 'user',
        parts: [{ text: options.prompt }],
      },
    ],
    generationConfig: {
      temperature: options.temperature ?? 0.4,
      topP: 0.9,
      maxOutputTokens: 8192,
    },
  };

  if (options.systemInstruction) {
    payload.systemInstruction = {
      parts: [{ text: options.systemInstruction }],
    };
  }

  if (options.responseSchema) {
    (payload.generationConfig as Record<string, unknown>).responseMimeType = 'application/json';
    (payload.generationConfig as Record<string, unknown>).responseSchema = options.responseSchema;
  }

  // 429 (quota momentânea), 500 e 503 são transitórios — retry com backoff
  // exponencial em vez de estourar o erro direto para a UI do chat/derivações.
  const RETRYABLE = new Set([429, 500, 503]);
  const MAX_ATTEMPTS = 4;
  const BASE_BACKOFF_MS = 4_000; // 4s, 8s, 16s — quota por minuto precisa de espera real

  let lastError: Error | null = null;
  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    let res: Response;
    try {
      res = await fetch(getVertexGenerateEndpoint(projectId), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify(payload),
      });
    } catch (err) {
      lastError = new Error(`Vertex AI network error: ${err instanceof Error ? err.message : String(err)}`);
      if (attempt < MAX_ATTEMPTS) {
        await new Promise((r) => setTimeout(r, BASE_BACKOFF_MS * 2 ** (attempt - 1)));
        continue;
      }
      throw lastError;
    }

    if (res.ok) {
      const data = await res.json();
      const text = data?.candidates?.[0]?.content?.parts?.[0]?.text;
      if (!text) {
        throw new Error('No text returned from Vertex AI candidate');
      }
      return text;
    }

    const errText = await res.text();
    lastError = new Error(`Vertex AI generateContent error (${res.status}): ${errText}`);
    if (RETRYABLE.has(res.status) && attempt < MAX_ATTEMPTS) {
      const wait = BASE_BACKOFF_MS * 2 ** (attempt - 1);
      console.warn(`[vertex] HTTP ${res.status} (attempt ${attempt}/${MAX_ATTEMPTS}), retrying in ${wait}ms`);
      await new Promise((r) => setTimeout(r, wait));
      continue;
    }
    throw lastError;
  }

  throw lastError ?? new Error('Vertex AI: exhausted retries');
}

