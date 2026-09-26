import type { Metadata } from "next";

import { RequireAuth } from "@/components/auth/require-auth";
import { WalletView } from "@/components/wallet/wallet-view";

export const metadata: Metadata = { title: "Wallet" };

// [PERSON 3] Creator wallet: balance, lifetime totals, mock cash out, transaction history.
export default function WalletPage() {
  return (
    <RequireAuth roles={["creator"]}>
      <WalletView />
    </RequireAuth>
  );
}
