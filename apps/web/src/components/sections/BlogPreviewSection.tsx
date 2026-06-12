import type { Locale, Dictionary } from '@/types/i18n';

interface BlogPreviewSectionProps {
  locale: Locale;
  dictionary: Dictionary['blog'];
}

const staticPreviews = [
  {
    slug: 'variaveis-aleatorias',
    title: { 'pt-BR': 'Variáveis Aleatórias', en: 'Random Variables' },
    formula: 'X: Ω → ℝ',
    description: {
      'pt-BR': 'O alicerce de todo modelo de ML — do conceito à aplicação em produção.',
      en: 'The foundation of every ML model — from concept to production application.',
    },
    date: '01 Jun 2025',
    readTime: 8,
    category: 'Estatística',
  },
  {
    slug: 'estatisticas-basicas',
    title: { 'pt-BR': 'Estatísticas Básicas', en: 'Basic Statistics' },
    formula: 'x̄ = Σxᵢ / n',
    description: {
      'pt-BR': 'Média, mediana, IQR e por que o CEO errou confiando só na média.',
      en: 'Mean, median, IQR and why the CEO was wrong trusting only the mean.',
    },
    date: '08 Jun 2025',
    readTime: 9,
    category: 'Estatística',
  },
  {
    slug: 'probabilidade-bayesiana',
    title: { 'pt-BR': 'Probabilidade Bayesiana', en: 'Bayesian Probability' },
    formula: 'P(A|B) = P(B|A)·P(A) / P(B)',
    description: {
      'pt-BR': 'Como inverter a pergunta com Bayes — taxa base e valor preditivo.',
      en: 'How to invert the question with Bayes — base rate and predictive value.',
    },
    date: '22 Jun 2025',
    readTime: 8,
    category: 'Estatística',
  },
];

export default function BlogPreviewSection({ locale, dictionary }: BlogPreviewSectionProps) {
  return (
    <section id="blog" className="relative py-24 overflow-hidden bg-[#0f0f1a]">
      {/* Blob */}
      <div className="blob blob-primary w-[400px] h-[400px] top-10 right-0" />

      <div className="relative z-10 max-w-container mx-auto px-4">
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-bold text-white">{dictionary.title}</h2>
          <p className="mt-3 text-slate-400 text-lg">{dictionary.subtitle}</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {staticPreviews.map((post) => (
            <a
              key={post.slug}
              href={`/${locale}/blog/exemplo`}
              className="group glass rounded-card-lg overflow-hidden hover:bg-white/10 hover:shadow-glow transition-all duration-500" style={{ background: 'rgba(255,255,255,0.04)' }}
            >
              {/* Formula preview */}
              <div className="h-[100px] bg-gradient-to-br from-primary/10 to-cyan-500/10 flex items-center justify-center">
                <span className="font-mono text-lg text-white/80 group-hover:text-white transition-colors">
                  {post.formula}
                </span>
              </div>

              <div className="p-5">
                <span className="text-[0.65rem] font-bold uppercase tracking-wider text-primary">
                  {post.category}
                </span>
                <h3 className="mt-1.5 text-base font-semibold text-white group-hover:text-glow transition-colors">
                  {post.title[locale]}
                </h3>
                <div className="mt-2 flex items-center gap-3 text-xs text-slate-500">
                  <span>{post.date}</span>
                  <span>·</span>
                  <span>{post.readTime} {dictionary.readTime}</span>
                </div>
                <p className="mt-2 text-sm text-slate-400 leading-relaxed line-clamp-2">
                  {post.description[locale]}
                </p>
              </div>
            </a>
          ))}
        </div>

        {/* View all */}
        <div className="text-center mt-10">
          <a
            href={`/${locale}/blog`}
            className="inline-flex items-center gap-2 px-5 py-2.5 border border-white/20 text-white text-sm font-medium rounded-lg hover:border-primary hover:text-primary transition-all"
          >
            {locale === 'pt-BR' ? 'Ver todos os artigos' : 'View all articles'}
            <i className="fa-solid fa-arrow-right text-xs" />
          </a>
        </div>
      </div>
    </section>
  );
}
