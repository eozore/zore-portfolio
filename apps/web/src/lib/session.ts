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
    const doc = await db.doc(dbPaths.sessionDoc(sessionId, tenantId)).get();
    if (!doc.exists) return null;
    return doc.data() as CsmSession;
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
 * Saves the active draft state to the session document in Firestore.
 */
export async function saveDraftToSession(
  sessionId: string,
  draft: any,
  tenantId: string | null = null
): Promise<void> {
  const db = getFirestoreDb();
  if (!db) return;

  try {
    await db.doc(dbPaths.sessionDoc(sessionId, tenantId)).set(
      {
        draft,
        updatedAt: Date.now(),
      },
      { merge: true }
    );
  } catch (err) {
    console.error('[session] Failed to save draft to session:', err);
  }
}
