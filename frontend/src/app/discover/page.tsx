import type { Metadata } from "next";
import { Suspense } from "react";
import Link from "next/link";

import { DiscoverSidebar } from "@/components/discover/discover-sidebar";
import { DiscoverView } from "@/components/discover/discover-view";
import { routes } from "@/lib/routes";

export const metadata: Metadata = { title: "Discover Campaigns" };

const quickLinks = [
  { label: "Logo placement", category: "logo" },
  { label: "Music", category: "music" },
  { label: "Clipping", category: "clipping" },
  { label: "UGC", category: "ugc" },
];

export default function DiscoverPage() {
  return (
    <div className="space-y-6">
      <section className="rounded-xl bg-[#0e3b25] px-6 py-8 text-white sm:px-10 sm:py-10">
        <h1 className="max-w-3xl text-3xl leading-tight font-bold text-balance sm:text-4xl">
          Get paid for the views your videos bring in
        </h1>
        <p className="mt-2 max-w-xl text-sm text-white/75 sm:text-base">
          Pick a campaign, post an original video, submit the link — approved posts earn from the brand&apos;s pool.
        </p>
        <div className="mt-5 flex flex-wrap gap-2">
          {quickLinks.map((q) => (
            <Link
              key={q.category}
              href={`${routes.discover}?category=${q.category}`}
              className="rounded-full border border-white/30 px-3.5 py-1.5 text-sm font-semibold transition-colors hover:bg-white hover:text-[#0e3b25]"
            >
              {q.label}
            </Link>
          ))}
        </div>
      </section>

      <div className="grid items-start gap-6 lg:grid-cols-[1fr_300px]">
        <Suspense>
          <DiscoverView />
        </Suspense>
        <DiscoverSidebar />
      </div>
    </div>
  );
}
