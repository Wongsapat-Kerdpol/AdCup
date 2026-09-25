import { ComingSoon } from "@/components/layout/coming-soon";

// TODO(Person 1): campaign detail page. Data: GET /api/campaigns/{id} -> CampaignDetail (src/lib/types.ts)
export default async function CampaignDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <ComingSoon
      owner="Person 1 — Campaign Detail"
      title={`Campaign #${id}`}
      todo={[
        "Header: thumbnail, title, brand, category, platforms",
        "Stats: paid out % + progress bar, total budget, remaining pool, rate / 1M views",
        "Cap per post, cap per profile, minimum views to qualify, deadline",
        "Description + requirements (the admin checks these in round 2)",
        "\"How you get paid\": system check -> admin review -> earn as views grow",
        "Submit Content button -> <SubmitContentForm campaignId={id} /> from Person 2 (creators only, YouTube for now)",
        "Brand owner: Fund campaign button -> /campaigns/{id}/fund (Person 3)",
      ]}
    />
  );
}
