import type { Metadata } from "next";

import { RequireAuth } from "@/components/auth/require-auth";
import { MyCampaignsView } from "@/components/brand/my-campaigns-view";

export const metadata: Metadata = { title: "My campaigns" };

// [PERSON 1] Brand's own campaigns incl. drafts. GET /api/brand/campaigns
export default function BrandCampaignsPage() {
  return (
    <RequireAuth roles={["brand"]}>
      <MyCampaignsView />
    </RequireAuth>
  );
}
