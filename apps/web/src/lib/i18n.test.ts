import { describe, it, expect } from 'vitest';
import {
  getDictionary,
  getAlternateUrl,
  generateHreflangTags,
  LOCALES,
  DEFAULT_LOCALE,
} from './i18n';

describe('getDictionary', () => {
  it('returns pt-BR dictionary for pt-BR locale', () => {
    const dict = getDictionary('pt-BR');
    expect(dict.nav.home).toBe('Home');
    expect(dict.nav.projects).toBe('Projetos');
    expect(dict.hero.greeting).toBe('Prazer, Victor Zoré!');
    expect(dict.footer.rights).toBe('Todos os direitos reservados.');
  });

  it('returns en dictionary for en locale', () => {
    const dict = getDictionary('en');
    expect(dict.nav.home).toBe('Home');
    expect(dict.nav.projects).toBe('Projects');
    expect(dict.hero.greeting).toBe("Hi, I'm Victor Zoré!");
    expect(dict.footer.rights).toBe('All rights reserved.');
  });

  it('has all required keys in both dictionaries', () => {
    for (const locale of LOCALES) {
      const dict = getDictionary(locale);
      expect(dict.nav).toBeDefined();
      expect(dict.hero).toBeDefined();
      expect(dict.projects).toBeDefined();
      expect(dict.timeline).toBeDefined();
      expect(dict.blog).toBeDefined();
      expect(dict.tools).toBeDefined();
      expect(dict.footer).toBeDefined();
    }
  });
});

describe('getAlternateUrl', () => {
  it('switches from pt-BR to en', () => {
    expect(getAlternateUrl('/pt-BR/blog', 'en')).toBe('/en/blog');
  });

  it('switches from en to pt-BR', () => {
    expect(getAlternateUrl('/en/blog', 'pt-BR')).toBe('/pt-BR/blog');
  });

  it('handles nested paths', () => {
    expect(getAlternateUrl('/pt-BR/blog/my-post', 'en')).toBe('/en/blog/my-post');
  });

  it('handles root locale path', () => {
    expect(getAlternateUrl('/pt-BR', 'en')).toBe('/en');
    expect(getAlternateUrl('/en', 'pt-BR')).toBe('/pt-BR');
  });

  it('handles path without locale prefix', () => {
    expect(getAlternateUrl('/blog', 'en')).toBe('/en/blog');
  });
});

describe('generateHreflangTags', () => {
  it('generates tags for both locales', () => {
    const tags = generateHreflangTags('/blog');
    expect(tags).toHaveLength(2);
    expect(tags).toContainEqual({ locale: 'pt-BR', url: '/pt-BR/blog' });
    expect(tags).toContainEqual({ locale: 'en', url: '/en/blog' });
  });

  it('handles root path', () => {
    const tags = generateHreflangTags('/');
    expect(tags).toHaveLength(2);
    expect(tags).toContainEqual({ locale: 'pt-BR', url: '/pt-BR' });
    expect(tags).toContainEqual({ locale: 'en', url: '/en' });
  });

  it('strips existing locale prefix before generating', () => {
    const tags = generateHreflangTags('/pt-BR/blog');
    expect(tags).toHaveLength(2);
    expect(tags).toContainEqual({ locale: 'pt-BR', url: '/pt-BR/blog' });
    expect(tags).toContainEqual({ locale: 'en', url: '/en/blog' });
  });

  it('handles nested paths', () => {
    const tags = generateHreflangTags('/blog/my-article');
    expect(tags).toHaveLength(2);
    expect(tags).toContainEqual({ locale: 'pt-BR', url: '/pt-BR/blog/my-article' });
    expect(tags).toContainEqual({ locale: 'en', url: '/en/blog/my-article' });
  });
});

describe('constants', () => {
  it('LOCALES contains pt-BR and en', () => {
    expect(LOCALES).toContain('pt-BR');
    expect(LOCALES).toContain('en');
    expect(LOCALES).toHaveLength(2);
  });

  it('DEFAULT_LOCALE is pt-BR', () => {
    expect(DEFAULT_LOCALE).toBe('pt-BR');
  });
});
