import type { Metadata } from 'next';
import type { Locale } from '@/types/i18n';
import { getDictionary } from '@/lib/i18n';
import { projects } from '@/data/projects';
import { timelineEntries } from '@/data/timeline';
import HeroSection from '@/components/sections/HeroSection';
import ProjectsSection from '@/components/sections/ProjectsSection';
import TimelineSection from '@/components/sections/TimelineSection';
import YouTubeSection from '@/components/sections/YouTubeSection';
import BlogPreviewSection from '@/components/sections/BlogPreviewSection';

interface HomePageProps {
  params: { locale: Locale };
}

export async function generateMetadata({
  params,
}: {
  params: { locale: Locale };
}): Promise<Metadata> {
  const { locale } = params;

  const title =
    locale === 'pt-BR'
      ? 'Victor Zoré - Portfólio | ML & AI'
      : 'Victor Zoré - Portfolio | ML & AI';
  const description =
    locale === 'pt-BR'
      ? 'Portfólio de Victor Zoré — Líder na área de ML & AI. Soluções com inteligência artificial para problemas reais de negócio.'
      : 'Victor Zoré Portfolio — ML & AI Leader. Artificial intelligence solutions for real business problems.';

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      url: `https://eozore.com/${locale}`,
      type: 'website',
    },
    twitter: {
      card: 'summary_large_image',
      title,
      description,
    },
    alternates: {
      canonical: `/${locale}`,
      languages: {
        'pt-BR': '/pt-BR',
        en: '/en',
        'x-default': '/pt-BR',
      },
    },
  };
}

export default function HomePage({ params }: HomePageProps) {
  const { locale } = params;
  const dictionary = getDictionary(locale);

  return (
    <>
      <HeroSection locale={locale} dictionary={dictionary.hero} />
      <ProjectsSection
        locale={locale}
        dictionary={dictionary.projects}
        projects={projects}
      />
      <TimelineSection
        locale={locale}
        dictionary={dictionary.timeline}
        entries={timelineEntries}
      />
      <YouTubeSection locale={locale} />
      <BlogPreviewSection locale={locale} dictionary={dictionary.blog} />
    </>
  );
}
