// [PERSON 1] Campaign lifecycle badge: draft (not funded) -> active (live) <-> paused -> completed.

import { Badge } from "@/components/ui/badge";
import type { CampaignStatus } from "@/lib/types";

const config: Record<CampaignStatus, { label: string; variant: "secondary" | "warning" | "success" | "outline" }> = {
  draft: { label: "Draft · not funded", variant: "warning" },
  active: { label: "Live", variant: "success" },
  paused: { label: "Paused", variant: "secondary" },
  completed: { label: "Completed", variant: "outline" },
};

export function CampaignStatusBadge({ status }: { status: CampaignStatus }) {
  const { label, variant } = config[status];
  return <Badge variant={variant}>{label}</Badge>;
}
