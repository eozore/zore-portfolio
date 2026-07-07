'use client';

import { useState, useEffect } from 'react';
import styles from './TelemetryTab.module.css';

interface TelemetryTabProps {
  onBack: () => void;
}

interface UsageSummary {
  totalCost: number;
  totalInputTokens: number;
  totalOutputTokens: number;
  totalCalls: number;
}

interface StageDistribution {
  stage: string;
  calls: number;
  cost: number;
}

interface UsageLogItem {
  id: string;
  timestamp: number;
  stage: string;
  model: string;
  inputTokens: number;
  outputTokens: number;
  estimatedCostUsd: number;
  latencyMs: number;
}

interface UsageMetrics {
  summary: UsageSummary;
  stageDistribution: StageDistribution[];
  recentLogs: UsageLogItem[];
}

export default function TelemetryTab({ onBack }: TelemetryTabProps) {
  const [metrics, setMetrics] = useState<UsageMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchUsageMetrics = async () => {
    try {
      setLoading(true);
      setError('');
      const token = typeof window !== 'undefined' ? sessionStorage.getItem('csm_auth_token') || '' : '';
      const tenantId = typeof window !== 'undefined' ? localStorage.getItem('csm_tenant_id') || '' : '';
      
      const res = await fetch('/api/csm/usage', {
        headers: {
          'x-csm-session': token,
          'x-tenant-id': tenantId,
        },
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const data = await res.json();
      setMetrics(data);
    } catch (err: any) {
      console.error('[csm/telemetry] Fetch error:', err);
      setError(err.message || 'Falha ao buscar telemetria de uso.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsageMetrics();
  }, []);

  const formatDate = (timestamp: number) => {
    const d = new Date(timestamp);
    return d.toLocaleString('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatStageLabel = (stage: string) => {
    const stageMap: Record<string, string> = {
      article_critic: 'Critic (Análise Editorial)',
      article_research: 'Research (Papers & Web)',
      article_generation: 'Generation (Escrita do Artigo)',
      youtube_script: 'YouTube Script (Roteiro)',
      social_repurpose: 'Repurpose (Derivação Omnicanal)',
      heygen_render: 'HeyGen Video (Avatar)',
      cmo_interview: 'CMO Interview (Pauta)',
    };
    return stageMap[stage] || stage;
  };

  const getStageBadgeClass = (stage: string) => {
    const base = styles.badgeStage;
    if (stage.includes('generation')) return `${base} ${styles.badgeStage_generation}`;
    if (stage.includes('critic')) return `${base} ${styles.badgeStage_critic}`;
    if (stage.includes('research')) return `${base} ${styles.badgeStage_research}`;
    if (stage.includes('youtube')) return `${base} ${styles.badgeStage_youtube}`;
    if (stage.includes('repurpose')) return `${base} ${styles.badgeStage_repurpose}`;
    return base;
  };

  const maxStageCost = metrics?.stageDistribution.reduce((max, s) => Math.max(max, s.cost), 0.000001) || 1;

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <div className={styles.titleSection}>
          <h2>📊 Uso & Telemetria</h2>
          <p>Métricas financeiras e de tokens de IA consumidos nas suas execuções</p>
        </div>
        <button onClick={fetchUsageMetrics} disabled={loading} className={styles.refreshBtn}>
          {loading ? 'Carregando...' : 'Atualizar Dados'}
        </button>
      </header>

      {loading ? (
        <div className={styles.loadingState}>
          <div className={styles.spinner} />
          <span>Calculando métricas do Firestore...</span>
        </div>
      ) : error ? (
        <div className={styles.emptyState} style={{ color: '#ef4444' }}>
          <span>❌ Erro: {error}</span>
        </div>
      ) : !metrics || metrics.summary.totalCalls === 0 ? (
        <div className={styles.emptyState}>
          <span>Nenhum log de uso registrado até o momento. Execute uma geração para coletar métricas.</span>
        </div>
      ) : (
        <>
          <div className={styles.grid}>
            <div className={styles.card}>
              <span className={styles.cardLabel}>Custo Estimado</span>
              <span className={styles.cardValue}>${metrics.summary.totalCost.toFixed(4)}</span>
              <span className={styles.cardSubtext}>Baseado nos preços do Gemini 2.5 Flash</span>
            </div>
            <div className={styles.card}>
              <span className={styles.cardLabel}>Tokens de Entrada</span>
              <span className={styles.cardValue}>{metrics.summary.totalInputTokens.toLocaleString()}</span>
              <span className={styles.cardSubtext}>Prompt e contexto dos agentes</span>
            </div>
            <div className={styles.card}>
              <span className={styles.cardLabel}>Tokens de Saída</span>
              <span className={styles.cardValue}>{metrics.summary.totalOutputTokens.toLocaleString()}</span>
              <span className={styles.cardSubtext}>Respostas e conteúdo final</span>
            </div>
            <div className={styles.card}>
              <span className={styles.cardLabel}>Total de Chamadas</span>
              <span className={styles.cardValue}>{metrics.summary.totalCalls}</span>
              <span className={styles.cardSubtext}>Últimas execuções agregadas</span>
            </div>
          </div>

          <div className={styles.chartSection}>
            <h3 className={styles.chartTitle}>Custo por Estágio de Processamento</h3>
            <div className={styles.barsContainer}>
              {metrics.stageDistribution.map((item) => {
                const percent = (item.cost / maxStageCost) * 100;
                return (
                  <div key={item.stage} className={styles.barRow}>
                    <div className={styles.barLabelInfo}>
                      <span className={styles.barStage}>{formatStageLabel(item.stage)}</span>
                      <span>${item.cost.toFixed(5)} ({item.calls}x)</span>
                    </div>
                    <div className={styles.barOuter}>
                      <div className={styles.barInner} style={{ width: `${percent}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className={styles.logsSection}>
            <h3 className={styles.chartTitle}>Execuções Recentes</h3>
            <div className={styles.tableWrapper}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Data</th>
                    <th>Etapa / Agente</th>
                    <th>Modelo</th>
                    <th>Tokens In/Out</th>
                    <th>Latência</th>
                    <th>Custo</th>
                  </tr>
                </thead>
                <tbody>
                  {metrics.recentLogs.map((log) => (
                    <tr key={log.id}>
                      <td>{formatDate(log.timestamp)}</td>
                      <td>
                        <span className={getStageBadgeClass(log.stage)}>
                          {formatStageLabel(log.stage)}
                        </span>
                      </td>
                      <td style={{ fontFamily: 'monospace', color: '#64748b' }}>{log.model}</td>
                      <td>{log.inputTokens.toLocaleString()} / {log.outputTokens.toLocaleString()}</td>
                      <td>{(log.latencyMs / 1000).toFixed(1)}s</td>
                      <td style={{ fontWeight: 600, color: '#0f172a' }}>
                        ${log.estimatedCostUsd.toFixed(5)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
