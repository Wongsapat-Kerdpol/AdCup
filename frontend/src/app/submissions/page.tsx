import { RequireAuth } from "@/components/auth/require-auth";
import { ComingSoon } from "@/components/layout/coming-soon";

// TODO(Person 2): creator's submissions. Use <SubmissionStatusBadge> from @/components/campaign/submission-status-badge.
export default function SubmissionsPage() {
  return (
    <RequireAuth roles={["creator"]}>
      <ComingSoon
        owner="Person 2 — Submissions"
        title="My submissions"
        todo={[
          "List submissions with status: System check / Admin review / Earning / Rejected (+ reason)",
          "Pending ones below the campaign's min views: show progress, e.g. 640 / 1,000 views",
          "Views, gross, commission, net earned so far per submission",
          "\"Refresh views\" button (Person 3's endpoint) -> new earnings appear",
          "SubmitContentForm component (YouTube link) — also used on the campaign detail page",
        ]}
      />
    </RequireAuth>
  );
}
