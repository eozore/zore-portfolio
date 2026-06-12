import type { Dictionary } from '@/types/i18n';
import type { Locale } from '@/types/i18n';

interface HeaderProps {
  locale: Locale;
  dictionary: Dictionary['nav'];
}

export default function Header({ locale, dictionary }: HeaderProps) {
  return (
    <header className="sticky top-0 z-50 glass-strong">
      <div className="max-w-container mx-auto px-4 h-16 flex items-center justify-between">
        <a href={`/${locale}`} className="text-xl font-bold text-text-main hover:text-primary transition-colors">
          éozoré<span className="text-primary">.</span>
        </a>
        <nav className="hidden md:flex items-center gap-6 text-sm font-medium">
          <a href={`/${locale}`} className="text-text-muted hover:text-text-main transition-colors">{dictionary.home}</a>
          <a href={`/${locale}#projetos`} className="text-text-muted hover:text-text-main transition-colors">{dictionary.projects}</a>
          <a href={`/${locale}#timeline`} className="text-text-muted hover:text-text-main transition-colors">{dictionary.timeline}</a>
          <a href={`/${locale}/blog`} className="text-text-muted hover:text-text-main transition-colors">{dictionary.blog}</a>
          <a href={`/${locale}/tools`} className="text-text-muted hover:text-text-main transition-colors">{dictionary.tools}</a>
        </nav>
      </div>
    </header>
  );
}
