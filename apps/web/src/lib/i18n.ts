import type { Dictionary, Locale } from '@/types/i18n';
import ptBR from '@/data/dictionaries/pt-BR.json';
import en from '@/data/dictionaries/en.json';

export const LOCALES: Locale[] = ['pt-BR', 'en'];
export const DEFAULT_LOCALE: Locale = 'pt-BR';

const dictionaries: Record<Locale, Dictionary> = {
  'pt-BR': ptBR as Dictionary,
  en: en as Dictionary,
};

/**
 * Returns the dictionary for the given locale.
 * Falls back to pt-BR if the locale is not recognized.
 */
export function getDictionary(locale: Locale): Dictionary {
  return dictionaries[locale] ?? dictionaries[DEFAULT_LOCALE];
}

/**
 * Given a current path that includes a locale prefix, returns the equivalent
 * path in the target locale.
 *
 * Examples:
 *   getAlternateUrl('/pt-BR/blog', 'en') → '/en/blog'
 *   getAlternateUrl('/en/blog/my-post', 'pt-BR') → '/pt-BR/blog/my-post'
 *   getAlternateUrl('/pt-BR', 'en') → '/en'
 */
export function getAlternateUrl(
  currentPath: string,
  targetLocale: Locale
): string {
  // Find and replace the locale segment in the path
  for (const locale of LOCALES) {
    if (
      currentPath === `/${locale}` ||
      currentPath.startsWith(`/${locale}/`)
    ) {
      const rest = currentPath.slice(`/${locale}`.length);
      return `/${targetLocale}${rest}`;
    }
  }

  // If no locale prefix found, prepend target locale
  const normalizedPath = currentPath.startsWith('/')
    ? currentPath
    : `/${currentPath}`;
  return `/${targetLocale}${normalizedPath}`;
}

/**
 * Generates hreflang tag data for a given path (without locale prefix).
 * Returns an array of objects with locale and full URL for each supported locale.
 *
 * Example:
 *   generateHreflangTags('/blog') → [
 *     { locale: 'pt-BR', url: '/pt-BR/blog' },
 *     { locale: 'en', url: '/en/blog' },
 *   ]
 */
export function generateHreflangTags(
  path: string
): Array<{ locale: string; url: string }> {
  // Strip any existing locale prefix to get the raw path
  let rawPath = path;
  for (const locale of LOCALES) {
    if (path === `/${locale}` || path.startsWith(`/${locale}/`)) {
      rawPath = path.slice(`/${locale}`.length) || '/';
      break;
    }
  }

  // Ensure rawPath starts with /
  if (!rawPath.startsWith('/')) {
    rawPath = `/${rawPath}`;
  }

  // For root path, don't double-slash
  const suffix = rawPath === '/' ? '' : rawPath;

  return LOCALES.map((locale) => ({
    locale,
    url: `/${locale}${suffix}`,
  }));
}
