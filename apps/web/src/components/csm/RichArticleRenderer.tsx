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

  // Remove wrapper de backticks se veio com ele
  if (cleaned.startsWith('```')) {
    cleaned = cleaned.replace(/^```(?:mermaid)?\n?/i, '').replace(/\n?```$/m, '').trim();
  }

  // Normaliza separadores: ponto e vírgula → newline
  cleaned = cleaned.replace(/;/g, '\n');

  // Garante newline após declaração do tipo de diagrama se veio tudo em uma linha
  cleaned = cleaned.replace(
    /^(graph\s+\w+|flowchart\s+\w+|sequenceDiagram|classDiagram|stateDiagram(?:[-v2]*)|erDiagram|gantt|pie|journey|gitGraph|requirementDiagram)\s+(?=\S)/i,
    '$1\n'
  );

  // Remove blocos LaTeX que crasham o parser Mermaid
  cleaned = cleaned.replace(/\$\$[\s\S]*?\$\$/g, '');
  cleaned = cleaned.replace(/\$[^\n$]+\$/g, (match) =>
    match.replace(/\$/g, '').replace(/\\[a-zA-Z]+\{([^}]+)\}/g, '$1').replace(/\\[a-zA-Z]+/g, '')
  );

  // Converte <br> HTML para espaço dentro de rótulos (Mermaid não aceita HTML)
  cleaned = cleaned.replace(/<br\s*\/?>/gi, ' ');

  return cleaned.trim();
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

// ── Matplotlib Plot Parser — REMOVIDO (BUG3 fix) ──
// O code_executor agora salva o PNG no GCS como ![alt](url) no Markdown.
// O handler de <img> abaixo renderiza normalmente — sem parsing JS necessário.

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

          // ── Images (inclui plots GCS gerados pelo code_executor) ──
          // BUG3 fix: code_executor retorna ![alt](https://storage.googleapis.com/...)
          // que chega aqui como um <img> padrão. Sem parsing JavaScript necessário.
          // eslint-disable-next-line @next/next/no-img-element
          img: ({ src, alt }) => (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={src}
              alt={alt ?? 'gráfico'}
              className="w-full rounded-xl my-6 border border-white/[0.08] shadow-[0_4px_16px_rgba(0,0,0,0.12)]"
              loading="lazy"
            />
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
            // Intercept mermaid ANTES do <pre> renderizar
            const child = React.Children.toArray(children)[0] as React.ReactElement<{className?: string; children?: React.ReactNode}>;
            const childClass = child?.props?.className ?? '';
            if (childClass.includes('language-mermaid')) {
              const codeText = String(child?.props?.children ?? '').replace(/\n$/, '');
              return <MermaidBlock code={cleanMermaidCode(codeText)} />;
            }
            return (
              <pre className="bg-[#1e1e2e] rounded-xl p-5 my-6 overflow-x-auto border border-white/[0.08] shadow-[0_4px_16px_rgba(0,0,0,0.12)]">
                {children}
              </pre>
            );
          },
          // eslint-disable-next-line
          // react-markdown's ExtraProps are not exported consistently across
          // the supported versions, so keep this adapter intentionally loose.
          code({ node: _node, className: cls, children, ...props }: any) {
            const language = (cls as string | undefined)?.replace('language-', '').trim() ?? '';
            const codeString = String(children).replace(/\n$/, '');

            // Mermaid — já tratado no <pre>, mas fallback caso venha inline
            if (language === 'mermaid') {
              return <MermaidBlock code={cleanMermaidCode(codeString)} />;
            }

            // Matplotlib charts — BUG3 fix: code_executor gera imagem no GCS
            // e insere no Markdown como ![alt](url). O bloco python-plot no
            // artigo foi substituído por ```python + ![img](url) antes de chegar aqui.
            // Se ainda aparecer python-plot (artigos antigos), renderiza como código padrão.
            if (language === 'python-plot') {
              return (
                <code
                  className="font-mono text-[0.875rem] leading-[1.7] text-[#cdd6f4] language-python"
                >
                  {codeString}
                </code>
              );
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

        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
