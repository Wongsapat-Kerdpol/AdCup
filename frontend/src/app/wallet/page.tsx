import { RequireAuth } from "@/components/auth/require-auth";
import { ComingSoon } from "@/components/layout/coming-soon";

// TODO(Person 3)
export default function WalletPage() {
  return (
    <RequireAuth roles={["creator"]}>
      <ComingSoon
        owner="Person 3 — Wallet"
        title="Wallet"
        todo={[
          "Balance + transaction history (gross / commission / net)",
          "Mock Cash Out — enabled once balance ≥ ฿1,500",
        ]}
      />
    </RequireAuth>
  );
}
