import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { localeArb, slugArb, pathArb } from './generators';

describe('Test setup validation', () => {
  it('vitest runs correctly', () => {
    expect(1 + 1).toBe(2);
  });

  it('fast-check works with custom generators', () => {
    fc.assert(
      fc.property(localeArb, (locale) => {
        return locale === 'pt-BR' || locale === 'en';
      })
    );
  });

  it('slugArb generates valid slugs', () => {
    fc.assert(
      fc.property(slugArb, (slug) => {
        return /^[a-z0-9-]+$/.test(slug) && slug.length >= 1 && slug.length <= 100;
      })
    );
  });

  it('pathArb generates valid paths', () => {
    fc.assert(
      fc.property(pathArb, (path) => {
        return path.startsWith('/');
      })
    );
  });
});
