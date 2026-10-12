"use client";

// "Is this campaign still worth making a video for?" — GET /api/campaigns/{id}/outlook.
// The remaining pool alone is misleading: approved videos keep gaining views and have a claim on it.
// The backend projects those claims, finds the day the pool runs dry, and estimates what a new video
// would earn (the creator can try their own views/day).

import { useEffect, useState } from "react";
import { Hourglass } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import type { CampaignOutlook, OutlookVerdict } from "@/lib/types";
import { cn, formatNumber, formatTHB } from "@/lib/utils";

const VERDICTS: Record<
  OutlookVerdict,
  { label: string; variant: "success" | "warning" | "destructive" | "secondary"; text: string }
> = {
  open: { label: "Worth it", variant: "success", text: "There is plenty of room in the pool for another video." },
  competitive: {
    label: "Getting competitive",
    variant: "warning",
    text: "The pool may not cover everyone in full — you'd likely get most of it.",
  },
  crowded: { label: "Crowded", variant: "destructive", text: "Approved videos have already claimed most of the pool." },
  closed: { label: "Closed", variant: "secondary", text: "This campaign is not paying new videos." },
};

export function CampaignOutlookCard({ campaignId }: { campaignId: number }) {
  const [outlook, setOutlook] = useState<CampaignOutlook | null>(null);
  const [vpd, setVpd] = useState("");
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      const n = Number(vpd);
      api<CampaignOutlook>(`/api/campaigns/${campaignId}/outlook`, {
        query: { views_per_day: vpd !== "" && n >= 0 ? n : undefined },
      })
        .then((o) => {
          setOutlook(o);
          setFailed(false);
        })
        .catch(() => setFailed(true));
    }, 300);
    return () => clearTimeout(timer);
  }, [campaignId, vpd]);

  if (failed && !outlook) return null;
  if (!outlook) return <Skeleton className="h-56 rounded-xl" />;

  const v = VERDICTS[outlook.verdict];
  const n = outlook.newcomer;
  const fill = n.fill_ratio === null ? null : Math.round(n.fill_ratio * 100);
  const assumption =
    n.assumption === "input"
      ? "your estimate"
      : n.assumption === "median"
        ? `median of ${outlook.approved_videos} approved videos`
        : "a typical new video";

  return (
    <div className="space-y-3 rounded-xl border bg-card p-5">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">Is it still worth joining?</h2>
        <Badge variant={v.variant}>{v.label}</Badge>
      </div>
      <p className="text-xs text-muted-foreground">{v.text}</p>

      <dl className="space-y-2 text-sm">
        <Row label="Pool left today" value={formatTHB(outlook.pool_remaining)} />
        <Row
          label={`Expected claims, next ${outlook.horizon_days} days`}
          value={formatTHB(outlook.projected_claims)}
          hint={outlook.pressure !== null ? `${outlook.pressure.toFixed(1)}× the pool` : undefined}
        />
        <Row
          label="Pool runs dry"
          value={
            outlook.exhausted_on
              ? outlook.exhausted_in_days === 0
                ? "already claimed"
                : `~${new Date(outlook.exhausted_on).toLocaleDateString(undefined, { month: "short", day: "numeric" })}`
              : `not within ${outlook.horizon_days} days`
          }
          hint={outlook.exhausted_in_days ? `in ${outlook.exhausted_in_days} days` : undefined}
        />
        <Row label="Videos in the race" value={`${outlook.approved_videos} approved · ${outlook.in_review_videos} in review`} />
      </dl>

      <div className="space-y-2 rounded-lg bg-muted/50 p-3">
        <label className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
          If my video gets (views / day)
          <Input
            type="number"
            min={0}
            inputMode="numeric"
            placeholder={String(Math.round(n.views_per_day))}
            value={vpd}
            onChange={(e) => setVpd(e.target.value)}
            className="h-8 w-28 text-right"
          />
        </label>
        <div className="flex items-baseline justify-between gap-3">
          <span className="text-xs text-muted-foreground">
            I&apos;d earn about
            <span className="block text-[11px]">
              at {formatNumber(n.views_per_day)} views/day · {assumption}
            </span>
          </span>
          <span className="text-right">
            <span className="text-xl font-bold">{formatTHB(n.expected_net)}</span>
            {fill !== null && (
              <span className={cn("block text-xs", fill >= 95 ? "text-green-700" : fill >= 60 ? "text-amber-700" : "text-red-600")}>
                {fill}% of what it earns gets paid
              </span>
            )}
          </span>
        </div>
      </div>
      <p className="flex items-start gap-1.5 text-[11px] leading-snug text-muted-foreground">
        <Hourglass className="mt-0.5 size-3 shrink-0" />
        An estimate: it assumes videos keep their average views per day. After the 10% fee, paid in payout rounds.
      </p>
    </div>
  );
}

function Row({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right font-medium">
        {value}
        {hint && <span className="block text-xs font-normal text-muted-foreground">{hint}</span>}
      </dd>
    </div>
  );
}
