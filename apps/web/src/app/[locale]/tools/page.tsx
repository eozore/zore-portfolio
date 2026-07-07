import type { Metadata } from 'next';
import { cookies } from 'next/headers';
import type { Locale } from '@/types/i18n';
import { getDictionary } from '@/lib/i18n';
import ToolsClientPage from '@/components/tools/ToolsClientPage';

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

  // Read session cookie server-side (prevents layout shift)
  const cookieStore = cookies();
  const sessionCookie = cookieStore.get('eozore_session')?.value;
  let userSession: any = null;

  if (sessionCookie) {
    try {
      userSession = JSON.parse(decodeURIComponent(sessionCookie));
    } catch (e) {
      // Ignore parsing errors
    }
  }

  return (
    <section className="py-16">
      <ToolsClientPage 
        locale={locale} 
        initialSession={userSession} 
        dictionary={dictionary} 
      />
    </section>
  );
}
