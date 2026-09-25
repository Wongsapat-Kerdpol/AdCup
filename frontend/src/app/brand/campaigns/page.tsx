import { RequireAuth } from "@/components/auth/require-auth";
import { ComingSoon } from "@/components/layout/coming-soon";

// TODO(Person 1): brand's own campaigns. Reuse <CampaignCard> from @/components/campaign/campaign-card.
export default function BrandCampaignsPage() {
  return (
    <RequireAuth roles={["brand"]}>
      <ComingSoon
        owner="Person 1 — Brand"
        title="My campaigns"
        todo={[
          "List own campaigns incl. drafts (not funded yet)",
          "Per campaign: spend so far, creators joined, submissions per status, total views",
          "Read-only list of submitted videos (Person 2's API) — brands don't approve, admins do",
        ]}
      />
    </RequireAuth>
  );
}
