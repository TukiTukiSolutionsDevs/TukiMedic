/**
 * Server-side route guard (Next 16 proxy.ts — replaces middleware.ts).
 *
 * Protected paths require the `tuki-auth` companion cookie (set by the
 * login flow alongside the localStorage token). Unauthenticated requests
 * are redirected to /login with the original path preserved as `?next=...`.
 *
 * The cookie holds NO secrets — it's just a "user is signed in" flag. The
 * actual access token lives in localStorage (XSS surface) and is checked
 * by the FastAPI backend, which is the real authority on auth.
 *
 * Public paths: /, /login. Everything else under the matcher requires auth.
 */
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

const PUBLIC_PATHS = new Set(['/', '/login'])
const AUTH_COOKIE = 'tuki-auth'

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl

  if (PUBLIC_PATHS.has(pathname)) return NextResponse.next()

  const authed = request.cookies.get(AUTH_COOKIE)?.value === '1'
  if (authed) return NextResponse.next()

  const loginUrl = new URL('/login', request.url)
  loginUrl.searchParams.set('next', pathname)
  return NextResponse.redirect(loginUrl)
}

export const config = {
  matcher: [
    /*
     * Match every path except:
     * - api routes (handled by the backend)
     * - Next.js internals (_next/static, _next/image)
     * - public assets (favicon, robots, sitemap)
     */
    '/((?!api|_next/static|_next/image|favicon.ico|robots.txt|sitemap.xml).*)',
  ],
}
