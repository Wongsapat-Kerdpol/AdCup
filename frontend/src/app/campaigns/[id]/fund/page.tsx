import { RequireAuth } from "@/components/auth/require-auth";
import { ComingSoon } from "@/components/layout/coming-soon";

// TODO(Person 3): mock checkout. POST /api/payments/checkout/{id}
export default function FundCampaignPage() {
  return (
    <RequireAuth roles={["brand"]}>
      <ComingSoon
        owner="Person 3 — Payment"
        title="Fund campaign"
        todo={[
          "Order summary: total budget to lock into the pool",
          "Mock payment (fake QR / Stripe test mode)",
          "On success: campaign becomes active + Transaction(type=campaign_fund)",
        ]}
      />
    </RequireAuth>
  );
}
