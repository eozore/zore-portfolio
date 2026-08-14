/**
 * CSM Session Persistence
 *
 * Persists CMO interview chat history in Firestore under the `csm_sessions`
 * collection so the user can resume a conversation across page reloads.
 */

import { getFirestoreDb } from './firebase';
import { dbPaths } from './dbPaths';

export interface SessionMessage {
  role: 'user' | 'model';
  text: string;
  timestamp: number;
}

export interface CsmSession {
  sessionId: string;
  messages: SessionMessage[];
  articleBrief?: string; // Handoff brief gerado no fechamento da pauta
  createdAt: number;
  updatedAt: number;
}

/**
 * Saves (upserts) the full session to Firestore.
 */
export async function saveSession(session: CsmSession, tenantId: string | null = null): Promise<void> {
  const db = getFirestoreDb();
  if (!db) {
    console.warn('[session] Firestore unavailable — session not persisted.');
    return;
  }

  try {
    await db
      .doc(dbPaths.sessionDoc(session.sessionId, tenantId))
      .set(
        {
          ...session,
          updatedAt: Date.now(),
        },
        { merge: true }
      );
  } catch (err) {
    console.error('[session] Failed to save session:', err);
  }
}

/**
 * Loads a session from Firestore by sessionId.
 * Returns null if not found.
 */
export async function loadSession(sessionId: string, tenantId: string | null = null): Promise<CsmSession | null> {
  const db = getFirestoreDb();
  if (!db) return null;

  try {
    const [doc, artifactsDoc] = await Promise.all([
      db.doc(dbPaths.sessionDoc(sessionId, tenantId)).get(),
      db.doc(dbPaths.sessionArtifactsDoc(sessionId, tenantId)).get().catch(() => null),
    ]);
    if (!doc.exists) return null;

    const session = doc.data() as CsmSession & { draft?: Record<string, unknown> };

    // Recompõe os artefatos pesados dentro do draft. Nenhum consumidor
    // (ReviewTab, rotas de package/derivatives) precisa saber que eles moram
    // num doc separado — para quem lê, o draft continua inteiro.
    if (artifactsDoc?.exists && session.draft) {
      const artifacts = artifactsDoc.data() ?? {};
      for (const field of HEAVY_DRAFT_FIELDS) {
        if (artifacts[field] !== undefined && session.draft[field] === undefined) {
          session.draft[field] = artifacts[field];
        }
      }
    }
    return session as CsmSession;
  } catch (err) {
    console.error('[session] Failed to load session:', err);
    return null;
  }
}

/**
 * Appends a single message to an existing session.
 * More efficient than saving the full array when the session is large.
 */
export async function appendMessageToSession(
  sessionId: string,
  message: SessionMessage,
  tenantId: string | null = null
): Promise<void> {
  const db = getFirestoreDb();
  if (!db) return;

  try {
    const ref = db.doc(dbPaths.sessionDoc(sessionId, tenantId));
    const doc = await ref.get();

    if (!doc.exists) {
      // Create new session
      await ref.set({
        sessionId,
        messages: [message],
        createdAt: Date.now(),
        updatedAt: Date.now(),
      });
    } else {
      const current = doc.data() as CsmSession;
      await ref.update({
        messages: [...(current.messages || []), message],
        updatedAt: Date.now(),
      });
    }
  } catch (err) {
    console.error('[session] Failed to append message:', err);
  }
}

/**
 * Saves the article brief generated at the end of the CMO interview.
 */
export async function saveArticleBrief(
  sessionId: string,
  brief: string,
  tenantId: string | null = null
): Promise<void> {
  const db = getFirestoreDb();
  if (!db) return;

  try {
    await db.doc(dbPaths.sessionDoc(sessionId, tenantId)).update({
      articleBrief: brief,
      updatedAt: Date.now(),
    });
  } catch (err) {
    console.error('[session] Failed to save article brief:', err);
  }
}

/**
 * Campos do draft que crescem sem teto e por isso vivem num doc separado.
 *
 * `manifestHtml` é o deck de slides inteiro; com slides reais gerados pelo
 * slide_designer_agent ele passa de centenas de KB. `thumbnails` são dois
 * documentos HTML completos. Mantidos no draft, empurravam a sessão para o
 * limite de 1MB por documento do Firestore — e a escrita falhava em silêncio.
 */
const HEAVY_DRAFT_FIELDS = ['manifestHtml', 'thumbnails'] as const;

/** Margem de segurança abaixo do teto real de 1.048.576 bytes do Firestore. */
const DOC_SIZE_BUDGET_BYTES = 900_000;

function byteSize(value: unknown): number {
  return Buffer.byteLength(JSON.stringify(value ?? null), 'utf8');
}

/** Aponta o campo mais pesado, para o erro dizer o que cortar. */
function heaviestField(obj: Record<string, unknown>): string {
  let name = '(nenhum)';
  let max = 0;
  for (const [key, value] of Object.entries(obj)) {
    const size = byteSize(value);
    if (size > max) { max = size; name = `${key} (${Math.round(max / 1024)}KB)`; }
  }
  return name;
}

/**
 * Saves the active draft state to the session document in Firestore.
 *
 * Diferente da versão anterior, **lança** em caso de falha em vez de logar e
 * seguir. O silêncio aqui era a causa do sintoma "recarreguei a página e perdi
 * tudo": a escrita falhava, a rota respondia `{success:true}`, e o usuário só
 * descobria no reload seguinte.
 */
export async function saveDraftToSession(
  sessionId: string,
  draft: any,
  tenantId: string | null = null
): Promise<void> {
  const db = getFirestoreDb();
  if (!db) throw new Error('Firestore indisponível — draft não foi salvo.');

  // Separa artefatos pesados do corpo do draft.
  const light: Record<string, unknown> = { ...(draft ?? {}) };
  const heavy: Record<string, unknown> = {};
  for (const field of HEAVY_DRAFT_FIELDS) {
    if (light[field] !== undefined) {
      heavy[field] = light[field];
      delete light[field];
    }
  }

  const lightSize = byteSize(light);
  if (lightSize > DOC_SIZE_BUDGET_BYTES) {
    throw new Error(
      `Draft com ${Math.round(lightSize / 1024)}KB excede o limite de 1MB por documento do Firestore. ` +
      `Maior campo: ${heaviestField(light)}.`
    );
  }

  await db.doc(dbPaths.sessionDoc(sessionId, tenantId)).set(
    { draft: light, updatedAt: Date.now() },
    { merge: true }
  );

  if (Object.keys(heavy).length > 0) {
    const heavySize = byteSize(heavy);
    if (heavySize > DOC_SIZE_BUDGET_BYTES) {
      throw new Error(
        `Artefatos do pacote com ${Math.round(heavySize / 1024)}KB excedem o limite de 1MB. ` +
        `Maior: ${heaviestField(heavy)}.`
      );
    }
    await db.doc(dbPaths.sessionArtifactsDoc(sessionId, tenantId)).set(
      { ...heavy, updatedAt: Date.now() },
      { merge: true }
    );
  }
}
