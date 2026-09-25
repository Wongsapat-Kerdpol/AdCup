"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LogOut, Menu, Plus, Settings, Wallet, X } from "lucide-react";
import { toast } from "sonner";

import { Logo } from "@/components/layout/logo";
import { useAuth } from "@/components/providers/auth-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { navByRole, routes } from "@/lib/routes";
import { cn, formatTHB } from "@/lib/utils";

export function Header() {
  const { user, loading, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);

  const links = navByRole[user?.role ?? "guest"];

  function handleLogout() {
    logout();
    toast.success("Signed out");
    router.push(routes.discover);
  }

  return (
    <header className="sticky top-0 z-40 border-b bg-background/85 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-4">
        <Logo />

        <nav className="hidden items-center gap-1 md:flex">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground",
                pathname.startsWith(l.href) && "bg-accent text-foreground",
              )}
            >
              {l.label}
            </Link>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          {user?.role === "brand" && (
            <Button asChild size="sm" className="hidden sm:inline-flex">
              <Link href={routes.newCampaign}>
                <Plus /> New campaign
              </Link>
            </Button>
          )}

          {loading ? null : user ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="flex items-center gap-2 rounded-full border py-1 pr-3 pl-1 text-sm hover:bg-accent">
                  <span className="flex size-7 items-center justify-center rounded-full bg-primary/20 text-xs font-semibold text-primary">
                    {user.display_name.slice(0, 1).toUpperCase()}
                  </span>
                  <span className="hidden max-w-32 truncate sm:inline">{user.display_name}</span>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel className="flex flex-col gap-1">
                  <span className="truncate">{user.display_name}</span>
                  <span className="truncate text-xs font-normal text-muted-foreground">{user.email}</span>
                  <Badge variant="secondary" className="capitalize">
                    {user.role}
                  </Badge>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                {user.role === "creator" && (
                  <DropdownMenuItem asChild>
                    <Link href={routes.wallet}>
                      <Wallet /> Wallet
                      <span className="ml-auto text-xs text-muted-foreground">{formatTHB(user.wallet_balance)}</span>
                    </Link>
                  </DropdownMenuItem>
                )}
                <DropdownMenuItem asChild>
                  <Link href={routes.settings}>
                    <Settings /> Settings
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={handleLogout}>
                  <LogOut /> Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <>
              <Button asChild variant="outline" size="sm" className="hidden rounded-full sm:inline-flex">
                <Link href={`${routes.register}?role=brand`}>For Brands</Link>
              </Button>
              <Button asChild size="sm" className="rounded-full">
                <Link href={routes.login}>Sign in</Link>
              </Button>
            </>
          )}

          <Button variant="ghost" size="icon" className="md:hidden" onClick={() => setOpen((o) => !o)} aria-label="Menu">
            {open ? <X /> : <Menu />}
          </Button>
        </div>
      </div>

      {open && (
        <nav className="flex flex-col gap-1 border-t px-4 py-3 md:hidden">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              onClick={() => setOpen(false)}
              className={cn(
                "rounded-md px-3 py-2 text-sm text-muted-foreground",
                pathname.startsWith(l.href) && "bg-accent text-foreground",
              )}
            >
              {l.label}
            </Link>
          ))}
          {user?.role === "brand" && (
            <Link href={routes.newCampaign} onClick={() => setOpen(false)} className="rounded-md px-3 py-2 text-sm text-primary">
              + New campaign
            </Link>
          )}
        </nav>
      )}
    </header>
  );
}
