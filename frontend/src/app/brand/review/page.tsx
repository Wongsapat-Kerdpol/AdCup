import { RequireAuth } from "@/components/auth/require-auth";
import { ComingSoon } from "@/components/layout/coming-soon";

// TODO(Person 2): brand approval screen.
export default function BrandReviewPage() {
  return (
    <RequireAuth roles={["brand"]}>
      <ComingSoon
        owner="Person 2 — Submissions"
        title="Review submissions"
        todo={[
          "Pending submissions across my campaigns (video link/embed, creator, views)",
          "Approve -> payout engine (FCFS + 10% commission) -> toast",
          "Reject with reason",
        ]}
      />
    </RequireAuth>
  );
}
