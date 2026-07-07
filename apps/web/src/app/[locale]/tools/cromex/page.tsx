'use client';

import React, { useState, useMemo } from 'react';
import type { Locale } from '@/types/i18n';
import dashboardData from '@/data/cromex_dashboard.json';
import styles from './cromex.module.css';

interface CromexPageProps {
  params: { locale: Locale };
}

export default function CromexPage({ params }: CromexPageProps) {
  const { locale } = params;

  // States
  const [activeTab, setActiveTab] = useState<'dashboard' | 'cm1' | 'processes'>('dashboard');
  const [market, setMarket] = useState<'MI' | 'ME'>('MI');
  const [selectedMonth, setSelectedMonth] = useState<string>('');
  const [cm1Search, setCm1Search] = useState<string>('');
  
  // Simulation States for Processes
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [peLinear, setPeLinear] = useState('');
  const [peBaixa, setPeBaixa] = useState('');
  const [pp, setPp] = useState('');
  const [showWarningModal, setShowWarningModal] = useState(false);
  const [showDownloadBtn, setShowDownloadBtn] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [filesUploaded, setFilesUploaded] = useState({ vendas: false, aderencia: false });

  // Load market specific data
  const marketData = useMemo(() => {
    return dashboardData[market] || { months: [], historical: [], by_month: {} };
  }, [market]);

  // Set default month to last available month if empty
  const monthsList = useMemo(() => {
    return marketData.months || [];
  }, [marketData]);

  React.useEffect(() => {
    if (monthsList.length > 0 && !selectedMonth) {
      setSelectedMonth(monthsList[monthsList.length - 1]);
    }
  }, [monthsList, selectedMonth]);

  // Current month's consolidated data
  const activeMonthData = useMemo(() => {
    if (!selectedMonth || !marketData.by_month) return null;
    return marketData.by_month[selectedMonth] || null;
  }, [selectedMonth, marketData]);

  // KPI display helper
  const kpis = useMemo(() => {
    if (!activeMonthData) return { itens: 0, aderencia: 0, aumento: 0, reducao: 0, manutencao: 0, novo: 0, recuperacao: 0, volume_total: 0 };
    return activeMonthData.kpis;
  }, [activeMonthData]);

  // CM1 filtered search
  const filteredCm1 = useMemo(() => {
    const data = dashboardData.CM1 || [];
    if (!cm1Search) return data.slice(0, 100);
    const searchLower = cm1Search.toLowerCase();
    return data.filter(item => 
      String(item.client_id).includes(searchLower) || 
      String(item.material_id).includes(searchLower)
    ).slice(0, 100);
  }, [cm1Search]);

  // Historical Chart dimensions & paths
  const historicalChartPaths = useMemo(() => {
    const hist = marketData.historical || [];
    if (hist.length === 0) return { bars: [], linePath: '', areaPath: '', points: [] };

    const width = 800;
    const height = 200;
    const paddingLeft = 60;
    const paddingRight = 60;
    const paddingTop = 20;
    const paddingBottom = 30;

    const chartWidth = width - paddingLeft - paddingRight;
    const chartHeight = height - paddingTop - paddingBottom;

    // Find limits
    const maxVol = Math.max(...hist.map(d => d.volume), 1);
    
    const stepX = chartWidth / (hist.length - 1 || 1);

    const bars = hist.map((d, index) => {
      const x = paddingLeft + index * stepX;
      const barWidth = Math.min(stepX * 0.4, 12);
      const barHeight = (d.volume / maxVol) * chartHeight;
      const y = paddingTop + chartHeight - barHeight;
      return {
        x: x - barWidth / 2,
        y,
        width: barWidth,
        height: barHeight,
        volume: d.volume,
        month: d.month
      };
    });

    const points = hist.map((d, index) => {
      const x = paddingLeft + index * stepX;
      // Adherence ranges from 0 to 100
      const y = paddingTop + chartHeight - (d.aderencia / 100) * chartHeight;
      return { x, y, value: d.aderencia, month: d.month };
    });

    let linePath = '';
    let areaPath = '';
    if (points.length > 0) {
      linePath = `M ${points[0].x} ${points[0].y} ` + points.slice(1).map(p => `L ${p.x} ${p.y}`).join(' ');
      areaPath = `${linePath} L ${points[points.length - 1].x} ${paddingTop + chartHeight} L ${points[0].x} ${paddingTop + chartHeight} Z`;
    }

    return { bars, linePath, areaPath, points, maxVol, chartHeight, paddingTop, paddingLeft, width, height };
  }, [marketData]);

  // Formatter for values
  const formatVol = (val: number) => {
    if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(2)} M`;
    if (val >= 1_000) return `${(val / 1_000).toFixed(0)} mil`;
    return String(val);
  };

  const handleFileUpload = (type: 'vendas' | 'aderencia') => {
    setFilesUploaded(prev => ({ ...prev, [type]: true }));
  };

  const startCalculation = (finalPeLinear: string, finalPeBaixa: string, finalPp: string) => {
    setIsProcessing(true);
    setProgress(0);
    setLogs([]);
    setShowDownloadBtn(false);

    const logMessages = [
      "Iniciando pipelines de cálculo da Cromex...",
      "Carregando bases do Google Cloud Storage...",
      "Conectando ao Firestore para buscar referências históricas...",
      `Aplicando parâmetros de PE/PP informados (PE Linear: ${finalPeLinear}, PE Baixa: ${finalPeBaixa}, PP: ${finalPp})...`,
      "Executando script cromex_cm1.py: Calculando quartis por material...",
      "Executando script cromex_cm1.py: Gerando CM1 sugerido (+5% margem)...",
      "Executando script cromex_aderencia_me.py: Mapeando Mercado Externo...",
      "Executando script cromex_aderencia_me.py: Aplicando deduplicações de Vendedores e Linhas...",
      "Executando script cromex_aderencia_mi.py: Mapeando Mercado Interno...",
      "Consolidando métricas e agregando bases de dados...",
      "Enviando dados consolidados para o Google Sheets...",
      "Salvando arquivos de backup locais na pasta dataoutput/...",
      "Atualizando banco de dados de visualização de dados (dashboard)...",
      "Processamento concluído com sucesso!"
    ];

    let currentStep = 0;
    const interval = setInterval(() => {
      if (currentStep < logMessages.length) {
        const time = new Date().toLocaleTimeString();
        setLogs(prev => [...prev, `[${time}] ${logMessages[currentStep]}`]);
        setProgress(Math.min(((currentStep + 1) / logMessages.length) * 100, 100));
        currentStep++;
      } else {
        clearInterval(interval);
        setIsProcessing(false);
        setShowDownloadBtn(true);
      }
    }, 800);
  };

  const triggerProcessRun = () => {
    if (!filesUploaded.vendas || !filesUploaded.aderencia) {
      alert("Por favor, faça upload de ambas as bases antes de rodar.");
      return;
    }

    // Check if any value is blank
    if (!peLinear.trim() || !peBaixa.trim() || !pp.trim()) {
      setShowWarningModal(true);
    } else {
      startCalculation(peLinear, peBaixa, pp);
    }
  };

  const confirmWarningFallback = () => {
    const finalPeLinear = peLinear.trim() || '202';
    const finalPeBaixa = peBaixa.trim() || '217';
    const finalPp = pp.trim() || '184';

    setPeLinear(finalPeLinear);
    setPeBaixa(finalPeBaixa);
    setPp(finalPp);

    setShowWarningModal(false);
    startCalculation(finalPeLinear, finalPeBaixa, finalPp);
  };

  return (
    <section className={styles.container}>
      {/* Title */}
      <div className={styles.header}>
        <div className={styles.titleSection}>
          <h1 id="cromex-title">Cromex Intelligence</h1>
          <p className={styles.subtitle}>Consolidação de CM1 e dashboards de aderência de preços (ME e MI).</p>
        </div>

        {/* Tab Controls */}
        <div className={styles.tabsContainer} role="tablist">
          <button
            id="tab-dashboard"
            role="tab"
            aria-selected={activeTab === 'dashboard'}
            className={`${styles.tabButton} ${activeTab === 'dashboard' ? styles.tabButtonActive : ''}`}
            onClick={() => setActiveTab('dashboard')}
          >
            Dashboard Aderência
          </button>
          <button
            id="tab-cm1"
            role="tab"
            aria-selected={activeTab === 'cm1'}
            className={`${styles.tabButton} ${activeTab === 'cm1' ? styles.tabButtonActive : ''}`}
            onClick={() => setActiveTab('cm1')}
          >
            Tabela CM1
          </button>
          <button
            id="tab-processes"
            role="tab"
            aria-selected={activeTab === 'processes'}
            className={`${styles.tabButton} ${activeTab === 'processes' ? styles.tabButtonActive : ''}`}
            onClick={() => setActiveTab('processes')}
          >
            Processos / Upload
          </button>
        </div>
      </div>

      {/* TAB 1: DASHBOARD ADERENCIA */}
      {activeTab === 'dashboard' && (
        <div>
          {/* Filters Bar */}
          <div className={styles.controlsBar}>
            <div className={styles.controlGroup}>
              <span className={styles.controlLabel}>Mercado</span>
              <select
                id="select-market"
                className={styles.selectInput}
                value={market}
                onChange={(e) => {
                  setMarket(e.target.value as 'ME' | 'MI');
                  setSelectedMonth(''); // Trigger default month reset
                }}
              >
                <option value="MI">Mercado Interno (MI)</option>
                <option value="ME">Mercado Externo (ME)</option>
              </select>
            </div>

            <div className={styles.controlGroup}>
              <span className={styles.controlLabel}>Período</span>
              <select
                id="select-month"
                className={styles.selectInput}
                value={selectedMonth}
                onChange={(e) => setSelectedMonth(e.target.value)}
              >
                {monthsList.map((m) => {
                  const [year, month] = m.split('-');
                  const monthNames = [
                    'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
                    'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'
                  ];
                  const label = `${monthNames[parseInt(month, 10) - 1]} de ${year}`;
                  return (
                    <option key={m} value={m}>
                      {label}
                    </option>
                  );
                })}
              </select>
            </div>
          </div>

          {/* KPI Cards Grid */}
          <div className={styles.kpiGrid}>
            <div className={`${styles.kpiCard} ${styles.kpiCardActive}`}>
              <div className={styles.kpiLabel}>Itens Faturados</div>
              <div className={styles.kpiValue}>{kpis.itens.toLocaleString()}</div>
              <span className={`${styles.kpiTrend} ${styles.trendNeutral}`}>Faturamentos</span>
            </div>

            <div className={`${styles.kpiCard} ${styles.kpiCardActive}`}>
              <div className={styles.kpiLabel}>Aderência</div>
              <div className={styles.kpiValue}>{kpis.aderencia}%</div>
              <span className={`${styles.kpiTrend} ${kpis.aderencia >= 75 ? styles.trendUp : styles.trendDown}`}>
                {kpis.aderencia >= 75 ? '★ Ótima' : '⚠ Abaixo da Meta'}
              </span>
            </div>

            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Aumento</div>
              <div className={styles.kpiValue}>{kpis.aumento}%</div>
              <span className={`${styles.kpiTrend} ${styles.trendUp}`}>↑ Preço subiu</span>
            </div>

            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Redução</div>
              <div className={styles.kpiValue}>{kpis.reducao}%</div>
              <span className={`${styles.kpiTrend} ${styles.trendDown}`}>↓ Preço caiu</span>
            </div>

            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Manutenção</div>
              <div className={styles.kpiValue}>{kpis.manutencao}%</div>
              <span className={`${styles.kpiTrend} ${styles.trendNeutral}`}>→ Preço mantido</span>
            </div>

            <div className={styles.kpiCard}>
              <div className={styles.kpiLabel}>Recuperação</div>
              <div className={styles.kpiValue}>{kpis.recuperacao}%</div>
              <span className={`${styles.kpiTrend} ${styles.trendUp}`}>🚀 Recuperados</span>
            </div>
          </div>

          {/* Dashboard Visual Grid */}
          <div className={styles.dashboardGrid}>
            {/* Historical Charts Panel */}
            <div className={`${styles.panel} ${styles.col12}`}>
              <div className={styles.panelHeader}>
                <div className={styles.panelTitle}>
                  <i className="fa-solid fa-chart-line" />
                  Aderência & Volume Histórico
                </div>
                <div style={{ display: 'flex', gap: '1rem', fontSize: '0.8rem', fontWeight: 600 }}>
                  <span style={{ color: '#e67e22' }}>■ Volume (Kg)</span>
                  <span style={{ color: '#2563eb' }}>● Aderência (%)</span>
                </div>
              </div>

              {/* Pure SVG Line/Bar Combination Chart */}
              <div className={styles.chartContainer}>
                {historicalChartPaths.bars.length > 0 ? (
                  <svg className={styles.chartSvg} viewBox={`0 0 ${historicalChartPaths.width} ${historicalChartPaths.height}`}>
                    {/* Gridlines */}
                    {[0, 0.25, 0.5, 0.75, 1].map((p, i) => {
                      const y = historicalChartPaths.paddingTop + p * (historicalChartPaths.chartHeight);
                      return (
                        <line
                          key={i}
                          x1={historicalChartPaths.paddingLeft}
                          y1={y}
                          x2={historicalChartPaths.width - 60}
                          y2={y}
                          className={styles.gridLine}
                        />
                      );
                    })}

                    {/* Bars for Volume */}
                    {historicalChartPaths.bars.map((bar, i) => (
                      <g key={i}>
                        <rect
                          x={bar.x}
                          y={bar.y}
                          width={bar.width}
                          height={bar.height}
                          className={styles.chartBar}
                        >
                          <title>{`${bar.month}: ${formatVol(bar.volume)}`}</title>
                        </rect>
                        {/* Month labels at bottom */}
                        {i % 3 === 0 && (
                          <text
                            x={bar.x + bar.width / 2}
                            y={historicalChartPaths.height - 10}
                            textAnchor="middle"
                            className={styles.axisText}
                          >
                            {bar.month}
                          </text>
                        )}
                      </g>
                    ))}

                    {/* Area & Line for Adherence */}
                    <path d={historicalChartPaths.areaPath} className={styles.chartArea} />
                    <path d={historicalChartPaths.linePath} className={styles.chartLine} />

                    {/* Points on Line */}
                    {historicalChartPaths.points.map((pt, i) => (
                      <circle
                        key={i}
                        cx={pt.x}
                        cy={pt.y}
                        r={4}
                        fill="#2563eb"
                        stroke="#ffffff"
                        strokeWidth={1.5}
                      >
                        <title>{`${pt.month}: Aderência ${pt.value}%`}</title>
                      </circle>
                    ))}

                    {/* Axis Labels */}
                    <text x={10} y={150} transform="rotate(-90 10 150)" className={styles.axisText}>Volume (kg)</text>
                    <text x={historicalChartPaths.width - 15} y={150} transform="rotate(90 y)" className={styles.axisText} textAnchor="middle">Aderência (%)</text>
                  </svg>
                ) : (
                  <p style={{ textAlign: 'center', paddingTop: '100px', color: 'var(--text-muted)' }}>Sem dados históricos disponíveis.</p>
                )}
              </div>
            </div>

            {/* Top 10 Clientes Panel (Horizontal SVG list) */}
            <div className={`${styles.panel} ${styles.col6}`}>
              <div className={styles.panelHeader}>
                <div className={styles.panelTitle}>
                  <i className="fa-solid fa-building" />
                  Top 10 Clientes por Volume & Aderência
                </div>
              </div>
              <div className={styles.tableContainer}>
                <table className={styles.customTable}>
                  <thead>
                    <tr>
                      <th>Cliente</th>
                      <th>Volume</th>
                      <th>Aderência</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(activeMonthData?.clients || []).map((cli, i) => (
                      <tr key={i}>
                        <td>{cli.name}</td>
                        <td>{formatVol(cli.volume)}</td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <div style={{ background: '#e2e8f0', width: '60px', height: '6px', borderRadius: '4px', overflow: 'hidden' }}>
                              <div style={{ background: '#16a34a', width: `${cli.aderencia}%`, height: '100%' }} />
                            </div>
                            <span style={{ fontSize: '0.8rem', fontWeight: 700 }}>{cli.aderencia.toFixed(0)}%</span>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Top 10 Vendedores Panel */}
            <div className={`${styles.panel} ${styles.col6}`}>
              <div className={styles.panelHeader}>
                <div className={styles.panelTitle}>
                  <i className="fa-solid fa-user-tie" />
                  Top 10 Vendedores por Volume & Aderência
                </div>
              </div>
              <div className={styles.tableContainer}>
                <table className={styles.customTable}>
                  <thead>
                    <tr>
                      <th>Vendedor</th>
                      <th>Volume</th>
                      <th>Aderência</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(activeMonthData?.sellers || []).map((sel, i) => (
                      <tr key={i}>
                        <td>{sel.name}</td>
                        <td>{formatVol(sel.volume)}</td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <div style={{ background: '#e2e8f0', width: '60px', height: '6px', borderRadius: '4px', overflow: 'hidden' }}>
                              <div style={{ background: '#e67e22', width: `${sel.aderencia}%`, height: '100%' }} />
                            </div>
                            <span style={{ fontSize: '0.8rem', fontWeight: 700 }}>{sel.aderencia.toFixed(0)}%</span>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Performance por Região & Linha & Tipo */}
            <div className={`${styles.panel} ${styles.col4}`}>
              <div className={styles.panelHeader}>
                <div className={styles.panelTitle}>
                  <i className="fa-solid fa-map-location-dot" />
                  Métricas por Região
                </div>
              </div>
              <div className={styles.tableContainer}>
                <table className={styles.customTable}>
                  <thead>
                    <tr>
                      <th>Região</th>
                      <th>Volume</th>
                      <th>Aderência</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(activeMonthData?.regions || []).map((reg, i) => (
                      <tr key={i}>
                        <td>{reg.name}</td>
                        <td>{formatVol(reg.volume)}</td>
                        <td>
                          <span className={`${styles.badge} ${reg.aderencia >= 75 ? styles.badgeSuccess : styles.badgeWarning}`}>
                            {reg.aderencia.toFixed(0)}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className={`${styles.panel} ${styles.col4}`}>
              <div className={styles.panelHeader}>
                <div className={styles.panelTitle}>
                  <i className="fa-solid fa-tags" />
                  Material (Linha)
                </div>
              </div>
              <div className={styles.tableContainer}>
                <table className={styles.customTable}>
                  <thead>
                    <tr>
                      <th>Linha</th>
                      <th>Volume</th>
                      <th>Aderência</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(activeMonthData?.materials || []).slice(0, 10).map((mat, i) => (
                      <tr key={i}>
                        <td>{mat.name}</td>
                        <td>{formatVol(mat.volume)}</td>
                        <td>
                          <span className={`${styles.badge} ${mat.aderencia >= 75 ? styles.badgeSuccess : styles.badgeWarning}`}>
                            {mat.aderencia.toFixed(0)}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className={`${styles.panel} ${styles.col4}`}>
              <div className={styles.panelHeader}>
                <div className={styles.panelTitle}>
                  <i className="fa-solid fa-cart-shopping" />
                  Tipo de Compra
                </div>
              </div>
              <div className={styles.tableContainer}>
                <table className={styles.customTable}>
                  <thead>
                    <tr>
                      <th>Canal</th>
                      <th>Volume</th>
                      <th>Aderência</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(activeMonthData?.purchase_types || []).map((pt, i) => (
                      <tr key={i}>
                        <td>{pt.name}</td>
                        <td>{formatVol(pt.volume)}</td>
                        <td>
                          <span className={`${styles.badge} ${pt.aderencia >= 75 ? styles.badgeSuccess : styles.badgeWarning}`}>
                            {pt.aderencia.toFixed(0)}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: CM1 REFERENCE LIST */}
      {activeTab === 'cm1' && (
        <div className={styles.panel}>
          <div className={styles.panelHeader}>
            <div className={styles.panelTitle}>
              <i className="fa-solid fa-list-check" />
              Lista de Referência CM1 sugerido (Top 100)
            </div>
            
            {/* Search filter & Download Button */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
              <a
                id="btn-download-cm1-tab"
                href="/api/tools/cromex/download"
                className={styles.downloadTabButton}
              >
                <i className="fa-solid fa-file-arrow-down" />
                Baixar Planilha CM1
              </a>

              <div className={styles.searchContainer}>
                <i className={`fa-solid fa-magnifying-glass ${styles.searchIcon}`} />
                <input
                  id="input-search-cm1"
                  type="text"
                  placeholder="Buscar Cliente ou Material..."
                  className={styles.searchBar}
                  value={cm1Search}
                  onChange={(e) => setCm1Search(e.target.value)}
                />
              </div>
            </div>
          </div>

          <div className={styles.tableContainer}>
            <table className={styles.customTable}>
              <thead>
                <tr>
                  <th>Código Cliente</th>
                  <th>Código Material</th>
                  <th>CM1 Recomendado</th>
                </tr>
              </thead>
              <tbody>
                {filteredCm1.length > 0 ? (
                  filteredCm1.map((item, index) => (
                    <tr key={index}>
                      <td>{item.client_id}</td>
                      <td>{item.material_id}</td>
                      <td style={{ fontWeight: 700, color: '#e67e22' }}>
                        R$ {item.cm1_indicado.toFixed(2)}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={3} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                      Nenhum registro encontrado para a busca.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 3: PROCESSES / PIPELINE TRIGGER */}
      {activeTab === 'processes' && (
        <div className={styles.panel}>
          <div className={styles.panelHeader}>
            <div className={styles.panelTitle}>
              <i className="fa-solid fa-gears" />
              Central de Processamento Autônomo
            </div>
          </div>

          <div className={styles.processForm}>
            <p className={styles.subtitle} style={{ marginBottom: '1rem', textAlign: 'center' }}>
              Faça upload dos arquivos mensais, informe os limitadores de preço e dispare os scripts de processamento da Cromex.
            </p>

            {/* File Upload Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div 
                id="upload-vendas"
                className={styles.uploadZone} 
                onClick={() => handleFileUpload('vendas')}
                style={{ borderColor: filesUploaded.vendas ? '#16a34a' : '' }}
              >
                <i className={`fa-solid ${filesUploaded.vendas ? 'fa-circle-check text-green-600' : 'fa-file-excel'} ${styles.uploadIcon}`} />
                <h4 style={{ fontWeight: 700, fontSize: '0.95rem' }}>Base de Vendas</h4>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                  {filesUploaded.vendas ? 'vendas.xlsx (Carregado)' : 'Clique para simular upload'}
                </p>
              </div>

              <div 
                id="upload-aderencia"
                className={styles.uploadZone} 
                onClick={() => handleFileUpload('aderencia')}
                style={{ borderColor: filesUploaded.aderencia ? '#16a34a' : '' }}
              >
                <i className={`fa-solid ${filesUploaded.aderencia ? 'fa-circle-check text-green-600' : 'fa-file-excel'} ${styles.uploadIcon}`} />
                <h4 style={{ fontWeight: 700, fontSize: '0.95rem' }}>Base de Aderência</h4>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                  {filesUploaded.aderencia ? 'aderencia.xlsx (Carregado)' : 'Clique para simular upload'}
                </p>
              </div>
            </div>

            {/* PE / PP configuration form */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <span className={styles.controlLabel}>Valores de Referência (PE_PP)</span>
              <div className={styles.formGrid}>
                <div className={styles.controlGroup}>
                  <label htmlFor="pe-linear-input" style={{ fontSize: '0.75rem', fontWeight: 600 }}>PE Linear</label>
                  <input
                    id="pe-linear-input"
                    type="number"
                    value={peLinear}
                    onChange={(e) => setPeLinear(e.target.value)}
                    className={styles.textInput}
                    placeholder="PE Linear"
                  />
                </div>
                <div className={styles.controlGroup}>
                  <label htmlFor="pe-baixa-input" style={{ fontSize: '0.75rem', fontWeight: 600 }}>PE Baixa</label>
                  <input
                    id="pe-baixa-input"
                    type="number"
                    value={peBaixa}
                    onChange={(e) => setPeBaixa(e.target.value)}
                    className={styles.textInput}
                    placeholder="PE Baixa"
                  />
                </div>
                <div className={styles.controlGroup}>
                  <label htmlFor="pp-input" style={{ fontSize: '0.75rem', fontWeight: 600 }}>PP</label>
                  <input
                    id="pp-input"
                    type="number"
                    value={pp}
                    onChange={(e) => setPp(e.target.value)}
                    className={styles.textInput}
                    placeholder="PP"
                  />
                </div>
              </div>
            </div>

            {/* Disparador de Execução */}
            <button
              id="btn-run-process"
              className={styles.runButton}
              onClick={triggerProcessRun}
              disabled={isProcessing || !filesUploaded.vendas || !filesUploaded.aderencia}
            >
              {isProcessing ? (
                <>
                  <i className="fa-solid fa-spinner fa-spin" />
                  Processando...
                </>
              ) : (
                <>
                  <i className="fa-solid fa-play" />
                  Rodar Processamento Mensal
                </>
              )}
            </button>

            {/* Progress bar */}
            {isProcessing && (
              <div className={styles.progressBarContainer}>
                <div className={styles.progressBar} style={{ width: `${progress}%` }} />
              </div>
            )}

            {/* Download Button */}
            {showDownloadBtn && !isProcessing && (
              <a
                id="btn-download-results"
                href="/api/tools/cromex/download?file=input_julho_2026.xlsx"
                download="input_julho_2026.xlsx"
                className={styles.downloadButton}
              >
                <i className="fa-solid fa-file-arrow-down" />
                Baixar Resultados (Excel)
              </a>
            )}

            {/* Logging Console output */}
            {logs.length > 0 && (
              <div className={styles.consoleLog}>
                {logs.map((log, i) => (
                  <div key={i} className={`${styles.logEntry} ${log.includes("concluído") ? styles.logSuccess : ''}`}>
                    {log}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Warning Modal Overlay */}
      {showWarningModal && (
        <div className={styles.warningOverlay}>
          <div className={styles.warningModal}>
            <div className={styles.warningHeader}>
              <i className="fa-solid fa-triangle-exclamation" />
              <h3>Valores de Referência Ausentes</h3>
            </div>
            <div className={styles.warningBody}>
              <p>
                Você não preencheu todos os valores de referência (PE Linear, PE Baixa e PP).
              </p>
              <p style={{ marginTop: '0.5rem' }}>
                Deseja prosseguir e calcular utilizando os valores de referência padrão do mês anterior?
              </p>
              <ul style={{ marginTop: '0.5rem', listStyle: 'disc', paddingLeft: '1.25rem' }}>
                <li>PE Linear: 202</li>
                <li>PE Baixa: 217</li>
                <li>PP: 184</li>
              </ul>
            </div>
            <div className={styles.warningButtons}>
              <button 
                id="btn-warning-cancel"
                className={styles.warningCancelBtn} 
                onClick={() => setShowWarningModal(false)}
              >
                Cancelar
              </button>
              <button 
                id="btn-warning-confirm"
                className={styles.warningConfirmBtn} 
                onClick={confirmWarningFallback}
              >
                Continuar
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
