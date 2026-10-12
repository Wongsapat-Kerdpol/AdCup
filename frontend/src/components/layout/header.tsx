"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LogOut, Menu, Plus, Search, Settings, Wallet, X } from "lucide-react";
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

/** Jumps to Discover with ?q=. Hidden on Discover itself, which has its own search box. */
function HeaderSearch({ className }: { className?: string }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  return (
    <form
      role="search"
      className={cn("relative", className)}
      onSubmit={(e) => {
        e.preventDefault();
        router.push(q.trim() ? `${routes.discover}?q=${encodeURIComponent(q.trim())}` : routes.discover);
      }}
    >
      <Search className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-muted-foreground" />
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search campaigns"
        aria-label="Search campaigns"
        className="h-10 w-full rounded-full border border-input bg-muted/60 pr-4 pl-10 text-sm outline-none placeholder:text-muted-foreground focus:border-ring focus:bg-card"
      />
    </form>
  );
}

export function Header() {
  const { user, loading, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);

  const links = navByRole[user?.role ?? "guest"];
  const showSearch = !pathname.startsWith(routes.discover);
  // Longest matching link wins, so /admin/review doesn't also light up "Analytics" (/admin).
  const activeHref = links
    .map((l) => l.href)
    .filter((h) => pathname === h || pathname.startsWith(h + "/"))
    .sort((a, b) => b.length - a.length)[0];

  function handleLogout() {
    logout();
    toast.success("Signed out");
    router.push(routes.discover);
  }

  return (
    <header className="sticky top-0 z-40 border-b bg-card">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-4">
        <Logo />

        {showSearch && <HeaderSearch className="hidden max-w-md flex-1 lg:block" />}

        <nav className={cn("hidden h-full items-stretch gap-5 md:flex", !showSearch && "flex-1")}>
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={cn(
                "flex items-center border-b-2 border-transparent text-sm font-semibold text-muted-foreground transition-colors hover:text-foreground",
                l.href === activeHref && "border-brand text-foreground",
              )}
            >
              {l.label}
            </Link>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-3">
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
                <button className="flex items-center gap-2 rounded-full py-1 pr-1 pl-1 text-sm font-semibold hover:bg-accent sm:pr-3">
                  <span className="flex size-8 items-center justify-center rounded-full bg-foreground text-xs font-bold text-background">
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
              <Link
                href={`${routes.register}?role=brand`}
                className="hidden text-sm font-semibold text-muted-foreground hover:text-foreground sm:inline"
              >
                For Brands
              </Link>
              <Link href={routes.login} className="text-sm font-semibold text-muted-foreground hover:text-foreground">
                Sign in
              </Link>
              <Button
                asChild
                size="sm"
                variant="outline"
                className="border-primary text-primary hover:bg-primary hover:text-primary-foreground"
              >
                <Link href={routes.register}>Join</Link>
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
          {showSearch && <HeaderSearch className="mb-2" />}
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              onClick={() => setOpen(false)}
              className={cn(
                "rounded-md px-3 py-2 text-sm font-semibold text-muted-foreground",
                l.href === activeHref && "bg-accent text-foreground",
              )}
            >
              {l.label}
            </Link>
          ))}
          {user?.role === "brand" && (
            <Link
              href={routes.newCampaign}
              onClick={() => setOpen(false)}
              className="rounded-md px-3 py-2 text-sm font-semibold text-primary"
            >
              + New campaign
            </Link>
          )}
        </nav>
      )}
    </header>
  );
}
