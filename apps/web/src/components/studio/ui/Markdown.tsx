/**
 * Markdown.tsx — Renderização do artigo no gate de aprovação.
 *
 * Mapa de componentes em vez de `@tailwindcss/typography`: o `prose` do
 * plugin não está instalado (a classe sairia sem efeito, e o artigo
 * apareceria como um bloco de texto corrido no exato momento em que alguém
 * precisa julgá-lo). Um mapa explícito também dá controle sobre o que
 * importa aqui — ritmo de leitura e hierarquia — sem trazer dependência.
 */
'use client';

import ReactMarkdown from 'react-markdown';

const H = 'font-bold tracking-tight text-[#1e1e1e]';

export function Markdown({ children }: { children: string }) {
  return (
    <ReactMarkdown
      components={{
        h1: (p) => <h1 className={`${H} mb-3 mt-7 text-[22px] first:mt-0`} {...p} />,
        h2: (p) => <h2 className={`${H} mb-2.5 mt-7 text-[18px] first:mt-0`} {...p} />,
        h3: (p) => <h3 className={`${H} mb-2 mt-5 text-[15px]`} {...p} />,
        p:  (p) => <p className="mb-4 text-[14px] leading-[1.75] text-[#2b2b2b]" {...p} />,
        ul: (p) => <ul className="mb-4 list-disc space-y-1.5 pl-5 text-[14px] leading-relaxed text-[#2b2b2b]" {...p} />,
        ol: (p) => <ol className="mb-4 list-decimal space-y-1.5 pl-5 text-[14px] leading-relaxed text-[#2b2b2b]" {...p} />,
        li: (p) => <li className="pl-1" {...p} />,
        strong: (p) => <strong className="font-semibold text-[#1e1e1e]" {...p} />,
        a: (p) => <a className="text-[#e67e22] underline underline-offset-2" target="_blank" rel="noopener noreferrer" {...p} />,
        blockquote: (p) => (
          <blockquote className="mb-4 border-l-2 border-[#e67e22]/40 pl-4 text-[14px] italic leading-relaxed text-[#4a4a4a]" {...p} />
        ),
        code: ({ className, ...p }) => {
          // Bloco (tem linguagem) versus inline: o artigo técnico tem os dois,
          // e tratá-los igual deixa o código inline gigante no meio da frase.
          const bloco = /language-/.test(className || '');
          return bloco
            ? <code className="block overflow-x-auto rounded-lg bg-[#0d0f14] p-4 font-mono text-[12px] leading-relaxed text-[#eae4dc]" {...p} />
            : <code className="rounded bg-black/[0.06] px-1.5 py-0.5 font-mono text-[12.5px] text-[#1e1e1e]" {...p} />;
        },
        pre: (p) => <pre className="mb-4" {...p} />,
        table: (p) => (
          <div className="mb-4 overflow-x-auto">
            <table className="w-full border-collapse text-[13px]" {...p} />
          </div>
        ),
        th: (p) => <th className="border-b border-black/10 px-3 py-2 text-left font-semibold" {...p} />,
        td: (p) => <td className="border-b border-black/[0.06] px-3 py-2 align-top text-[#2b2b2b]" {...p} />,
        hr: () => <hr className="my-7 border-black/[0.08]" />,
        // O artigo traz URLs assinadas do GCS, que expiram. next/image
        // tentaria otimizá-las e falharia quando a assinatura vencesse.
        img: (p) => (
          // eslint-disable-next-line @next/next/no-img-element
          <img className="mb-4 w-full rounded-xl" {...p} alt={p.alt || ''} />
        ),
      }}
    >
      {children}
    </ReactMarkdown>
  );
}
