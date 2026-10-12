import Link from "next/link";

import { Logo } from "@/components/layout/logo";
import { routes } from "@/lib/routes";

const columns: { title: string; links: { href: string; label: string }[] }[] = [
  {
    title: "Categories",
    links: [
      { href: `${routes.discover}?category=logo`, label: "Logo placement" },
      { href: `${routes.discover}?category=music`, label: "Music" },
      { href: `${routes.discover}?category=clipping`, label: "Clipping" },
      { href: `${routes.discover}?category=ugc`, label: "UGC" },
    ],
  },
  {
    title: "For Creators",
    links: [
      { href: `${routes.register}?role=creator`, label: "Start earning" },
      { href: routes.discover, label: "Browse campaigns" },
    ],
  },
  {
    title: "For Brands",
    links: [
      { href: `${routes.register}?role=brand`, label: "Create a brand account" },
      { href: routes.newCampaign, label: "Post a campaign" },
    ],
  },
];

export function Footer() {
  return (
    <footer className="mt-16 border-t bg-card">
      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-10 sm:grid-cols-2 lg:grid-cols-4">
        <div className="space-y-3">
          <Logo />
          <p className="max-w-xs text-sm text-muted-foreground">
            Brands post campaigns with a fixed rate per views. Creators post original videos and get paid for real results.
          </p>
        </div>
        {columns.map((col) => (
          <div key={col.title} className="space-y-3">
            <h3 className="text-sm font-bold">{col.title}</h3>
            <ul className="space-y-2 text-sm text-muted-foreground">
              {col.links.map((l) => (
                <li key={l.label}>
                  <Link href={l.href} className="hover:text-foreground hover:underline">
                    {l.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="border-t py-5 text-center text-xs text-muted-foreground">
        © {new Date().getFullYear()} AdCup · AdvComPro course project · No real money is transferred.
      </div>
    </footer>
  );
}
