export type Locale = 'pt-BR' | 'en';

export interface Dictionary {
  nav: { home: string; projects: string; timeline: string; blog: string; tools: string };
  hero: { greeting: string; title: string; subtitle: string; cta: string; ctaProjects: string };
  projects: { title: string; subtitle: string; tags: Record<string, string> };
  timeline: { title: string; subtitle: string; career: string; education: string };
  blog: { title: string; subtitle: string; readMore: string; readTime: string; viewAll: string; filters: Record<string, string> };
  tools: { title: string; subtitle: string };
  footer: { rights: string };
}
