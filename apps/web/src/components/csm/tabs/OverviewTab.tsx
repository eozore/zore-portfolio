/* ============================================================
   OverviewTab.tsx — Visão Geral: TODOS os projetos, travados ou não.

   Resolve o problema de visibilidade: hoje um pacote ou pipeline de vídeo
   só aparece se você estiver exatamente na sessão do navegador que o criou.
   Esta tela junta tudo — pacotes editoriais e pipelines de vídeo — com um
   status computado (rodando / travado / erro / pronto) e um botão para
   pular direto para aquele projeto.
   ============================================================ */
'use client';

import { useState, useEffect, useCallback } from 'react';
import styles from './OverviewTab.module.css';

interface OverviewItem {
  id: string;
  kind: 'pacote' | 'video';
  title: string;
  status: 'idle' | 'running' | 'stuck' | 'done' | 'error';
  statusLabel: string;
  detail: string;
  updatedAt: number;
  updatedLabel: string;
  sessionId?: string;
}

interface OverviewTabProps {
  onBack: () => void;
  onOpenSession: (sessionId: string) => void;
}

const DOT_CLASS: Record<OverviewItem['status'], string> = {
  done: 'dotDone', running: 'dotRunning', stuck: 'dotStuck', error: 'dotError', idle: 'dotIdle',
};

const PILL_LABEL: Record<'stuck' | 'error' | 'running' | 'done', string> = {
  stuck: '⏸ travado', error: '✗ erro', running: '⟳ rodando', done: '✓ pronto',
};

export default function OverviewTab({ onBack, onOpenSession }: OverviewTabProps) {
  const [items, setItems] = useState<OverviewItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [lastFetch, setLastFetch] = useState<Date | null>(null);

  const fetchOverview = useCallback(async () => {
    try {
      const res = await fetch('/api/csm/overview', { headers: { 'x-csm-session': 'authenticated' } });
      if (res.ok) {
        const data = await res.json();
        setItems(data.items ?? []);
        setLastFetch(new Date());
      }
    } catch (err) {
      console.error('[overview] fetch failed:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchOverview();
    const interval = setInterval(fetchOverview, 30_000);
    return () => clearInterval(interval);
  }, [fetchOverview]);

  const counts = {
    running: items.filter((i) => i.status === 'running').length,
    stuck: items.filter((i) => i.status === 'stuck').length,
    error: items.filter((i) => i.status === 'error').length,
    done: items.filter((i) => i.status === 'done').length,
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div>
          <h2 className={styles.title}>🗂️ Visão Geral</h2>
          <p className={styles.subtitle}>
            Todos os projetos — pacotes editoriais e pipelines de vídeo — num lugar só.
            {lastFetch && ` Atualizado ${lastFetch.toLocaleTimeString('pt-BR')} · atualiza a cada 30s.`}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button onClick={fetchOverview} className={styles.refreshBtn} type="button">↻ Atualizar</button>
          <button onClick={onBack} className={styles.refreshBtn} type="button">← Studio</button>
        </div>
      </div>

      {(counts.stuck > 0 || counts.error > 0) && (
        <div className={styles.summaryRow}>
          {counts.stuck > 0 && (
            <span className={`${styles.summaryPill} ${styles.summaryPillStuck}`}>
              ⏸ {counts.stuck} projeto(s) travado(s) — sem atualização além do esperado
            </span>
          )}
          {counts.error > 0 && (
            <span className={`${styles.summaryPill} ${styles.summaryPillError}`}>
              ✗ {counts.error} com erro
            </span>
          )}
          {counts.running > 0 && (
            <span className={`${styles.summaryPill} ${styles.summaryPillRunning}`}>
              ⟳ {counts.running} em andamento
            </span>
          )}
          <span className={`${styles.summaryPill} ${styles.summaryPillOk}`}>
            ✓ {counts.done} concluído(s)
          </span>
        </div>
      )}

      {isLoading ? (
        <div className={styles.loadingState}><div className={styles.spinner} /><span>Carregando projetos...</span></div>
      ) : items.length === 0 ? (
        <div className={styles.emptyState}>
          <div style={{ fontSize: '1.5rem' }}>📭</div>
          <div>Nenhum projeto ainda. Comece uma conversa com o CMO.</div>
        </div>
      ) : (
        <div className={styles.list}>
          {items.map((item) => (
            <div key={`${item.kind}-${item.id}`} className={`${styles.card} ${item.status === 'stuck' ? styles.cardStuck : ''} ${item.status === 'error' ? styles.cardError : ''}`}>
              <span className={`${styles.statusDot} ${styles[DOT_CLASS[item.status]]}`} />
              <div className={styles.cardBody}>
                <div className={styles.cardTitleRow}>
                  <span className={styles.cardKind}>{item.kind === 'pacote' ? 'pacote' : 'vídeo'}</span>
                  <span className={styles.cardTitle}>{item.title}</span>
                </div>
                <div className={styles.cardStatus}>
                  {item.status in PILL_LABEL ? `${PILL_LABEL[item.status as keyof typeof PILL_LABEL]} · ` : ''}{item.statusLabel}
                </div>
                {item.detail && <div className={styles.cardDetail}>{item.detail}</div>}
              </div>
              <div className={styles.cardMeta}>
                <span className={styles.cardTime}>{item.updatedLabel}</span>
                {item.sessionId && (
                  <button className={styles.cardBtn} type="button" onClick={() => onOpenSession(item.sessionId!)}>
                    Abrir →
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
