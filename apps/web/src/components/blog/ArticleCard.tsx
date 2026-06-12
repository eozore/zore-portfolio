import type { Article } from '@/types/article';
import type { Locale, Dictionary } from '@/types/i18n';

interface ArticleCardProps {
  article: Article;
  locale: Locale;
  dictionary: Dictionary['blog'];
}

/**
 * Extracts a key formula from markdown content to display as preview.
 * Returns Unicode-friendly text (not raw LaTeX).
 */
function extractFormula(content: string): string | null {
  if (!content || content.length === 0) return null;
  
  // If content is short and has math symbols, use it directly (Unicode formulas)
  if (content.length <= 60 && /[Ω→ℝΣ∫∞≤≥±√πμσβ]/.test(content)) {
    return content;
  }

  // Look for block formula $$...$$ and convert common LaTeX to Unicode
  const blockMatch = content.match(/\$\$([^$]+)\$\$/);
  if (blockMatch) {
    return latexToUnicode(blockMatch[1].trim().slice(0, 60));
  }

  // Look for inline formula $...$
  const inlineMatch = content.match(/\$([^$]{3,50})\$/);
  if (inlineMatch) {
    return latexToUnicode(inlineMatch[1].trim());
  }

  return null;
}

/** Convert common LaTeX notation to Unicode for card display */
function latexToUnicode(latex: string): string {
  return latex
    .replace(/\\Omega/g, 'Ω')
    .replace(/\\rightarrow/g, '→')
    .replace(/\\mathbb\{R\}/g, 'ℝ')
    .replace(/\\sum/g, 'Σ')
    .replace(/\\int/g, '∫')
    .replace(/\\infty/g, '∞')
    .replace(/\\mu/g, 'μ')
    .replace(/\\sigma/g, 'σ')
    .replace(/\\beta/g, 'β')
    .replace(/\\hat\{([^}]+)\}/g, '$1̂')
    .replace(/\\frac\{([^}]+)\}\{([^}]+)\}/g, '$1/$2')
    .replace(/\\sqrt\{([^}]+)\}/g, '√$1')
    .replace(/\\pi/g, 'π')
    .replace(/\\leq/g, '≤')
    .replace(/\\geq/g, '≥')
    .replace(/\\text\{([^}]+)\}/g, '$1')
    .replace(/[\\{}]/g, '')
    .trim();
}

// Fallback formulas by category (Unicode, not LaTeX)
const CATEGORY_FORMULAS: Record<string, string> = {
  estatistica: 'E[X] = Σ xᵢ · P(xᵢ)',
  ml: 'ŷ = β₀ + β₁x',
  ia: 'softmax(zᵢ) = eᶻⁱ / Σeᶻʲ',
};

export default function ArticleCard({ article, locale, dictionary }: ArticleCardProps) {
  const isPublished = article.status === 'published';
  const date = new Date(article.publishedAt).toLocaleDateString(
    locale === 'pt-BR' ? 'pt-BR' : 'en-US',
    { day: '2-digit', month: 'short', year: 'numeric' }
  );

  const categoryLabels: Record<string, string> = {
    estatistica: dictionary.filters.estatistica || 'Estatística',
    ml: dictionary.filters.ml || 'ML',
    ia: dictionary.filters.ia || 'IA',
  };

  const formula = extractFormula(article.content) || CATEGORY_FORMULAS[article.category] || 'f(x)';

  const cardContent = (
    <div
      className={`group glass rounded-card-lg overflow-hidden transition-all duration-300 ${
        isPublished
          ? 'hover:bg-white/80 hover:shadow-glow-sm hover:-translate-y-1'
          : 'opacity-50 cursor-not-allowed'
      }`}
    >
      {/* Formula preview area — no images */}
      <div className="h-[90px] bg-gradient-to-br from-primary/5 to-accent-data/5 flex items-center justify-center relative">
        <span className="font-mono text-base text-text-main/70 group-hover:text-primary transition-colors">
          {formula}
        </span>
        {!isPublished && (
          <span className="absolute top-2 right-2 px-2 py-0.5 bg-text-muted/20 text-text-muted text-[0.6rem] font-bold uppercase rounded-full">
            {locale === 'pt-BR' ? 'Em breve' : 'Soon'}
          </span>
        )}
      </div>

      {/* Card content */}
      <div className="p-5">
        <span className="inline-block px-2.5 py-0.5 text-[0.65rem] font-bold uppercase tracking-wider text-primary bg-primary/10 rounded-full">
          {categoryLabels[article.category] || article.category}
        </span>
        <h3 className="mt-2 text-base font-semibold text-text-main group-hover:text-primary transition-colors">
          {article.title}
        </h3>
        <div className="mt-2 flex items-center gap-3 text-xs text-text-muted">
          <span>{date}</span>
          <span>·</span>
          <span>{article.readTime} {dictionary.readTime}</span>
        </div>
        {isPublished && (
          <p className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-primary">
            {dictionary.readMore}
            <i className="fa-solid fa-arrow-right text-xs" />
          </p>
        )}
      </div>
    </div>
  );

  if (isPublished) {
    return <a href={`/${locale}/blog/${article.slug}`}>{cardContent}</a>;
  }

  return cardContent;
}
