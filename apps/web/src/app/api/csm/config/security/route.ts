/**
 * GET /api/csm/config/security
 *
 * Painel de leitura (não editável via API) com a postura de segurança atual
 * do CSM Studio — usado pela seção "Segurança" em Configurações. Nenhum valor
 * sensível é retornado, só booleans/labels de estado.
 */

import { NextResponse } from 'next/server';
import { isCsmAuthenticated, csmUnauthorized } from '@/lib/csmAuth';
import { cmoAgentUrl, cmoAgentHeaders } from '@/lib/cmoAgent';

function isGcpProduction(): boolean {
  return !!(process.env.GOOGLE_CLOUD_PROJECT || process.env.GCP_PROJECT);
}

export async function GET(request: Request): Promise<Response> {
  if (!isCsmAuthenticated(request)) return csmUnauthorized();

  const nextjs = {
    environment: isGcpProduction() ? 'production' : 'development',
    csmAuthConfigured: !!(process.env.CSM_AUTH_SECRET || process.env.CSM_PASSWORD_HASH),
    cmoInternalAuthConfigured: !!process.env.CMO_INTERNAL_SECRET,
    secretsBackend: isGcpProduction() ? 'GCP Secret Manager' : 'Firestore local (dev)',
  };

  let cmoAgent: Record<string, unknown> | null = null;
  let cmoAgentReachable = false;
  try {
    const res = await fetch(`${cmoAgentUrl()}/health`, {
      headers: cmoAgentHeaders(),
      signal: AbortSignal.timeout(5000),
    });
    if (res.ok) {
      const data = await res.json();
      cmoAgent = data.security ?? null;
      cmoAgentReachable = true;
    }
  } catch {
    /* cmo-agent indisponível — reporta como desconhecido, não bloqueia a tela */
  }

  return NextResponse.json({
    nextjs,
    cmoAgent,
    cmoAgentReachable,
  });
}
