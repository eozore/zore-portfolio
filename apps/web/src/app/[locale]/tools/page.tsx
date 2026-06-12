import type { Metadata } from 'next';
import type { Locale } from '@/types/i18n';
import { getDictionary } from '@/lib/i18n';

interface ToolsPageProps {
  params: { locale: Locale };
}

export async function generateMetadata({
  params,
}: {
  params: { locale: Locale };
}): Promise<Metadata> {
  const { locale } = params;

  const title = locale === 'pt-BR' ? 'Tools | Victor Zoré' : 'Tools | Victor Zoré';
  const description =
    locale === 'pt-BR'
      ? 'Ferramentas de IA e ML para explorar e experimentar'
      : 'AI and ML tools to explore and experiment with';

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      url: `https://eozore.com/${locale}/tools`,
      type: 'website',
    },
    twitter: {
      card: 'summary',
      title,
      description,
    },
    alternates: {
      canonical: `/${locale}/tools`,
      languages: {
        'pt-BR': '/pt-BR/tools',
        en: '/en/tools',
        'x-default': '/pt-BR/tools',
      },
    },
  };
}

export default function ToolsPage({ params }: ToolsPageProps) {
  const { locale } = params;
  const dictionary = getDictionary(locale);

  return (
    <section className="py-16">
      <div className="max-w-container mx-auto px-4">
        {/* Section Header */}
        <div className="text-center mb-10">
          <h1 className="text-2xl md:text-3xl font-bold text-text-main">
            {dictionary.tools.title}
          </h1>
          <p className="mt-2 text-text-light">
            {locale === 'pt-BR'
              ? 'Ferramentas de IA e ML para explorar e experimentar'
              : 'AI and ML tools to explore and experiment with'}
          </p>
        </div>

        {/* Tools Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {/* Classificador de Sentimento */}
          <a
            href={`/${locale}/tools/classificador-sentimento`}
            className="bg-secondary rounded-card border border-border p-6 flex flex-col hover:-translate-y-[5px] hover:shadow-lg transition-all duration-300 group"
          >
            <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mb-4 group-hover:bg-primary/20 transition-colors">
              <i className="fa-solid fa-brain text-primary text-xl" />
            </div>
            <h3 className="text-lg font-semibold text-text-main mb-1">
              {locale === 'pt-BR' ? 'Classificador de Sentimento' : 'Sentiment Classifier'}
            </h3>
            <p className="text-sm text-text-light flex-1">
              {locale === 'pt-BR'
                ? 'Analise o sentimento de textos em português ou inglês usando NLP.'
                : 'Analyze text sentiment in Portuguese or English using NLP.'}
            </p>
            <span className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-primary">
              {locale === 'pt-BR' ? 'Experimentar' : 'Try it'}
              <i className="fa-solid fa-arrow-right text-xs" />
            </span>
          </a>

          {/* Coming Soon Placeholder */}
          <div className="bg-secondary rounded-card border-2 border-dashed border-border p-6 flex flex-col items-center justify-center text-center min-h-[220px] opacity-60">
            <div className="w-12 h-12 rounded-full bg-background flex items-center justify-center mb-4">
              <i className="fa-solid fa-flask text-text-light text-xl" />
            </div>
            <h3 className="text-base font-semibold text-text-main mb-1">
              {locale === 'pt-BR' ? 'Mais ferramentas em breve' : 'More tools coming soon'}
            </h3>
            <p className="text-xs text-text-light">
              {locale === 'pt-BR'
                ? 'Visualização de dados, clustering, predições e mais'
                : 'Data visualization, clustering, predictions and more'}
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
