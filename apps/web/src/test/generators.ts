import * as fc from 'fast-check';
import { Article, ArticleCategory } from '@/types/article';
import { Locale } from '@/types/i18n';
import { Project } from '@/types/project';
import { TimelineEntry } from '@/types/timeline';

export const localeArb = fc.constantFrom<Locale>('pt-BR', 'en');
export const categoryArb = fc.constantFrom<ArticleCategory>('estatistica', 'ml', 'ia');

export const slugArb = fc.stringMatching(/^[a-z0-9-]+$/)
  .filter(s => s.length >= 1 && s.length <= 100);

export const articleArb: fc.Arbitrary<Article> = fc.record({
  id: fc.uuid(),
  title: fc.string({ minLength: 1, maxLength: 150 }),
  slug: slugArb,
  content: fc.string({ minLength: 1, maxLength: 1000 }), // reduced for test performance
  category: categoryArb,
  language: localeArb,
  publishedAt: fc.date().map(d => d.toISOString()),
  readTime: fc.integer({ min: 1, max: 120 }),
  coverImage: fc.webUrl({ withFragments: false }).map(u => u.replace('http://', 'https://')),
  createdAt: fc.date().map(d => d.toISOString()),
  status: fc.constantFrom<'published' | 'draft'>('published', 'draft'),
});

export const projectArb: fc.Arbitrary<Project> = fc.record({
  id: fc.uuid(),
  title: fc.record({ 'pt-BR': fc.string({ minLength: 1 }), en: fc.string({ minLength: 1 }) }),
  description: fc.record({ 'pt-BR': fc.string({ minLength: 1 }), en: fc.string({ minLength: 1 }) }),
  category: fc.constantFrom<'ai' | 'ml'>('ai', 'ml'),
  technologies: fc.array(fc.string({ minLength: 1 }), { minLength: 1, maxLength: 5 }),
  image: fc.constant('/image/placeholder.png'),
  link: fc.option(fc.webUrl(), { nil: undefined }),
});

export const timelineEntryArb: fc.Arbitrary<TimelineEntry> = fc.record({
  year: fc.integer({ min: 2000, max: 2030 }),
  type: fc.constantFrom<'career' | 'education'>('career', 'education'),
  title: fc.record({ 'pt-BR': fc.string({ minLength: 1 }), en: fc.string({ minLength: 1 }) }),
  description: fc.record({ 'pt-BR': fc.string({ minLength: 1 }), en: fc.string({ minLength: 1 }) }),
  position: fc.constantFrom<'left' | 'right'>('left', 'right'),
});

export const pathArb = fc.array(
  fc.stringMatching(/^[a-z0-9-]+$/),
  { minLength: 0, maxLength: 3 }
).map(segments => '/' + segments.join('/'));
