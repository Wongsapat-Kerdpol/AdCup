"use client";

// [PERSON 1] Loads a campaign for /brand/campaigns/[id]/edit and hands it to <CampaignForm>.

import { useEffect, useState } from "react";
import Link from "next/link";

import { CampaignForm } from "@/components/brand/campaign-form";
import { useAuth } from "@/components/providers/auth-provider";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import { routes } from "@/lib/routes";
import type { CampaignDetail } from "@/lib/types";

export function EditCampaign({ campaignId }: { campaignId: string }) {
  const { user } = useAuth();
  const [campaign, setCampaign] = useState<CampaignDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<CampaignDetail>(`/api/campaigns/${campaignId}`)
      .then(setCampaign)
      .catch((err) => setError(err instanceof ApiError && err.status === 404 ? "Campaign not found." : err.message));
  }, [campaignId]);

  if (error) return <Notice text={error} />;
  if (!campaign || !user) return <Skeleton className="mx-auto my-6 h-[600px] max-w-6xl rounded-xl" />;
  if (campaign.brand.id !== user.id) return <Notice text="You can only edit campaigns you created." />;
  if (campaign.status === "completed") return <Notice text="Completed campaigns can't be edited." />;
  return <CampaignForm campaign={campaign} />;
}

function Notice({ text }: { text: string }) {
  return (
    <div className="mx-auto max-w-md space-y-3 py-16 text-center">
      <h1 className="text-xl font-bold">Can&apos;t edit this campaign</h1>
      <p className="text-sm text-muted-foreground">{text}</p>
      <Button asChild variant="outline">
        <Link href={routes.brandCampaigns}>My campaigns</Link>
      </Button>
    </div>
  );
}
