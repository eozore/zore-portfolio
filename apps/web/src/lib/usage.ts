import { getFirestoreDb } from './firebase';
import { dbPaths } from './dbPaths';

export interface UsageLog {
  timestamp: number;
  stage: 'article_generation' | 'youtube_script' | 'social_repurpose' | 'heygen_render';
  model: string;
  inputTokens: number;
  outputTokens: number;
  estimatedCostUsd: number;
  latencyMs: number;
}

export async function logUsage(
  tenantId: string | null,
  stage: UsageLog['stage'],
  model: string,
  inputTokens: number,
  outputTokens: number,
  latencyMs: number
): Promise<void> {
  const db = getFirestoreDb();
  if (!db) return;

  const costInput = (inputTokens * 0.075) / 1000000;
  const costOutput = (outputTokens * 0.30) / 1000000;
  const estimatedCostUsd = costInput + costOutput;

  try {
    const logsColl = db.collection(dbPaths.usageLogs(tenantId));
    await logsColl.add({
      timestamp: Date.now(),
      stage,
      model,
      inputTokens,
      outputTokens,
      estimatedCostUsd,
      latencyMs,
    });
    console.log(`[usage] Logged cost of $${estimatedCostUsd.toFixed(6)} for stage ${stage} (${inputTokens} in, ${outputTokens} out)`);
  } catch (err) {
    console.error('[usage] Failed to write usage log:', err);
  }
}
