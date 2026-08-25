import { createHmac, timingSafeEqual } from 'node:crypto';

export const CSM_AUTH_COOKIE = 'csm_auth';
const TOKEN_TTL_SECONDS = 8 * 60 * 60;

/**
 * Chave que assina o cookie de sessão.
 *
 * NÃO cai mais para `CSM_PASSWORD_HASH`. O fallback antigo transformava a
 * senha na chave de assinatura: como o token é `HMAC(chave, timestamp)`, quem
 * conhecesse a senha podia calcular o hash, forjar um cookie válido OFFLINE e
 * entrar sem tentar login nenhum — sem passar pela verificação, sem rastro.
 *
 * Em 25/08 isso deixou de ser teórico: o repositório estava público no GitHub
 * com a senha em texto puro num arquivo versionado, e produção rodava sem
 * `CSM_AUTH_SECRET` — só com o hash. A chave de sessão era, na prática,
 * pública.
 *
 * Falha FECHADA: sem a variável, `isCsmAuthenticated` recusa tudo. Um admin
 * inacessível é muito melhor que um admin com chave conhecida.
 */
function authSecret(): string {
  return process.env.CSM_AUTH_SECRET || '';
}

export function createCsmToken(now = Math.floor(Date.now() / 1000)): string {
  const payload = String(now);
  const signature = createHmac('sha256', authSecret()).update(payload).digest('hex');
  return `${payload}.${signature}`;
}

function readCookie(request: Request): string | null {
  const raw = request.headers.get('cookie') || '';
  const pair = raw.split(';').map((item) => item.trim()).find((item) => item.startsWith(`${CSM_AUTH_COOKIE}=`));
  return pair ? decodeURIComponent(pair.slice(CSM_AUTH_COOKIE.length + 1)) : null;
}

export function isCsmAuthenticated(request: Request): boolean {
  const token = readCookie(request);
  if (!token || !authSecret()) return false;

  const [timestamp, signature] = token.split('.');
  const issuedAt = Number(timestamp);
  if (!Number.isInteger(issuedAt) || !signature) return false;
  if (Math.abs(Math.floor(Date.now() / 1000) - issuedAt) > TOKEN_TTL_SECONDS) return false;

  const expected = createHmac('sha256', authSecret()).update(String(issuedAt)).digest('hex');
  const actualBuffer = Buffer.from(signature, 'hex');
  const expectedBuffer = Buffer.from(expected, 'hex');
  return actualBuffer.length === expectedBuffer.length && timingSafeEqual(actualBuffer, expectedBuffer);
}

export function csmUnauthorized(): Response {
  return new Response(JSON.stringify({ error: 'Unauthorized' }), {
    status: 401,
    headers: { 'Content-Type': 'application/json' },
  });
}
