import type { Metadata } from "next";

import { RequireAuth } from "@/components/auth/require-auth";
import { EditCampaign } from "@/components/brand/edit-campaign";

export const metadata: Metadata = { title: "Edit campaign" };

// [PERSON 1] Edit own campaign. PATCH /api/brand/campaigns/{id}
export default async function EditCampaignPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <RequireAuth roles={["brand"]}>
      <EditCampaign campaignId={id} />
    </RequireAuth>
  );
}
