import type { Dictionary } from '@/types/i18n';
import type { Locale } from '@/types/i18n';

interface FooterProps {
  locale: Locale;
  dictionary: Dictionary['footer'];
}

export default function Footer({ locale, dictionary }: FooterProps) {
  const year = new Date().getFullYear();

  return (
    <footer className="border-t border-border bg-bg-deep py-10">
      <div className="max-w-container mx-auto px-4 flex flex-col md:flex-row items-center justify-between gap-4">
        <p className="text-sm text-text-muted">
          © {year} Victor Zoré. {dictionary.rights}
        </p>
        <div className="flex items-center gap-5 text-text-muted">
          <a href="https://github.com/eozore" target="_blank" rel="noopener noreferrer" className="hover:text-text-main transition-colors" aria-label="GitHub">
            <i className="fa-brands fa-github text-lg" />
          </a>
          <a href="https://www.linkedin.com/in/victor-zor%C3%A9/" target="_blank" rel="noopener noreferrer" className="hover:text-text-main transition-colors" aria-label="LinkedIn">
            <i className="fa-brands fa-linkedin text-lg" />
          </a>
          <a href="https://www.youtube.com/@eozore" target="_blank" rel="noopener noreferrer" className="hover:text-text-main transition-colors" aria-label="YouTube">
            <i className="fa-brands fa-youtube text-lg" />
          </a>
        </div>
      </div>
    </footer>
  );
}
