import { RequireAuth } from "@/components/auth/require-auth";
import { ComingSoon } from "@/components/layout/coming-soon";

// TODO(Person 2): creator's submissions. Show status on <CampaignCard badge={...} />.
export default function SubmissionsPage() {
  return (
    <RequireAuth roles={["creator"]}>
      <ComingSoon
        owner="Person 2 — Submissions"
        title="My submissions"
        todo={[
          "List submissions with status badge: pending / approved / rejected",
          "Views, gross, commission, net per submission",
          "Submit content form (video / YouTube link) — opened from campaign detail",
        ]}
      />
    </RequireAuth>
  );
}
