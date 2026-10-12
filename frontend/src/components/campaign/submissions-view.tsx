"use client";

// [PERSON 2] Creator's own submissions: status through the two review rounds, progress toward
// the campaign's minimum views, earnings so far, and a manual "refresh views" action.

import { useCallback, useEffect, useState } from "react";
import { AlertCircle, ExternalLink, Loader2, RefreshCw, Video } from "lucide-react";
import { toast } from "sonner";

import { PlatformIcon, platformLabels } from "@/components/campaign/platform-icon";
import { SubmissionStatusBadge } from "@/components/campaign/submission-status-badge";
import { SubmitContentForm } from "@/components/campaign/submit-content-form";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import type { Campaign, CampaignDetail, Paginated, Platform, Submission } from "@/lib/types";
import { cn, formatNumber, formatTHB, toNumber } from "@/lib/utils";

const isPlatform = (p: string): p is Platform => p in platformLabels;

export function SubmissionsView() {
  const [submissions, setSubmissions] = useState<Submission[] | null>(null);
  const [activeCampaigns, setActiveCampaigns] = useState<Campaign[]>([]);
  const [campaignDetails, setCampaignDetails] = useState<Record<number, CampaignDetail>>({});
  const [refreshingId, setRefreshingId] = useState<number | null>(null);
  const [pickerCampaignId, setPickerCampaignId] = useState<string>("");

  const load = useCallback(async () => {
    try {
      const [mine, active] = await Promise.all([
        api<Submission[]>("/api/submissions/mine"),
        api<Paginated<Campaign>>("/api/campaigns", { query: { status: "active", page_size: 100 } }),
      ]);
      setSubmissions(mine);
      setActiveCampaigns(active.items);

      // Fetch full campaign details (min_views, title) for every campaign referenced by a
      // submission — the list endpoint above doesn't include min_views.
      const ids = Array.from(new Set(mine.map((s) => s.campaign_id)));
      const details = await Promise.all(
        ids.map((id) => api<CampaignDetail>(`/api/campaigns/${id}`).catch(() => null)),
      );
      setCampaignDetails(
        Object.fromEntries(details.filter((c): c is CampaignDetail => c !== null).map((c) => [c.id, c])),
      );
    } catch (err) {
      toast.error(`Could not load your submissions: ${(err as Error).message}`);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function refreshViews(id: number) {
    setRefreshingId(id);
    try {
      const res = await api<{ throttled: boolean }>(`/api/platforms/refresh/${id}`, { method: "POST" });
      await load();
      if (res.throttled) toast.info("Refreshed a moment ago — try again in 30 seconds");
      else toast.success("Views refreshed");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not refresh views");
    } finally {
      setRefreshingId(null);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 py-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">My submissions</h1>
        <p className="text-sm text-muted-foreground">
          Every video you&apos;ve submitted, its review status, and what it has earned so far.
        </p>
      </div>

      <section className="space-y-3 rounded-xl border bg-card p-4">
        <h2 className="text-sm font-semibold">Submit a new video</h2>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <Select value={pickerCampaignId} onValueChange={setPickerCampaignId}>
            <SelectTrigger className="sm:w-64">
              <SelectValue placeholder="Choose a campaign" />
            </SelectTrigger>
            <SelectContent>
              {activeCampaigns.map((c) => (
                <SelectItem key={c.id} value={String(c.id)}>
                  {c.title}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="flex-1">
            {pickerCampaignId ? (
              <SubmitContentForm
                campaignId={pickerCampaignId}
                platforms={activeCampaigns.find((c) => String(c.id) === pickerCampaignId)?.platforms}
                onSubmitted={load}
              />
            ) : (
              <p className="text-sm text-muted-foreground">Pick a campaign to submit a video to it.</p>
            )}
          </div>
        </div>
      </section>

      {submissions === null ? (
        <div className="space-y-3">
          <Skeleton className="h-28 rounded-xl" />
          <Skeleton className="h-28 rounded-xl" />
        </div>
      ) : submissions.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed py-12 text-center">
          <Video className="size-8 text-muted-foreground" />
          <p className="font-medium">No submissions yet</p>
          <p className="text-sm text-muted-foreground">Pick a campaign above and submit your first video.</p>
        </div>
      ) : (
        <ul className="space-y-3">
          {submissions.map((s) => (
            <SubmissionCard
              key={s.id}
              submission={s}
              campaign={campaignDetails[s.campaign_id]}
              refreshing={refreshingId === s.id}
              onRefresh={() => refreshViews(s.id)}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

function SubmissionCard({
  submission: s,
  campaign,
  refreshing,
  onRefresh,
}: {
  submission: Submission;
  campaign: CampaignDetail | undefined;
  refreshing: boolean;
  onRefresh: () => void;
}) {
  const belowMinimum = s.status === "pending" && campaign && s.view_count < campaign.min_views;

  return (
    <li className="space-y-3 rounded-xl border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-1.5 text-sm font-medium">
            {isPlatform(s.platform) && <PlatformIcon platform={s.platform} className="shrink-0" />}
            <span className="truncate">{s.video_title ?? s.video_url}</span>
          </p>
          <a
            href={s.video_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          >
            {campaign?.title ?? `Campaign #${s.campaign_id}`} <ExternalLink className="size-3" />
          </a>
        </div>
        <SubmissionStatusBadge status={s.status} />
      </div>

      {belowMinimum && campaign && (
        <div className="space-y-1">
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>Views toward minimum</span>
            <span>
              {formatNumber(s.view_count)} / {formatNumber(campaign.min_views)}
            </span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-all"
              style={{ width: `${Math.min((s.view_count / campaign.min_views) * 100, 100)}%` }}
            />
          </div>
        </div>
      )}

      {s.status === "rejected" && s.rejection_reason && (
        <div className="flex items-start gap-2 rounded-lg bg-destructive/10 p-2.5 text-xs text-destructive">
          <AlertCircle className="mt-0.5 size-3.5 shrink-0" />
          <span>
            Rejected by {s.rejected_by === "system" ? "the automatic system check" : "an admin"}: {s.rejection_reason}
          </span>
        </div>
      )}

      <div className="flex items-center justify-between gap-3 border-t pt-3">
        <dl className="flex gap-4 text-xs">
          <div>
            <dt className="text-muted-foreground">Views</dt>
            <dd className="font-medium">{formatNumber(s.view_count)}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Earned (net)</dt>
            <dd className={cn("font-medium", toNumber(s.net_amount) > 0 && "text-green-700")}>
              {formatTHB(s.net_amount)}
            </dd>
          </div>
          {s.profile_cap_reached && (
            <div>
              <dt className="text-muted-foreground">Earnings</dt>
              <dd className="font-medium text-amber-700">Cap per profile reached</dd>
            </div>
          )}
        </dl>
        <Button size="sm" variant="outline" onClick={onRefresh} disabled={refreshing || s.status === "rejected"}>
          {refreshing ? <Loader2 className="animate-spin" /> : <RefreshCw />}
          Refresh views
        </Button>
      </div>
    </li>
  );
}
