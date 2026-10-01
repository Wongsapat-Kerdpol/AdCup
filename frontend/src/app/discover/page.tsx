import type { Metadata } from "next";
import { Suspense } from "react";
import Link from "next/link";
import { Megaphone } from "lucide-react";

import { DiscoverView } from "@/components/discover/discover-view";
import { routes } from "@/lib/routes";

export const metadata: Metadata = { title: "Discover Campaigns" };

export default function DiscoverPage() {
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 rounded-xl border border-primary/25 bg-gradient-to-r from-primary/15 via-card to-card p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <Megaphone className="mt-0.5 size-5 shrink-0 text-primary" />
          <div>
            <p className="text-sm font-semibold">Get paid for the views you drive</p>
            <p className="text-xs text-muted-foreground">
              Pick a campaign, post an original video, submit the link. Approved posts earn from the pool — everyone is paid
              together, and if the pool runs short everyone gets the same share.
            </p>
          </div>
        </div>
        <Link href={`${routes.register}?role=creator`} className="text-sm font-medium text-primary hover:underline">
          Start earning →
        </Link>
      </div>

      <h1 className="text-2xl font-bold tracking-tight">Discover</h1>

      <Suspense>
        <DiscoverView />
      </Suspense>
    </div>
  );
}
