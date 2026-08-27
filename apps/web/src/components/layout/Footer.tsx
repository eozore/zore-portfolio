import Link from 'next/link';
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
        <div className="flex flex-col sm:flex-row items-center gap-x-4 gap-y-2 text-sm text-text-muted">
          <p>
            © {year} Victor Zoré. {dictionary.rights}
          </p>
          {/* Privacidade e Termos ficam no rodapé de TODAS as páginas porque o
              Google exige que sejam acessíveis para publicar a tela de
              consentimento OAuth — e o revisor procura navegando, não pelo
              sitemap. Sem a tela publicada, o refresh token do YouTube expira
              a cada 7 dias e a publicação da pipeline quebra sozinha. */}
          <span className="flex items-center gap-4">
            <Link href={`/${locale}/privacy`} className="hover:text-text-main transition-colors">
              {locale === 'pt-BR' ? 'Privacidade' : 'Privacy'}
            </Link>
            <Link href={`/${locale}/terms`} className="hover:text-text-main transition-colors">
              {locale === 'pt-BR' ? 'Termos' : 'Terms'}
            </Link>
          </span>
        </div>
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
