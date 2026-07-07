'use client';

/**
 * RichArticleRenderer
 *
 * Renders the AI-generated article content with EXACT same styling
 * as the production blog page (eozore.com). Uses the same Tailwind classes
 * from `MarkdownRenderer.tsx` to guarantee pixel-perfect preview.
 *
 * Extra features beyond production:
 * - Mermaid diagrams (```mermaid blocks)
 * - Chart/Plot blocks (```python-plot / matplotlib_plot)
 *
 * Usage:
 *   <RichArticleRenderer content={markdownString} />
 */

import React, { useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';
import rehypeHighlight from 'rehype-highlight';
import 'katex/dist/katex.min.css';
import styles from './RichArticleRenderer.module.css';

interface RichArticleRendererProps {
  content: string;
  className?: string;
}

// ── Mermaid Diagram Sanitizer ──
function cleanMermaidCode(rawCode: string): string {
  let cleaned = rawCode.trim();

  if (cleaned.startsWith('```')) {
    cleaned = cleaned.replace(/^```(?:mermaid)?\n?/i, '').replace(/\n?```$/m, '');
  }
  cleaned = cleaned.trim();

  // Reformat single-line Mermaid declarations with statement separators into clean multi-line blocks
  cleaned = cleaned.replace(/;/g, '\n');
  cleaned = cleaned.replace(/^(graph\s+\w+|flowchart\s+\w+|sequenceDiagram|classDiagram|stateDiagram|erDiagram|gantt|pie|journey|gitGraph|requirementDiagram)\s+/i, '$1\n');
  cleaned = cleaned.replace(/([^\n])\s*(subgraph\b|direction\b|end\b|click\b|style\b|classDef\b|class\b|linkStyle\b)/g, '$1\n$2');
  cleaned = cleaned.replace(/(subgraph\s+"[^"]+")\s+/ig, '$1\n');

  cleaned = cleaned.replace(/\$\$[\s\S]*?\$\$/g, '');
  cleaned = cleaned.replace(/\$[^\n$]+\$/g, (match) => {
    return match.replace(/\$/g, '').replace(/\\text\{([^}]+)\}/g, '$1').replace(/\\[a-zA-Z]+/g, ' ');
  });

  const lines = cleaned.split('\n');
  const repairedLines = lines.map(line => {
    let l = line.trim();
    if (!l) return l;

    if (/^(graph|flowchart|sequenceDiagram|classDiagram|stateDiagram|erDiagram|gantt|pie|journey|gitGraph|requirementDiagram)\b/i.test(l)) {
      return l;
    }

    l = l.replace(/(\w+)(\[|\(|\{)([^"\])}]+)(\]|\)|\})/g, (match, nodeName, openBrace, nodeText, closeBrace) => {
      const cleanText = nodeText.trim().replace(/"/g, "'");
      return `${nodeName}${openBrace}"${cleanText}"${closeBrace}`;
    });

    return l;
  });

  return repairedLines.join('\n');
}

// ── Mermaid Block Component ──
const MermaidBlock = ({ code }: { code: string }) => {
  const ref = useRef<HTMLDivElement>(null);
  const [scale, setScale] = React.useState(1);
  const [position, setPosition] = React.useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = React.useState(false);
  const [dragStart, setDragStart] = React.useState({ x: 0, y: 0 });

  useEffect(() => {
    let cancelled = false;

    const render = async () => {
      if (!ref.current || cancelled) return;

      try {
        const mermaid = (await import('mermaid')).default;
        mermaid.initialize({
          startOnLoad: false,
          theme: 'neutral',
          themeVariables: {
            background: '#f8f7f4',
            primaryColor: '#e67e22',
            primaryTextColor: '#1e1e1e',
            primaryBorderColor: '#d35400',
            lineColor: '#6b6b6b',
            secondaryColor: '#fff3e8',
            tertiaryColor: '#fff8f0',
            fontFamily: 'Inter, sans-serif',
            fontSize: '14px',
          },
        });

        const id = `mermaid-${Math.random().toString(36).slice(2)}`;
        const sanitizedCode = cleanMermaidCode(code);
        const { svg } = await mermaid.render(id, sanitizedCode);
        if (ref.current && !cancelled) {
          ref.current.innerHTML = svg;
          const svgEl = ref.current.querySelector('svg');
          if (svgEl) {
            svgEl.style.width = '100%';
            svgEl.style.height = 'auto';
            svgEl.style.cursor = 'grab';
          }
        }
      } catch (err) {
        if (ref.current && !cancelled) {
          ref.current.innerHTML = `<pre class="${styles.mermaidError}">⚠️ Erro ao renderizar diagrama:\n${String(err)}</pre>`;
        }
      }
    };

    render();
    return () => {
      cancelled = true;
    };
  }, [code]);

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
    setDragStart({ x: e.clientX - position.x, y: e.clientY - position.y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    setPosition({
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y,
    });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const zoomIn = () => setScale((s) => Math.min(s + 0.15, 3));
  const zoomOut = () => setScale((s) => Math.max(s - 0.15, 0.5));
  const resetZoom = () => {
    setScale(1);
    setPosition({ x: 0, y: 0 });
  };

  return (
    <div className={styles.mermaidWrapper}>
      <div className={styles.mermaidControls}>
        <button onClick={zoomIn} title="Aumentar Zoom" type="button">+</button>
        <button onClick={zoomOut} title="Diminuir Zoom" type="button">−</button>
        <button onClick={resetZoom} title="Resetar Zoom" type="button">⟲</button>
      </div>
      <div
        ref={ref}
        className={styles.mermaidContainer}
        style={{
          transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`,
          transformOrigin: 'center center',
          cursor: isDragging ? 'grabbing' : 'grab',
        }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      />
    </div>
  );
};

// ── Matplotlib Plot Parser ──
interface ChartDataset {
  label: string;
  x: number[];
  y: number[];
}

interface ChartData {
  title: string;
  xLabel: string;
  yLabel: string;
  type: 'line' | 'scatter' | 'bar';
  datasets: ChartDataset[];
}

function parseMatplotlib(code: string): ChartData | null {
  try {
    const lines = code.split('\n');
    const vars: Record<string, number[]> = {};
    
    let title = '';
    let xLabel = '';
    let yLabel = '';
    let type: 'line' | 'scatter' | 'bar' = 'line';
    
    const datasets: ChartDataset[] = [];
    
    for (let line of lines) {
      line = line.trim();
      if (!line || line.startsWith('#')) continue;
      
      // Parse list variable definition, e.g. x = [1, 2, 3, 4]
      const listMatch = line.match(/^(\w+)\s*=\s*\[([^\]]+)\]/);
      if (listMatch) {
        const varName = listMatch[1];
        const elements = listMatch[2].split(',').map(el => {
          const val = parseFloat(el.trim().replace(/['"]/g, ''));
          return isNaN(val) ? 0 : val;
        });
        vars[varName] = elements;
        continue;
      }
      
      // Parse list(range(start, end)) definition, e.g. epochs = list(range(1, 11))
      const rangeMatch = line.match(/^(\w+)\s*=\s*list\(range\((\d+)\s*,\s*(\d+)\)\)/);
      if (rangeMatch) {
        const varName = rangeMatch[1];
        const start = parseInt(rangeMatch[2], 10);
        const end = parseInt(rangeMatch[3], 10);
        const elements: number[] = [];
        for (let i = start; i < end; i++) {
          elements.push(i);
        }
        vars[varName] = elements;
        continue;
      }
      
      // Parse plt.title
      const titleMatch = line.match(/plt\.title\(['"]([^'"]+)['"]\)/);
      if (titleMatch) {
        title = titleMatch[1];
        continue;
      }
      
      // Parse plt.xlabel
      const xLabelMatch = line.match(/plt\.xlabel\(['"]([^'"]+)['"]\)/);
      if (xLabelMatch) {
        xLabel = xLabelMatch[1];
        continue;
      }
      
      // Parse plt.ylabel
      const yLabelMatch = line.match(/plt\.ylabel\(['"]([^'"]+)['"]\)/);
      if (yLabelMatch) {
        yLabel = yLabelMatch[1];
        continue;
      }
      
      // Parse plt.plot(x, y, label='...') or plt.scatter, plt.bar
      const plotMatch = line.match(/plt\.(plot|scatter|bar)\(([^)]+)\)/);
      if (plotMatch) {
        const plotType = plotMatch[1] as 'plot' | 'scatter' | 'bar';
        type = plotType === 'plot' ? 'line' : plotType;
        
        const argsStr = plotMatch[2];
        const args = argsStr.split(',').map(s => s.trim());
        if (args.length >= 2) {
          let xVal: number[] = [];
          let yVal: number[] = [];
          
          const arg1 = args[0];
          if (vars[arg1]) {
            xVal = vars[arg1];
          } else if (arg1.startsWith('[') && arg1.endsWith(']')) {
            xVal = arg1.slice(1, -1).split(',').map(el => parseFloat(el.trim())).filter(n => !isNaN(n));
          } else {
            const val = parseFloat(arg1);
            if (!isNaN(val)) xVal = [val];
          }
          
          const arg2 = args[1];
          if (vars[arg2]) {
            yVal = vars[arg2];
          } else if (arg2.startsWith('[') && arg2.endsWith(']')) {
            yVal = arg2.slice(1, -1).split(',').map(el => parseFloat(el.trim())).filter(n => !isNaN(n));
          } else {
            const val = parseFloat(arg2);
            if (!isNaN(val)) yVal = [val];
          }
          
          let label = `Dataset ${datasets.length + 1}`;
          const labelArg = args.find(a => a.startsWith('label='));
          if (labelArg) {
            const labelMatch = labelArg.match(/label=['"]([^'"]+)['"]/);
            if (labelMatch) {
              label = labelMatch[1];
            }
          }
          
          if (xVal.length > 0 && yVal.length > 0) {
            datasets.push({ label, x: xVal, y: yVal });
          }
        }
      }
    }
    
    if (datasets.length === 0) return null;
    return { title, xLabel, yLabel, type, datasets };
  } catch (err) {
    console.warn('Failed parsing matplotlib python-plot block:', err);
    return null;
  }
}

// ── Interactive SVG Chart Component ──
const InteractiveChart = ({ code }: { code: string }) => {
  const chartData = React.useMemo(() => parseMatplotlib(code), [code]);
  const [activePoint, setActivePoint] = React.useState<{
    datasetIndex: number;
    pointIndex: number;
    x: number;
    y: number;
    valX: number;
    valY: number;
    label: string;
  } | null>(null);

  if (!chartData) {
    return (
      <pre className="bg-[#1e1e2e] rounded-xl p-5 my-6 overflow-x-auto border border-white/[0.08] shadow-[0_4px_16px_rgba(0,0,0,0.12)]">
        <code className="font-mono text-[0.875rem] leading-[1.7] text-[#cdd6f4] language-python">
          {code}
        </code>
      </pre>
    );
  }

  const width = 500;
  const height = 300;
  const paddingLeft = 55;
  const paddingRight = 20;
  const paddingTop = 40;
  const paddingBottom = 40;

  const allX = chartData.datasets.flatMap(d => d.x);
  const allY = chartData.datasets.flatMap(d => d.y);
  const xMin = Math.min(...allX);
  const xMax = Math.max(...allX);
  const yMin = Math.min(0, ...allY);
  const yMax = Math.max(...allY) * 1.1 || 10;

  const scaleX = (val: number) => {
    if (xMax === xMin) return paddingLeft + (width - paddingLeft - paddingRight) / 2;
    return paddingLeft + ((val - xMin) / (xMax - xMin)) * (width - paddingLeft - paddingRight);
  };

  const scaleY = (val: number) => {
    if (yMax === yMin) return paddingTop + (height - paddingTop - paddingBottom) / 2;
    return height - paddingBottom - ((val - yMin) / (yMax - yMin)) * (height - paddingTop - paddingBottom);
  };

  const colors = ['#e67e22', '#7c3aed', '#06b6d4', '#10b981', '#f43f5e'];

  return (
    <div className={styles.chartWrapper}>
      <div className={styles.chartHeader}>
        <h4 className={styles.chartTitle}>{chartData.title || 'Gráfico Científico'}</h4>
        <span className={styles.chartTypeBadge}>{chartData.type}</span>
      </div>
      
      <div className={styles.chartSvgContainer}>
        {activePoint && (
          <div
            className={styles.chartTooltip}
            style={{
              left: `${(activePoint.x / width) * 100}%`,
              top: `${(activePoint.y / height) * 100}%`,
            }}
          >
            <span className={styles.chartTooltipLabel}>{activePoint.label}</span>
            <span className={styles.chartTooltipValue}>
              {chartData.xLabel || 'X'}: {activePoint.valX.toFixed(2)}
            </span>
            <span className={styles.chartTooltipValue}>
              {chartData.yLabel || 'Y'}: {activePoint.valY.toFixed(2)}
            </span>
          </div>
        )}

        <svg viewBox={`0 0 ${width} ${height}`} width="100%" height="auto">
          {/* Grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((ratio, idx) => {
            const val = yMin + ratio * (yMax - yMin);
            const y = scaleY(val);
            return (
              <g key={idx}>
                <line x1={paddingLeft} y1={y} x2={width - paddingRight} y2={y} className={styles.chartGrid} />
                <text x={paddingLeft - 8} y={y + 3} textAnchor="end" className={styles.chartText}>
                  {val.toFixed(1)}
                </text>
              </g>
            );
          })}

          {/* X ticks */}
          {chartData.datasets[0].x.filter((_, idx, arr) => {
            const step = Math.max(1, Math.floor(arr.length / 5));
            return idx % step === 0 || idx === arr.length - 1;
          }).map((val, idx) => {
            const x = scaleX(val);
            return (
              <text key={idx} x={x} y={height - paddingBottom + 16} textAnchor="middle" className={styles.chartText}>
                {val.toFixed(0)}
              </text>
            );
          })}

          {/* Axes */}
          <line x1={paddingLeft} y1={paddingTop} x2={paddingLeft} y2={height - paddingBottom} className={styles.chartAxis} />
          <line x1={paddingLeft} y1={height - paddingBottom} x2={width - paddingRight} y2={height - paddingBottom} className={styles.chartAxis} />

          {/* Axis Labels */}
          {chartData.xLabel && (
            <text x={paddingLeft + (width - paddingLeft - paddingRight) / 2} y={height - 6} textAnchor="middle" className={styles.chartText} style={{ fontWeight: 'bold' }}>
              {chartData.xLabel}
            </text>
          )}

          {/* Lines and points */}
          {chartData.datasets.map((dataset, dIdx) => {
            const color = colors[dIdx % colors.length];
            const points = dataset.x.map((xVal, pIdx) => ({
              cx: scaleX(xVal),
              cy: scaleY(dataset.y[pIdx]),
              valX: xVal,
              valY: dataset.y[pIdx],
            }));
            
            const pathD = points.map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${p.cx} ${p.cy}`).join(' ');
            const areaD = points.length > 0 
              ? `${pathD} L ${points[points.length - 1].cx} ${height - paddingBottom} L ${points[0].cx} ${height - paddingBottom} Z`
              : '';

            return (
              <g key={dIdx}>
                {chartData.type === 'line' && areaD && (
                  <path d={areaD} className={styles.chartArea} fill={color} />
                )}
                {chartData.type === 'line' && (
                  <path d={pathD} className={styles.chartLine} stroke={color} />
                )}

                {points.map((p, pIdx) => {
                  const isActive = activePoint && activePoint.datasetIndex === dIdx && activePoint.pointIndex === pIdx;
                  
                  if (chartData.type === 'bar') {
                    const barWidth = Math.max(6, (width - paddingLeft - paddingRight) / (dataset.x.length * 2));
                    const barHeight = height - paddingBottom - p.cy;
                    return (
                      <rect
                        key={pIdx}
                        x={p.cx - barWidth / 2}
                        y={p.cy}
                        width={barWidth}
                        height={barHeight}
                        fill={color}
                        opacity={isActive ? 1 : 0.8}
                        onMouseEnter={() => setActivePoint({
                          datasetIndex: dIdx,
                          pointIndex: pIdx,
                          x: p.cx,
                          y: p.cy,
                          valX: p.valX,
                          valY: p.valY,
                          label: dataset.label,
                        })}
                        onMouseLeave={() => setActivePoint(null)}
                        style={{ cursor: 'pointer', transition: 'opacity 0.2s' }}
                      />
                    );
                  }

                  return (
                    <circle
                      key={pIdx}
                      cx={p.cx}
                      cy={p.cy}
                      r={isActive ? 6 : 4}
                      className={`${styles.chartDot} ${isActive ? styles.chartDotActive : ''}`}
                      stroke={color}
                      onMouseEnter={() => setActivePoint({
                        datasetIndex: dIdx,
                        pointIndex: pIdx,
                        x: p.cx,
                        y: p.cy,
                        valX: p.valX,
                        valY: p.valY,
                        label: dataset.label,
                      })}
                      onMouseLeave={() => setActivePoint(null)}
                    />
                  );
                })}
              </g>
            );
          })}
        </svg>
      </div>

      <div className={styles.chartLegend}>
        {chartData.datasets.map((dataset, dIdx) => (
          <div key={dIdx} className={styles.legendItem}>
            <span className={styles.legendColor} style={{ backgroundColor: colors[dIdx % colors.length] }} />
            <span>{dataset.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

/**
 * Main renderer. Uses the EXACT same component styling as the production
 * blog MarkdownRenderer to ensure preview fidelity.
 */
export default function RichArticleRenderer({
  content,
  className,
}: RichArticleRendererProps) {
  return (
    <div className={`article-content ${className ?? ''}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex, rehypeHighlight]}
        components={{
          // ── Headings (exact match with MarkdownRenderer.tsx) ──
          h1: ({ children }) => (
            <h1 className="text-[2.2rem] font-bold mt-10 mb-4 text-primary leading-tight tracking-tight">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-[1.6rem] font-bold mt-10 mb-3 text-text-main pb-2 border-b-2 border-border leading-tight">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-[1.25rem] font-semibold mt-8 mb-2 text-text-main">
              {children}
            </h3>
          ),
          h4: ({ children }) => (
            <h4 className="text-[1.1rem] font-semibold mt-6 mb-2 text-text-main">
              {children}
            </h4>
          ),

          // ── Paragraph ──
          p: ({ children }) => (
            <p className="text-[1.075rem] leading-[1.8] text-text-main mb-5">
              {children}
            </p>
          ),

          // ── Strong / Emphasis ──
          strong: ({ children }) => (
            <strong className="font-semibold text-text-main">{children}</strong>
          ),
          em: ({ children }) => (
            <em className="italic">{children}</em>
          ),

          // ── Links ──
          a: ({ href, children }) => (
            <a
              href={href}
              className="text-primary underline underline-offset-[3px] hover:opacity-75 transition-opacity"
              target={href?.startsWith('http') ? '_blank' : undefined}
              rel={href?.startsWith('http') ? 'noopener noreferrer' : undefined}
            >
              {children}
            </a>
          ),

          // ── Lists ──
          ul: ({ children }) => (
            <ul className="mb-5 pl-6 space-y-2">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="mb-5 pl-6 space-y-2 list-decimal">{children}</ol>
          ),
          li: ({ children }) => (
            <li className="text-[1.075rem] leading-[1.7] text-text-main list-disc marker:text-primary">
              {children}
            </li>
          ),

          // ── Blockquote ──
          blockquote: ({ children }) => (
            <blockquote className="border-l-4 border-orange-500 bg-orange-50/60 px-6 py-4 my-6 rounded-r-xl text-text-muted not-italic">
              {children}
            </blockquote>
          ),

          // ── Horizontal Rule ──
          hr: () => (
            <hr className="border-none h-[2px] bg-border my-10 rounded" />
          ),

          // ── Code blocks — with Mermaid support ──
          pre: ({ children }) => {
            const firstChild = React.Children.toArray(children)[0] as React.ReactElement;
            const cls = firstChild?.props?.className || '';
            if (cls.includes('language-mermaid') || cls.includes('language-python-plot')) {
              return <>{children}</>;
            }
            return (
              <pre className="bg-[#1e1e2e] rounded-xl p-5 my-6 overflow-x-auto border border-white/[0.08] shadow-[0_4px_16px_rgba(0,0,0,0.12)]">
                {children}
              </pre>
            );
          },
          // eslint-disable-next-line
          code({ node: _node, className: cls, children, ...props }: Record<string, unknown>) {
            const language = (cls as string | undefined)?.replace('language-', '').trim() ?? '';
            const codeString = String(children).replace(/\n$/, '');

            // Mermaid diagrams — render as interactive SVG
            if (language === 'mermaid') {
              return <MermaidBlock code={codeString} />;
            }

            // Matplotlib charts — render as custom SVG chart
            if (language === 'python-plot') {
              return <InteractiveChart code={codeString} />;
            }

            // Block code (inside <pre>) — syntax highlighted by rehype-highlight
            const isBlock = (cls as string)?.includes('hljs') || (cls as string)?.includes('language-');
            if (isBlock) {
              return (
                <code
                  className={`font-mono text-[0.875rem] leading-[1.7] text-[#cdd6f4] ${cls || ''}`}
                  {...props}
                >
                  {children}
                </code>
              );
            }

            // Inline code
            return (
              <code className="font-mono text-[0.85em] bg-primary/[0.08] text-primary px-1.5 py-0.5 rounded font-medium">
                {children}
              </code>
            );
          },

          // ── Tables (exact match with production) ──
          table: ({ children }) => (
            <div className="my-6 overflow-x-auto rounded-xl border border-border">
              <table className="w-full text-[0.9rem] border-collapse">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-primary/[0.06]">{children}</thead>
          ),
          tbody: ({ children }) => (
            <tbody className="divide-y divide-border">{children}</tbody>
          ),
          tr: ({ children }) => (
            <tr className="hover:bg-primary/[0.02] transition-colors">{children}</tr>
          ),
          th: ({ children }) => (
            <th className="px-4 py-3 text-left font-semibold text-text-main border-b-2 border-border">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="px-4 py-2.5 text-text-light">{children}</td>
          ),

          // ── Images ──
          img: ({ src, alt }) => (
            <figure className="my-6">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={src as string}
                alt={(alt as string) || ''}
                className="rounded-lg max-w-full h-auto mx-auto shadow-[0_2px_12px_rgba(0,0,0,0.06)]"
                loading="lazy"
              />
              {alt && (
                <figcaption className="text-center text-sm text-text-light mt-2 italic">
                  {alt as string}
                </figcaption>
              )}
            </figure>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
