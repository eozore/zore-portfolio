/**
 * cmoAgent.ts — Ponto único de configuração para chamadas Next.js → cmo-agent (Cloud Run).
 *
 * O cmo-agent roda com `--allow-unauthenticated` no Cloud Run (necessário porque o
 * Next.js e o Python são serviços separados sem IAM invoker configurado ainda).
 * Como mitigação, todo request server-side inclui o header `X-Internal-Auth` com um
 * segredo compartilhado (`CMO_INTERNAL_SECRET`, injetado via Secret Manager). O
 * agent.py rejeita qualquer request sem esse header quando o segredo está configurado.
 *
 * Isso NÃO substitui autenticação de usuário (isCsmAuthenticated já protege as rotas
 * do Next.js) — é defesa em profundidade para que o endpoint Python não fique
 * publicamente chamável por qualquer um que descubra a URL do Cloud Run.
 *
 * Recomendação futura mais forte: migrar para IAM invoker (ID tokens assinados via
 * metadata server do Cloud Run) e remover `--allow-unauthenticated`.
 */

export function cmoAgentUrl(): string {
  return process.env.CMO_AGENT_URL || 'http://localhost:8090';
}

export function cmoAgentHeaders(tenantId?: string | null, extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...extra,
  };
  // .trim() é obrigatório: um segredo gravado via `openssl rand | gcloud secrets create`
  // carrega \n final, e valores de header HTTP com newline são rejeitados pelo fetch —
  // o header não chegava e o cmo-agent respondia 401 em todas as chamadas.
  const secret = process.env.CMO_INTERNAL_SECRET?.trim();
  if (secret) headers['X-Internal-Auth'] = secret;
  if (tenantId) headers['X-Tenant-ID'] = tenantId;
  return headers;
}
