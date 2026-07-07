import { getApps } from 'firebase-admin/app';
import { getFirestoreDb } from './firebase';

export const VERTEX_REGION = 'us-central1';
export const VERTEX_MODEL = 'gemini-2.5-flash';

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

  const res = await fetch(getVertexGenerateEndpoint(projectId), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Vertex AI generateContent error (${res.status}): ${errText}`);
  }

  const data = await res.json();
  const text = data?.candidates?.[0]?.content?.parts?.[0]?.text;
  if (!text) {
    throw new Error('No text returned from Vertex AI candidate');
  }

  return text;
}

