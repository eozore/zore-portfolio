// apps/web/src/middleware.ts

import { NextRequest, NextResponse } from 'next/server';

const LOCALES = ['pt-BR', 'en'] as const;
const DEFAULT_LOCALE = 'pt-BR';

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Ignore API routes, static assets, and dev files
  if (
    pathname.startsWith('/api') ||
    pathname.startsWith('/admin') ||
    pathname.startsWith('/_next') ||
    pathname.includes('.')
  ) {
    return NextResponse.next();
  }

  // Check locale prefix
  const hasLocale = LOCALES.some(
    (locale) => pathname.startsWith(`/${locale}/`) || pathname === `/${locale}`
  );

  // Normalize path by removing locale prefix for easier matching
  let normalizedPath = pathname;
  let activeLocale = DEFAULT_LOCALE;

  for (const locale of LOCALES) {
    if (pathname.startsWith(`/${locale}/`)) {
      normalizedPath = pathname.slice(`/${locale}`.length);
      activeLocale = locale;
      break;
    } else if (pathname === `/${locale}`) {
      normalizedPath = '/';
      activeLocale = locale;
      break;
    }
  }

  // Get user session cookie
  const sessionCookie = request.cookies.get('eozore_session')?.value;
  let userSession: any = null;

  if (sessionCookie) {
    try {
      userSession = JSON.parse(decodeURIComponent(sessionCookie));
    } catch (e) {
      // Invalid cookie format
    }
  }

  // Route protection rules:
  // 1. /tools/cromex (Private Tool for Cromex tenant)
  if (normalizedPath.startsWith('/tools/cromex')) {
    const isCromexUser = userSession && (userSession.companyId === 'cromex' || userSession.role === 'admin');
    if (!isCromexUser) {
      const loginUrl = new URL(`/${activeLocale}/tools/login`, request.url);
      loginUrl.searchParams.set('redirect', `tools/cromex`);
      return NextResponse.redirect(loginUrl);
    }
  }

  // 2. /tools/login (Redirect to /tools if already logged in)
  if (normalizedPath === '/tools/login') {
    if (userSession) {
      return NextResponse.redirect(new URL(`/${activeLocale}/tools`, request.url));
    }
  }

  // General locale rewrite if no prefix
  if (!hasLocale) {
    return NextResponse.rewrite(
      new URL(`/${DEFAULT_LOCALE}${pathname}`, request.url)
    );
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico|image|.*\\..*).*)'],
};
