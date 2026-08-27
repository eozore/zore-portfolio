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

    // `FIRESTORE_DATABASE` existe por causa do emulador, e precisa existir aqui
    // pelo mesmo motivo que existe em agents/cmo_agent/tools.py: o emulador
    // recusa o banco `(default)` para o cliente Python, que manda o nome
    // percent-encoded. A saída foi apontar o Python para um banco `local`.
    //
    // Só que o cliente Node NÃO tem esse defeito — e por isso continuava
    // gravando em `(default)`. O resultado era pior que a falha original: o
    // artigo ia para um banco e o estado do grafo, a social_queue e os agentes
    // para outro. Nenhum erro, dois mundos paralelos, e o ambiente local
    // deixava de validar justamente o contrato entre Node e Python que ele
    // existe para validar.
    //
    // Em produção a variável não é definida e ambos usam `(default)`.
    const databaseId = process.env.FIRESTORE_DATABASE?.trim();
    db = databaseId ? getFirestore(databaseId) : getFirestore();
    return db;
  } catch (error) {
    console.error('[firebase] Failed to initialize:', error);
    return null;
  }
}
