import type { Metadata } from 'next';
import type { Locale } from '@/types/i18n';
import { getDictionary, LOCALES } from '@/lib/i18n';
import Header from '@/components/layout/Header';
import Footer from '@/components/layout/Footer';
import LanguageSwitcher from '@/components/layout/LanguageSwitcher';
import FloatingWhatsApp from '@/components/ui/FloatingWhatsApp';
import GlobalBackground from '@/components/layout/GlobalBackground';

interface LocaleLayoutProps {
  children: React.ReactNode;
  params: { locale: Locale };
}

export async function generateMetadata({
  params,
}: {
  params: { locale: Locale };
}): Promise<Metadata> {
  const { locale } = params;
  const dictionary = getDictionary(locale);

  const title =
    locale === 'pt-BR'
      ? 'Victor Zoré - Portfólio'
      : 'Victor Zoré - Portfolio';
  const description =
    locale === 'pt-BR'
      ? 'Portfólio de Victor Zoré — Líder na área de ML & AI. Soluções com inteligência artificial para problemas reais de negócio.'
      : 'Victor Zoré Portfolio — ML & AI Leader. Artificial intelligence solutions for real business problems.';

  const alternates: Record<string, string> = {};
  for (const loc of LOCALES) {
    alternates[loc] = `/${loc}`;
  }

  return {
    title: {
      template: '%s | Victor Zoré',
      default: title,
    },
    description,
    metadataBase: new URL('https://eozore.com'),
    alternates: {
      canonical: `/${locale}`,
      languages: {
        ...alternates,
        'x-default': '/pt-BR',
      },
    },
  };
}

export async function generateStaticParams() {
  return LOCALES.map((locale) => ({ locale }));
}

export default function LocaleLayout({ children, params }: LocaleLayoutProps) {
  const { locale } = params;
  const dictionary = getDictionary(locale);

  return (
    <div lang={locale} className="relative">
      {/* Global particle network + blobs — visible across all pages */}
      <GlobalBackground />

      {/* Content above background */}
      <div className="relative z-10">
        <Header locale={locale} dictionary={dictionary.nav} />
        <main>{children}</main>
        <Footer locale={locale} dictionary={dictionary.footer} />
      </div>

      <LanguageSwitcher locale={locale} />
      <FloatingWhatsApp />
    </div>
  );
}
