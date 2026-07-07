import { NextResponse } from 'next/server';
import { getFirestoreDb } from '@/lib/firebase';
import { dbPaths } from '@/lib/dbPaths';

export const dynamic = 'force-dynamic';

export async function GET(request: Request): Promise<Response> {
  const csmSession = request.headers.get('x-csm-session');
  if (csmSession !== 'authenticated') {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const tenantId = request.headers.get('x-tenant-id') || null;
  const db = getFirestoreDb();
  if (!db) {
    return NextResponse.json({ error: 'Firestore unavailable' }, { status: 500 });
  }

  try {
    const logsColl = db.collection(dbPaths.usageLogs(tenantId));
    
    const snapshot = await logsColl.orderBy('timestamp', 'desc').limit(100).get();
    
    let totalCost = 0;
    let totalInputTokens = 0;
    let totalOutputTokens = 0;
    let totalCalls = snapshot.size;
    
    const stageCounts: Record<string, { calls: number; cost: number }> = {};
    const recentLogs: any[] = [];

    snapshot.forEach((doc) => {
      const data = doc.data();
      const cost = Number(data.estimatedCostUsd) || 0;
      const input = Number(data.inputTokens) || 0;
      const output = Number(data.outputTokens) || 0;
      const stage = data.stage || 'unknown';

      totalCost += cost;
      totalInputTokens += input;
      totalOutputTokens += output;

      if (!stageCounts[stage]) {
        stageCounts[stage] = { calls: 0, cost: 0 };
      }
      stageCounts[stage].calls += 1;
      stageCounts[stage].cost += cost;

      if (recentLogs.length < 20) {
        recentLogs.push({
          id: doc.id,
          timestamp: data.timestamp || Date.now(),
          stage,
          model: data.model || 'gemini',
          inputTokens: input,
          outputTokens: output,
          estimatedCostUsd: cost,
          latencyMs: data.latencyMs || 0,
        });
      }
    });

    const metrics = {
      summary: {
        totalCost: Number(totalCost.toFixed(6)),
        totalInputTokens,
        totalOutputTokens,
        totalCalls,
      },
      stageDistribution: Object.entries(stageCounts).map(([stage, stats]) => ({
        stage,
        calls: stats.calls,
        cost: Number(stats.cost.toFixed(6)),
      })),
      recentLogs,
    };

    return NextResponse.json(metrics);
  } catch (err: any) {
    console.error('[csm/usage] GET error:', err);
    return NextResponse.json({ error: err.message || 'Failed to fetch usage metrics' }, { status: 500 });
  }
}
