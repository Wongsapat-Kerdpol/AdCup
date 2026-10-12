"use client";

// Right-hand "About" card on Discover. Buttons depend on who is looking.

import Link from "next/link";
import { CheckCircle2, Eye, ShieldCheck, Upload } from "lucide-react";

import { useAuth } from "@/components/providers/auth-provider";
import { Button } from "@/components/ui/button";
import { routes } from "@/lib/routes";

const steps = [
  { icon: Upload, text: "Post an original video and submit the link" },
  { icon: ShieldCheck, text: "We check it's yours and has enough views" },
  { icon: Eye, text: "An admin checks the brand's requirements" },
  { icon: CheckCircle2, text: "Earn from the pool as your views grow" },
];

export function DiscoverSidebar() {
  const { user } = useAuth();

  return (
    <aside className="space-y-4 lg:sticky lg:top-20">
      <div className="overflow-hidden rounded-lg border bg-card">
        <div className="h-10 bg-[#0e3b25]" />
        <div className="space-y-4 p-4">
          <div>
            <h2 className="font-bold">About AdCup</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Brands fund a pool and set a rate per view. Creators post videos and get paid for the views they bring in.
            </p>
          </div>

          <ol className="space-y-2.5">
            {steps.map((s) => (
              <li key={s.text} className="flex items-start gap-2.5 text-sm">
                <s.icon className="mt-0.5 size-4 shrink-0 text-primary" />
                {s.text}
              </li>
            ))}
          </ol>

          <div className="space-y-2 border-t pt-4">
            {!user && (
              <>
                <Button asChild className="w-full">
                  <Link href={`${routes.register}?role=creator`}>Start earning</Link>
                </Button>
                <Button asChild variant="outline" className="w-full">
                  <Link href={`${routes.register}?role=brand`}>Post a campaign</Link>
                </Button>
              </>
            )}
            {user?.role === "creator" && (
              <Button asChild className="w-full">
                <Link href={routes.submissions}>My submissions</Link>
              </Button>
            )}
            {user?.role === "brand" && (
              <>
                <Button asChild className="w-full">
                  <Link href={routes.newCampaign}>Post a campaign</Link>
                </Button>
                <Button asChild variant="outline" className="w-full">
                  <Link href={routes.brandCampaigns}>My campaigns</Link>
                </Button>
              </>
            )}
            {user?.role === "admin" && (
              <Button asChild className="w-full">
                <Link href={routes.adminReview}>Review queue</Link>
              </Button>
            )}
          </div>
        </div>
      </div>

      <p className="px-1 text-xs text-muted-foreground">
        Everyone approved is paid together. If a pool runs short, everyone gets the same share.
      </p>
    </aside>
  );
}
