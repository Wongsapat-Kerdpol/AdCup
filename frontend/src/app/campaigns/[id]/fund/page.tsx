import type { Metadata } from "next";

import { RequireAuth } from "@/components/auth/require-auth";
import { FundCheckout } from "@/components/payment/fund-checkout";

export const metadata: Metadata = { title: "Fund campaign" };

// [PERSON 3] Mock checkout — the brand locks the campaign budget into the reward pool.
export default async function FundCampaignPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <RequireAuth roles={["brand"]}>
      <FundCheckout campaignId={id} />
    </RequireAuth>
  );
}
