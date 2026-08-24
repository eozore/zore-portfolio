/**
 * POST /api/csm/pipeline-submit
 *
 * Casca HTTP. A lógica está em `@/lib/pipelineSubmit` porque o gate do vídeo
 * no Studio precisa dispará-la EM PROCESSO — a versão anterior fazia um
 * self-fetch para esta rota, e dentro do Cloud Run ele resolvia para o
 * localhost do container: sem log, sem rastro, e a falha era engolida.
 */

import { NextResponse } from 'next/server';
import { isCsmAuthenticated, csmUnauthorized } from '@/lib/csmAuth';
import { requireTenantId } from '@/lib/tenancy';
import {
  executarSubmit,
  SubmitInvalidoError,
  type SubmitRequest,
} from '@/lib/pipelineSubmit';

export const maxDuration = 300;

/** Handler HTTP: autentica, resolve tenant e delega para executarSubmit. */
export async function POST(request: Request): Promise<Response> {
  if (!isCsmAuthenticated(request)) return csmUnauthorized();

  let body: SubmitRequest;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  // Identidade de tenant VERIFICADA — não `request.headers.get('x-tenant-id')`
  // direto. Esta é a rota que dispara gasto real (HeyGen/ElevenLabs via
  // Pub/Sub), então é o ponto de maior risco de um tenant se declarar dono de
  // outro. Ver apps/web/src/lib/tenancy.ts.
  const tenantResolution = await requireTenantId(request);
  if ('response' in tenantResolution) return tenantResolution.response;

  try {
    const results = await executarSubmit(body, tenantResolution.tenantId);
    return NextResponse.json(results, { status: 200 });
  } catch (err) {
    if (err instanceof SubmitInvalidoError) {
      return NextResponse.json({ error: err.message }, { status: 400 });
    }
    throw err;
  }
}
