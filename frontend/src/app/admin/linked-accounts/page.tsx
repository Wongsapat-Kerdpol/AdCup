import { LinkedAccountsView } from "@/components/admin/linked-accounts-view";
import { RequireAuth } from "@/components/auth/require-auth";

// Linked account detection: decide whether flagged accounts are the same person.
export default function AdminLinkedAccountsPage() {
  return (
    <RequireAuth roles={["admin"]}>
      <LinkedAccountsView />
    </RequireAuth>
  );
}
