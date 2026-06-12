import { Locale } from './i18n';

export interface TimelineEntry {
  year: number;
  type: 'career' | 'education';
  title: Record<Locale, string>;
  description: Record<Locale, string>;
  position: 'left' | 'right';
}
