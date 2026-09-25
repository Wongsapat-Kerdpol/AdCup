// [MAIN] Route-level auth guard. Runs before protected pages render.
// - No token        -> redirect to /login?next=<path>
// - Wrong role      -> redirect to /discover
// Protected paths are configured in src/lib/routes.ts.

import { NextResponse, type NextRequest } from "next/server";

import { TOKEN_COOKIE, decodeTokenPayload } from "@/lib/auth-token";
import { matchProtectedRoute, routes } from "@/lib/routes";

export function middleware(req: NextRequest) {
  const rule = matchProtectedRoute(req.nextUrl.pathname);
  if (!rule) return NextResponse.next();

  const token = req.cookies.get(TOKEN_COOKIE)?.value;
  const payload = token ? decodeTokenPayload(token) : null;
  const expired = !payload || payload.exp * 1000 < Date.now();

  if (expired) {
    const url = new URL(routes.login, req.url);
    url.searchParams.set("next", req.nextUrl.pathname + req.nextUrl.search);
    return NextResponse.redirect(url);
  }
  if (rule.roles && !rule.roles.includes(payload.role as never)) {
    return NextResponse.redirect(new URL(routes.discover, req.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next|favicon.ico|.*\\..*).*)"],
};
