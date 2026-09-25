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
        "Cap per post, cap per profile, deadline",
        "Description + requirements",
        "Submit Content button -> Person 2's submit form (creators only)",
        "Brand owner: Fund campaign button -> /campaigns/{id}/fund (Person 3)",
      ]}
    />
  );
}
