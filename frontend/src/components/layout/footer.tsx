import Link from "next/link";

import { Logo } from "@/components/layout/logo";
import { routes } from "@/lib/routes";

export function Footer() {
  return (
    <footer className="mt-16 border-t">
      <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-8 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-2">
          <Logo />
          <p className="max-w-sm text-xs text-muted-foreground">
            Brands post campaigns with a fixed rate per views. Creators post original videos and get paid for real
            results.
          </p>
        </div>
        <div className="flex gap-6 text-sm text-muted-foreground">
          <Link href={routes.discover} className="hover:text-foreground">
            Discover
          </Link>
          <Link href={`${routes.register}?role=brand`} className="hover:text-foreground">
            For Brands
          </Link>
          <Link href={`${routes.register}?role=creator`} className="hover:text-foreground">
            For Creators
          </Link>
        </div>
      </div>
      <div className="border-t py-4 text-center text-xs text-muted-foreground">
        © {new Date().getFullYear()} AdCup · AdvComPro course project · No real money is transferred.
      </div>
    </footer>
  );
}
