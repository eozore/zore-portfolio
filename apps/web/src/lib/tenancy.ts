/**
 * apps/web/src/lib/tenancy.ts
 * ============================
 * Identidade de tenant verificada — a contraparte em Next.js de
 * agents/cmo_agent/tenancy.py e agents/pipeline/shared/tenancy.py.
 *
 * Os três módulos leem o MESMO documento Firestore `tenants/{id}` e o MESMO
 * segredo `TENANT_KEY_PEPPER`, então uma chave emitida para um tenant vale
 * nos três serviços sem sincronização adicional.
 *
 * Regra (idêntica nos três lugares):
 *   - tenantId ausente ou "default" → tenant único implícito (o operador de
 *     hoje), SEM chave exigida. É o comportamento atual, preservado.
 *   - qualquer outro tenantId → precisa de X-Tenant-Key válida, verificada
 *     por HMAC contra `tenants/{id}.key_hash`.
 *
 * Antes deste módulo, toda rota que lia `request.headers.get('x-tenant-id')`
 * confiava nele sem checagem — qualquer chamador autenticado pelo cookie
 * único do CSM podia se declarar dono de qualquer tenant. Sem risco prático
 * enquanto só existe um tenant, mas deixa de ser inofensivo no dia em que um
 * segundo existir.
 */

import { createHmac, timingSafeEqual } from 'node:crypto';
import { getFirestoreDb } from '@/lib/firebase';

export const DEFAULT_TENANT_ID = 'default';
const COLLECTION_TENANTS = 'tenants';

export interface TenantContext {
  tenantId: string;      // 'default' para o operador único
  name: string;
  status: string;
  isDefault: boolean;
}

export type ResolveTenantResult =
  | { ok: true; tenant: TenantContext }
  | { ok: false; status: number; error: string };

function pepper(): string {
  return (process.env.TENANT_KEY_PEPPER || '').trim();
}

/**
 * HMAC-SHA256 salgado pelo tenantId — idêntico ao hash_tenant_key() dos dois
 * módulos Python. Vazar o hash de um tenant não ajuda a forjar a chave de
 * outro, porque o salt é o tenantId, não um valor fixo global.
 */
export function hashTenantKey(tenantId: string, rawKey: string): string {
  const p = pepper();
  if (!p) {
    throw new Error(
      'TENANT_KEY_PEPPER não configurado — necessário para verificar chaves de tenant não-default.',
    );
  }
  return createHmac('sha256', p).update(`${tenantId}:${rawKey}`).digest('hex');
}

function timingSafeEqualHex(a: string, b: string): boolean {
  const bufA = Buffer.from(a, 'hex');
  const bufB = Buffer.from(b, 'hex');
  return bufA.length === bufB.length && timingSafeEqual(bufA, bufB);
}

/**
 * Resolve e verifica a identidade do tenant a partir dos headers da
 * requisição. Não lança — devolve um Result para o chamador decidir o
 * HTTP status (as rotas de API já padronizam NextResponse.json em cada
 * handler, então uma exceção aqui obrigaria try/catch em toda rota).
 */
export async function resolveTenant(request: Request): Promise<ResolveTenantResult> {
  const rawTenantId = request.headers.get('x-tenant-id');
  const tenantKey   = request.headers.get('x-tenant-key');

  const tid = (rawTenantId || '').trim() || DEFAULT_TENANT_ID;

  if (tid === DEFAULT_TENANT_ID) {
    // Comportamento de hoje, preservado: não consulta o Firestore, não exige
    // chave — é o único operador, sem outro tenant para se confundir com.
    return {
      ok: true,
      tenant: { tenantId: DEFAULT_TENANT_ID, name: 'éozoré', status: 'active', isDefault: true },
    };
  }

  const db = getFirestoreDb();
  if (!db) {
    return { ok: false, status: 503, error: 'Firestore indisponível para verificar tenant' };
  }

  const snap = await db.collection(COLLECTION_TENANTS).doc(tid).get();
  if (!snap.exists) {
    return { ok: false, status: 403, error: `Tenant '${tid}' não existe` };
  }

  const data = snap.data() ?? {};
  if (data.status !== 'active') {
    return { ok: false, status: 403, error: `Tenant '${tid}' não está ativo (status=${data.status})` };
  }

  const storedHash = String(data.key_hash || '');
  if (!tenantKey || !storedHash) {
    return { ok: false, status: 403, error: `Tenant '${tid}' exige X-Tenant-Key` };
  }

  let presentedHash: string;
  try {
    presentedHash = hashTenantKey(tid, tenantKey);
  } catch (err) {
    return { ok: false, status: 500, error: err instanceof Error ? err.message : String(err) };
  }

  if (!timingSafeEqualHex(presentedHash, storedHash)) {
    return { ok: false, status: 403, error: `Chave inválida para tenant '${tid}'` };
  }

  return {
    ok: true,
    tenant: {
      tenantId: tid,
      name: String(data.name || tid),
      status: data.status,
      isDefault: false,
    },
  };
}

/**
 * Açúcar para rotas que só precisam do tenantId no formato que dbPaths já
 * espera (`string | null`, null = tenant default / coleções raiz).
 *
 * Devolve `Response` pronta para `return` quando a verificação falha —
 * mantém as rotas de API com uma linha a mais, não um bloco de tratamento.
 */
export async function requireTenantId(
  request: Request,
): Promise<{ tenantId: string | null } | { response: Response }> {
  const result = await resolveTenant(request);
  if (!result.ok) {
    return {
      response: new Response(JSON.stringify({ error: result.error }), {
        status: result.status,
        headers: { 'Content-Type': 'application/json' },
      }),
    };
  }
  return { tenantId: result.tenant.isDefault ? null : result.tenant.tenantId };
}
