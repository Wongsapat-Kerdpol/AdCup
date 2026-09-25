import { RequireAuth } from "@/components/auth/require-auth";
import { ComingSoon } from "@/components/layout/coming-soon";

// TODO(Person 2): round-2 admin review queue. API: GET/POST /api/admin/review (backend/app/routers/review.py)
export default function AdminReviewPage() {
  return (
    <RequireAuth roles={["admin"]}>
      <ComingSoon
        owner="Person 2 — Admin Review"
        title="Review queue"
        todo={[
          "List submissions that passed the system check (status = under_review), oldest first",
          "Show the campaign's requirements next to an embedded YouTube player of the video",
          "Approve -> starts earning immediately (payout for current views) -> toast",
          "Reject with a reason (e.g. \"bottle not shown in the video\") -> toast",
        ]}
      />
    </RequireAuth>
  );
}
