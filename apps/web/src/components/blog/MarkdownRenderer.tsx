'use client';

import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';
import rehypeHighlight from 'rehype-highlight';
import type { Components } from 'react-markdown';

interface MarkdownRendererProps {
  content: string;
}

/**
 * Custom components for react-markdown.
 * Every HTML element is styled explicitly so that AI-generated markdown
 * renders consistently regardless of markdown style variations.
 */
const components: Components = {
  // Headings
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

  // Paragraph
  p: ({ children }) => (
    <p className="text-[1.075rem] leading-[1.8] text-text-main mb-5">
      {children}
    </p>
  ),

  // Strong / Emphasis
  strong: ({ children }) => (
    <strong className="font-semibold text-text-main">{children}</strong>
  ),
  em: ({ children }) => (
    <em className="italic">{children}</em>
  ),

  // Links
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

  // Lists
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

  // Blockquote
  blockquote: ({ children }) => (
    <blockquote className="border-l-4 border-orange-500 bg-orange-50/60 px-6 py-4 my-6 rounded-r-xl text-text-muted not-italic">
      {children}
    </blockquote>
  ),

  // Horizontal rule
  hr: () => (
    <hr className="border-none h-[2px] bg-border my-10 rounded" />
  ),

  // Code blocks
  pre: ({ children }) => (
    <pre className="bg-[#1e1e2e] rounded-xl p-5 my-6 overflow-x-auto border border-white/[0.08] shadow-[0_4px_16px_rgba(0,0,0,0.12)]">
      {children}
    </pre>
  ),
  code: ({ className, children, ...props }) => {
    // Block code (inside <pre>)
    const isBlock = className?.includes('hljs') || className?.includes('language-');
    if (isBlock) {
      return (
        <code
          className={`font-mono text-[0.875rem] leading-[1.7] text-[#cdd6f4] ${className || ''}`}
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

  // Tables — fully styled components
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

  // Images
  img: ({ src, alt }) => (
    <figure className="my-6">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={alt || ''}
        className="rounded-lg max-w-full h-auto mx-auto shadow-[0_2px_12px_rgba(0,0,0,0.06)]"
        loading="lazy"
      />
      {alt && (
        <figcaption className="text-center text-sm text-text-light mt-2 italic">
          {alt}
        </figcaption>
      )}
    </figure>
  ),
};

export default function MarkdownRenderer({ content }: MarkdownRendererProps) {
  return (
    <div className="article-content">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex, rehypeHighlight]}
        components={components}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
