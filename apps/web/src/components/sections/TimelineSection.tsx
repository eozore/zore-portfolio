'use client';

import { useEffect, useRef, useState } from 'react';
import type { Locale, Dictionary } from '@/types/i18n';
import type { TimelineEntry } from '@/types/timeline';

interface TimelineSectionProps {
  locale: Locale;
  dictionary: Dictionary['timeline'];
  entries: TimelineEntry[];
}

function TimelineItem({ entry, locale, dictionary, index, isVisible }: {
  entry: TimelineEntry;
  locale: Locale;
  dictionary: Dictionary['timeline'];
  index: number;
  isVisible: boolean;
}) {
  const isLeft = index % 2 === 0;

  return (
    <div className={`flex items-start gap-4 md:gap-8 ${isLeft ? 'md:flex-row' : 'md:flex-row-reverse'}`}>
      {/* Card */}
      <div
        className={`flex-1 transition-all duration-700 ${
          isVisible
            ? 'opacity-100 translate-y-0'
            : `opacity-0 ${isLeft ? '-translate-x-8' : 'translate-x-8'} translate-y-4`
        }`}
        style={{ transitionDelay: `${index * 100}ms` }}
      >
        <div className="glass rounded-card p-5 hover:bg-white/80 hover:shadow-glow-sm transition-all duration-300">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-lg font-bold text-primary">{entry.year}</span>
            <span className="text-[0.6rem] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-primary/10 text-primary">
              {entry.type === 'career' ? dictionary.career : dictionary.education}
            </span>
          </div>
          <h4 className="text-sm font-semibold text-text-main">{entry.title[locale]}</h4>
          <p className="mt-1 text-xs text-text-muted leading-relaxed">{entry.description[locale]}</p>
        </div>
      </div>

      {/* Center dot — visible on md+ */}
      <div className="hidden md:flex flex-col items-center shrink-0">
        <div className={`w-4 h-4 rounded-full border-[3px] transition-all duration-500 ${
          isVisible
            ? 'border-primary bg-bg-deep scale-100'
            : 'border-border bg-bg-deep scale-75'
        }`} />
      </div>

      {/* Empty space for alternation */}
      <div className="hidden md:block flex-1" />
    </div>
  );
}

export default function TimelineSection({ locale, dictionary, entries }: TimelineSectionProps) {
  const sectionRef = useRef<HTMLDivElement>(null);
  const [visibleItems, setVisibleItems] = useState<Set<number>>(new Set());

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const idx = Number(entry.target.getAttribute('data-index'));
            setVisibleItems((prev) => new Set([...prev, idx]));
          }
        });
      },
      { threshold: 0.3, rootMargin: '0px 0px -50px 0px' }
    );

    const items = sectionRef.current?.querySelectorAll('[data-index]');
    items?.forEach((item) => observer.observe(item));

    return () => observer.disconnect();
  }, []);

  return (
    <section id="timeline" className="relative py-24 overflow-visible">
      <div className="relative z-10 max-w-container mx-auto px-4">
        <div className="text-center mb-14">
          <h2 className="text-3xl md:text-4xl font-bold text-text-main">{dictionary.title}</h2>
          <p className="mt-3 text-text-muted text-lg">{dictionary.subtitle}</p>
        </div>

        {/* Vertical timeline */}
        <div ref={sectionRef} className="relative max-w-4xl mx-auto">
          {/* Vertical line — center on desktop, left on mobile */}
          <div className="absolute top-0 bottom-0 left-4 md:left-1/2 w-[2px] bg-gradient-to-b from-primary/30 via-primary/10 to-transparent md:-translate-x-[1px]" />

          {/* Timeline items */}
          <div className="space-y-8 md:space-y-12 pl-10 md:pl-0">
            {entries.map((entry, i) => (
              <div key={`${entry.year}-${i}`} data-index={i}>
                <TimelineItem
                  entry={entry}
                  locale={locale}
                  dictionary={dictionary}
                  index={i}
                  isVisible={visibleItems.has(i)}
                />
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
