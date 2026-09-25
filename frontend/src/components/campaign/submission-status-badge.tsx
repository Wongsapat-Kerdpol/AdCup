// [MAIN] Shared status badge. Person 2: use it on <CampaignCard badge={...} /> and in lists.

import { Badge } from "@/components/ui/badge";
import type { SubmissionStatus } from "@/lib/types";

const config: Record<SubmissionStatus, { label: string; variant: "secondary" | "warning" | "success" | "destructive" }> = {
  pending: { label: "System check", variant: "secondary" },
  under_review: { label: "Admin review", variant: "warning" },
  approved: { label: "Earning", variant: "success" },
  rejected: { label: "Rejected", variant: "destructive" },
};

export function SubmissionStatusBadge({ status }: { status: SubmissionStatus }) {
  const { label, variant } = config[status];
  return <Badge variant={variant}>{label}</Badge>;
}
