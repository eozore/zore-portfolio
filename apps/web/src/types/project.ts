import { Locale } from './i18n';

export interface Project {
  id: string;
  title: Record<Locale, string>;
  description: Record<Locale, string>;
  category: 'ai' | 'ml';
  technologies: string[];
  image: string;
  link?: string;
}
