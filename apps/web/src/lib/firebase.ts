import { cert, getApps, initializeApp, type ServiceAccount } from 'firebase-admin/app';
import { getFirestore, type Firestore } from 'firebase-admin/firestore';

let db: Firestore | null = null;

/**
 * Initializes and returns the Firestore Admin SDK instance.
 * Returns null if required environment variables are missing (graceful degradation for build time).
 */
export function getFirestoreDb(): Firestore | null {
  if (db) return db;

  const projectId = process.env.FIREBASE_PROJECT_ID;
  const credentialsPath = process.env.GOOGLE_APPLICATION_CREDENTIALS;

  if (!projectId) {
    console.warn('[firebase] FIREBASE_PROJECT_ID not set — Firestore unavailable');
    return null;
  }

  try {
    if (getApps().length === 0) {
      if (credentialsPath) {
        // Use service account key file
        initializeApp({
          credential: cert(credentialsPath as unknown as ServiceAccount),
          projectId,
        });
      } else {
        // Fall back to Application Default Credentials (e.g. on Cloud Run)
        initializeApp({ projectId });
      }
    }

    db = getFirestore();
    return db;
  } catch (error) {
    console.error('[firebase] Failed to initialize:', error);
    return null;
  }
}
