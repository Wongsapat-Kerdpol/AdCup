import type { Metadata } from "next";

import { CampaignDetailView } from "@/components/campaign/campaign-detail-view";

export const metadata: Metadata = { title: "Campaign" };

// [PERSON 1] Campaign detail. Data: GET /api/campaigns/{id} -> CampaignDetail
export default async function CampaignDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <CampaignDetailView campaignId={id} />;
}
