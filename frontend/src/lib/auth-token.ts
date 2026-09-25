// JWT lives in a cookie (not localStorage) so src/middleware.ts can see it for route guarding.
// The backend is the real authority — it verifies the signature on every request.

export const TOKEN_COOKIE = "adcup_token";

export function getToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${TOKEN_COOKIE}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

export function setToken(token: string, maxAgeSeconds = 60 * 60 * 24 * 7) {
  document.cookie = `${TOKEN_COOKIE}=${encodeURIComponent(token)}; path=/; max-age=${maxAgeSeconds}; samesite=lax`;
}

export function clearToken() {
  document.cookie = `${TOKEN_COOKIE}=; path=/; max-age=0; samesite=lax`;
}

/** Reads the (unverified) payload. Only for UI decisions — never trust it for security. */
export function decodeTokenPayload(token: string): { sub: string; role: string; exp: number } | null {
  try {
    const part = token.split(".")[1];
    const json = atob(part.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json);
  } catch {
    return null;
  }
}
