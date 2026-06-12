import { NextRequest, NextResponse } from 'next/server';

const LOCALES = ['pt-BR', 'en'] as const;
const DEFAULT_LOCALE = 'pt-BR';

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Ignore API routes and static files
  if (
    pathname.startsWith('/api') ||
    pathname.startsWith('/_next') ||
    pathname.includes('.')
  ) {
    return NextResponse.next();
  }

  // Check if already has locale in path
  const hasLocale = LOCALES.some(
    (locale) => pathname.startsWith(`/${locale}/`) || pathname === `/${locale}`
  );

  if (!hasLocale) {
    // Rewrite to default locale (not redirect — keeps URL clean)
    return NextResponse.rewrite(
      new URL(`/${DEFAULT_LOCALE}${pathname}`, request.url)
    );
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico|image|.*\\..*).*)'],
};
