"use client";

// [MAIN] Client-side guard for components/pages. middleware.ts already blocks protected
// routes; wrap page content with this too so it waits for the user to load.
//   <RequireAuth roles={["brand"]}> ... </RequireAuth>

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { useAuth } from "@/components/providers/auth-provider";
import { routes } from "@/lib/routes";
import type { UserRole } from "@/lib/types";

export function RequireAuth({ roles, children }: { roles?: UserRole[]; children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const allowed = !!user && (!roles || roles.includes(user.role));

  useEffect(() => {
    if (loading) return;
    if (!user) router.replace(`${routes.login}?next=${encodeURIComponent(pathname)}`);
    else if (!allowed) router.replace(routes.discover);
  }, [loading, user, allowed, pathname, router]);

  if (!allowed) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-muted-foreground">
        <Loader2 className="size-5 animate-spin" />
      </div>
    );
  }
  return <>{children}</>;
}
