import type { Locale, Dictionary } from '@/types/i18n';
import type { TimelineEntry } from '@/types/timeline';

interface TimelineItemProps {
  entry: TimelineEntry;
  locale: Locale;
  dictionary: Dictionary['timeline'];
}

export default function TimelineItem({ entry, locale, dictionary }: TimelineItemProps) {
  const isLeft = entry.position === 'left';
  const typeLabel = entry.type === 'career' ? dictionary.career : dictionary.education;
  const tagColor =
    entry.type === 'career'
      ? 'bg-primary/10 text-primary'
      : 'bg-accent/20 text-accent';

  return (
    <div
      className={`
        relative flex w-full
        md:justify-${isLeft ? 'start' : 'end'}
        justify-start
      `}
    >
      {/* Desktop: position left or right of center line */}
      <div
        className={`
          w-full md:w-[calc(50%-2rem)]
          ${isLeft ? 'md:mr-auto' : 'md:ml-auto'}
          pl-8 md:pl-0 md:pr-0
        `}
      >
        <div className="bg-secondary rounded-card p-5 border border-border shadow-sm">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-sm font-bold text-text-main">
              {entry.year}
            </span>
            <span className={`px-2 py-0.5 text-xs font-medium rounded ${tagColor}`}>
              {typeLabel}
            </span>
          </div>
          <h4 className="font-semibold text-text-main">
            {entry.title[locale]}
          </h4>
          <p className="mt-1 text-sm text-text-light leading-relaxed">
            {entry.description[locale]}
          </p>
        </div>
      </div>

      {/* Dot on the timeline */}
      <div className="absolute left-0 md:left-1/2 md:-translate-x-1/2 top-6 w-3 h-3 bg-primary rounded-full border-2 border-white shadow" />
    </div>
  );
}
