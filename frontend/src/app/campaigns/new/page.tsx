import type { Metadata } from "next";

import { RequireAuth } from "@/components/auth/require-auth";
import { CampaignForm } from "@/components/brand/campaign-form";

export const metadata: Metadata = { title: "Create a campaign" };

// [PERSON 1] Brand-only create form. POST /api/brand/campaigns -> /campaigns/{id}/fund (Person 3).
export default function NewCampaignPage() {
  return (
    <RequireAuth roles={["brand"]}>
      <CampaignForm />
    </RequireAuth>
  );
}
