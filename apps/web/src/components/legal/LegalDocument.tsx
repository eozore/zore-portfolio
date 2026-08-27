import type { ReactNode } from 'react';

/**
 * Layout dos documentos legais (privacidade e termos).
 *
 * Separado das páginas porque os dois documentos têm a mesma estrutura e
 * precisam continuar tendo: quem lê uma política compara com a outra, e
 * divergência de forma entre elas parece descuido.
 *
 * Sem hex cravado — só tokens do tailwind.config, como o resto do site.
 *
 * O `dangerouslySetInnerHTML` aqui é seguro e deliberado: o conteúdo é
 * estático, escrito no próprio repositório, e precisa de <strong>, <code> e
 * <a> no meio da frase. Nada vem de entrada de usuário, de Firestore ou de
 * query string — se um dia vier, este componente tem que sanitizar antes.
 */

export interface LegalSection {
  titulo: string;
  /** Parágrafos e listas na ordem em que aparecem. */
  blocos: Array<string | { lista: string[] }>;
}

interface LegalDocumentProps {
  titulo: string;
  atualizadoEm: string;
  resumo: string;
  secoes: LegalSection[];
  rodape?: ReactNode;
}

export default function LegalDocument({
  titulo,
  atualizadoEm,
  resumo,
  secoes,
  rodape,
}: LegalDocumentProps) {
  return (
    <section className="py-16">
      <article className="max-w-3xl mx-auto px-4">
        <header className="mb-10">
          <h1 className="text-2xl md:text-3xl font-bold text-text-main">{titulo}</h1>
          <p className="mt-2 text-sm text-text-muted">{atualizadoEm}</p>
          <p className="mt-4 text-text-body leading-relaxed">{resumo}</p>
        </header>

        {secoes.map((secao) => (
          <section key={secao.titulo} className="mb-8">
            <h2 className="text-lg font-semibold text-text-main mb-3">{secao.titulo}</h2>

            {secao.blocos.map((bloco, i) =>
              typeof bloco === 'string' ? (
                <p
                  key={i}
                  className="text-text-body leading-relaxed mb-3"
                  dangerouslySetInnerHTML={{ __html: bloco }}
                />
              ) : (
                <ul key={i} className="list-disc pl-5 mb-3 space-y-1.5">
                  {bloco.lista.map((item, j) => (
                    <li
                      key={j}
                      className="text-text-body leading-relaxed"
                      dangerouslySetInnerHTML={{ __html: item }}
                    />
                  ))}
                </ul>
              ),
            )}
          </section>
        ))}

        {rodape ? <footer className="mt-10 text-sm text-text-muted">{rodape}</footer> : null}
      </article>
    </section>
  );
}
