import type { Locale } from '@/types/i18n';

interface YouTubeSectionProps {
  locale: Locale;
}

export default function YouTubeSection({ locale }: YouTubeSectionProps) {
  return (
    <section className="relative py-24 overflow-hidden">
      {/* Blobs */}
      <div className="blob blob-cyan w-[350px] h-[350px] -top-10 left-1/4 animate-float" style={{ animationDelay: '1s' }} />
      <div className="blob blob-primary w-[300px] h-[300px] bottom-0 right-10 animate-float" style={{ animationDelay: '3s' }} />

      <div className="relative z-10 max-w-container mx-auto px-4">
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-bold text-text-main">
            {locale === 'pt-BR' ? 'Canal YouTube' : 'YouTube Channel'}
          </h2>
          <p className="mt-3 text-text-muted text-lg">
            {locale === 'pt-BR'
              ? 'Conteúdo sobre Machine Learning e Inteligência Artificial para quem trabalha com dados'
              : 'Content about Machine Learning and Artificial Intelligence for data professionals'
            }
          </p>
        </div>

        {/* Video embed — glass card */}
        <div className="max-w-3xl mx-auto glass rounded-card-lg p-4 md:p-6">
          <div className="relative w-full aspect-video rounded-2xl overflow-hidden">
            <iframe
              width="100%"
              height="100%"
              src="https://www.youtube.com/embed/r2UrN3eGCWA?si=Ch87JhFeXS4_uZQ1"
              title="YouTube video player"
              frameBorder="0"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
              referrerPolicy="strict-origin-when-cross-origin"
              allowFullScreen
              className="absolute inset-0 w-full h-full"
            />
          </div>
          {/* CTA */}
          <div className="mt-4 text-center">
            <a
              href="https://www.youtube.com/@eozore"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium text-primary hover:text-glow transition-colors"
            >
              <i className="fa-brands fa-youtube" />
              {locale === 'pt-BR' ? 'Ver canal completo' : 'View full channel'}
              <i className="fa-solid fa-arrow-right text-xs" />
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}
