import { RequireAuth } from "@/components/auth/require-auth";
import { ComingSoon } from "@/components/layout/coming-soon";

// TODO(Person 3)
export default function AdminPage() {
  return (
    <RequireAuth roles={["admin"]}>
      <ComingSoon
        owner="Person 3 — Admin"
        title="Analytics"
        todo={["Active users", "Transaction volume", "Commission revenue (projected)", "Campaign performance"]}
      />
    </RequireAuth>
  );
}
