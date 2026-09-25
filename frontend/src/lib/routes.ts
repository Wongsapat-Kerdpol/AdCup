// Central route map. Used by the header nav AND by middleware.ts for the auth guard.
// Add your pages here instead of hard-coding paths.

import type { UserRole } from "@/lib/types";

export const routes = {
  home: "/",
  discover: "/discover",
  login: "/login",
  register: "/register", // Person 1
  campaign: (id: number | string) => `/campaigns/${id}`, // Person 1
  newCampaign: "/campaigns/new", // Person 1
  fundCampaign: (id: number | string) => `/campaigns/${id}/fund`, // Person 3
  brandCampaigns: "/brand/campaigns", // Person 1 (+ read-only submissions list from Person 2)
  submissions: "/submissions", // Person 2
  wallet: "/wallet", // Person 3
  settings: "/settings", // Person 3 (YouTube connect)
  admin: "/admin", // Person 3 (analytics)
  adminReview: "/admin/review", // Person 2 (round-2 review queue)
} as const;

/** Path prefixes that require login, and optionally a specific role. First match wins. */
export const protectedRoutes: { prefix: string; roles?: UserRole[] }[] = [
  { prefix: "/campaigns/new", roles: ["brand"] },
  { prefix: "/brand", roles: ["brand"] },
  { prefix: "/submissions", roles: ["creator"] },
  { prefix: "/wallet", roles: ["creator"] },
  { prefix: "/settings" },
  { prefix: "/admin", roles: ["admin"] },
];

/** /campaigns/:id/fund is dynamic, so it is matched separately. */
export function matchProtectedRoute(pathname: string) {
  if (/^\/campaigns\/[^/]+\/fund/.test(pathname)) return { prefix: pathname, roles: ["brand"] as UserRole[] };
  return protectedRoutes.find((r) => pathname === r.prefix || pathname.startsWith(r.prefix + "/"));
}

export const navByRole: Record<UserRole | "guest", { href: string; label: string }[]> = {
  guest: [{ href: routes.discover, label: "Discover" }],
  creator: [
    { href: routes.discover, label: "Discover" },
    { href: routes.submissions, label: "My Submissions" },
    { href: routes.wallet, label: "Wallet" },
  ],
  brand: [
    { href: routes.discover, label: "Discover" },
    { href: routes.brandCampaigns, label: "My Campaigns" },
  ],
  admin: [
    { href: routes.discover, label: "Discover" },
    { href: routes.adminReview, label: "Review Queue" },
    { href: routes.admin, label: "Analytics" },
  ],
};
