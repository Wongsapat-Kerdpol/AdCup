import { RequireAuth } from "@/components/auth/require-auth";
import { ComingSoon } from "@/components/layout/coming-soon";

// TODO(Person 1): create-campaign form (brand only). POST /api/brand/campaigns
export default function NewCampaignPage() {
  return (
    <RequireAuth roles={["brand"]}>
      <ComingSoon
        owner="Person 1 — Brand"
        title="Create a campaign"
        todo={[
          "Title, description, category (logo/music/clipping/ugc)",
          "Requirements — what the admin checks in the video (e.g. \"show the bottle\")",
          "Rate per 1K views (THB), total budget, cap per post, cap per profile, min views (default 1,000), deadline",
          "Platforms: YouTube only for now (TikTok / IG later)",
          "Validate on frontend + backend",
          "After create -> redirect to /campaigns/{id}/fund (Person 3 mock checkout)",
        ]}
      />
    </RequireAuth>
  );
}
