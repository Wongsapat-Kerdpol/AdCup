"use client";

// [MAIN] One-click login as a seeded user so every module can be tested before real auth exists.
// Backend endpoint only works while DEV_LOGIN_ENABLED=true.

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";

import { useAuth } from "@/components/providers/auth-provider";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { routes } from "@/lib/routes";
import type { TokenResponse, UserRole } from "@/lib/types";

const roles: UserRole[] = ["creator", "brand", "admin"];

export function DevLogin() {
  const { login } = useAuth();
  const router = useRouter();
  const next = useSearchParams().get("next");
  const [busy, setBusy] = useState<UserRole | null>(null);

  async function signIn(role: UserRole) {
    setBusy(role);
    try {
      const res = await api<TokenResponse>("/api/auth/dev-login", { method: "POST", body: { role } });
      login(res);
      toast.success(`Signed in as ${res.user.display_name}`);
      router.push(next && next.startsWith("/") ? next : routes.discover);
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="rounded-xl border bg-card p-5">
      <p className="text-sm font-medium">Developer login</p>
      <p className="mb-4 text-xs text-muted-foreground">Signs in as a seeded demo account (password123).</p>
      <div className="grid grid-cols-3 gap-2">
        {roles.map((r) => (
          <Button key={r} variant="secondary" className="capitalize" disabled={!!busy} onClick={() => signIn(r)}>
            {busy === r ? "…" : r}
          </Button>
        ))}
      </div>
    </div>
  );
}
