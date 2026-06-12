'use client';

import type { Locale } from '@/types/i18n';

interface LanguageSwitcherProps {
  locale: Locale;
}

export default function LanguageSwitcher({ locale }: LanguageSwitcherProps) {
  const targetLocale: Locale = locale === 'pt-BR' ? 'en' : 'pt-BR';
  const label = locale === 'pt-BR' ? 'EN' : 'PT';

  function handleSwitch() {
    const currentPath = window.location.pathname;

    // If URL already has a locale prefix, swap it
    if (currentPath.startsWith(`/${locale}/`) || currentPath === `/${locale}`) {
      const newPath = currentPath.replace(`/${locale}`, `/${targetLocale}`);
      window.location.href = newPath || `/${targetLocale}`;
    } else {
      // URL has no locale prefix (middleware rewrite) — navigate explicitly
      const pathSuffix = currentPath === '/' ? '' : currentPath;
      window.location.href = `/${targetLocale}${pathSuffix}`;
    }
  }

  return (
    <button
      onClick={handleSwitch}
      className="fixed bottom-6 left-6 z-50 w-12 h-12 rounded-full bg-primary text-white font-bold text-sm shadow-lg hover:scale-110 transition-transform flex items-center justify-center"
      aria-label={`Switch to ${targetLocale === 'en' ? 'English' : 'Português'}`}
    >
      {label}
    </button>
  );
}
