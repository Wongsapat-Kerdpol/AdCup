"use client";

// [ADMIN] Every submission of a campaign with who sent it — shown on /campaigns/[id] to admins only.
// ?highlight=<submission id> (used by the duplicate-clip warning) scrolls to that row and marks it.
// "Details" loads the full record incl. the creator's email (GET /api/admin/submissions/{id}).

import { Fragment, useEffect, useState } from "react";
import { ChevronDown, ChevronUp, ExternalLink, Loader2, ShieldCheck } from "lucide-react";

import { SubmissionStatusBadge } from "@/components/campaign/submission-status-badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import type { AdminSubmissionDetail, AdminSubmissionRow } from "@/lib/types";
import { cn, formatNumber, formatTHB } from "@/lib/utils";

const when = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—";

export function AdminCampaignSubmissions({ campaignId }: { campaignId: number }) {
  const [rows, setRows] = useState<AdminSubmissionRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [highlight, setHighlight] = useState<number | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);

  useEffect(() => {
    api<AdminSubmissionRow[]>(`/api/admin/campaigns/${campaignId}/submissions`)
      .then(setRows)
      .catch((err) => setError((err as Error).message));
  }, [campaignId]);

  // Read ?highlight= once the rows are on screen, then scroll to that submission.
  useEffect(() => {
    if (!rows) return;
    const id = Number(new URLSearchParams(window.location.search).get("highlight"));
    if (!id || !rows.some((r) => r.id === id)) return;
    setHighlight(id);
    setOpenId(id);
    document.getElementById(`submission-${id}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [rows]);

  return (
    <section className="space-y-3 rounded-xl border border-primary/30 bg-card p-5">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h2 className="flex items-center gap-2 font-semibold">
            <ShieldCheck className="size-4 text-primary" /> Submissions {rows && `(${rows.length})`}
          </h2>
          <p className="text-xs text-muted-foreground">Admin view — who sent what, every status.</p>
        </div>
      </div>

      {error ? (
        <p className="text-sm text-destructive">Could not load submissions: {error}</p>
      ) : rows === null ? (
        <Skeleton className="h-24 rounded-lg" />
      ) : rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">No videos submitted yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b text-left text-xs text-muted-foreground">
                <th className="py-2 pr-3 font-medium">Creator</th>
                <th className="py-2 pr-3 font-medium">Video</th>
                <th className="py-2 pr-3 font-medium">Status</th>
                <th className="py-2 pr-3 font-medium">Submitted</th>
                <th className="py-2 pr-3 text-right font-medium">Views</th>
                <th className="py-2 pr-3 text-right font-medium">Earned (net)</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <Fragment key={r.id}>
                  <tr
                    id={`submission-${r.id}`}
                    className={cn(
                      "border-b align-top last:border-0",
                      highlight === r.id && "bg-amber-500/10 outline outline-1 outline-amber-500/60",
                    )}
                  >
                    <td className="py-2.5 pr-3">
                      <p className="font-medium">{r.creator_name}</p>
                      {r.youtube_channel_id ? (
                        <a
                          href={`https://www.youtube.com/channel/${r.youtube_channel_id}`}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                        >
                          {r.youtube_channel_title ?? "YouTube channel"} <ExternalLink className="size-3" />
                        </a>
                      ) : (
                        <p className="text-xs text-muted-foreground">No channel linked</p>
                      )}
                    </td>
                    <td className="max-w-[220px] py-2.5 pr-3">
                      <a
                        href={r.video_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 break-all hover:underline"
                      >
                        {r.video_title || r.video_url} <ExternalLink className="size-3 shrink-0" />
                      </a>
                      <p className="text-xs text-muted-foreground">#{r.id}</p>
                    </td>
                    <td className="py-2.5 pr-3">
                      <SubmissionStatusBadge status={r.status} />
                    </td>
                    <td className="py-2.5 pr-3 text-xs whitespace-nowrap text-muted-foreground">{when(r.submitted_at)}</td>
                    <td className="py-2.5 pr-3 text-right">{formatNumber(r.view_count)}</td>
                    <td className="py-2.5 pr-3 text-right">{formatTHB(r.net_amount)}</td>
                    <td className="py-2.5 text-right">
                      <Button variant="ghost" size="sm" onClick={() => setOpenId(openId === r.id ? null : r.id)}>
                        Details {openId === r.id ? <ChevronUp /> : <ChevronDown />}
                      </Button>
                    </td>
                  </tr>
                  {openId === r.id && (
                    <tr className="border-b last:border-0">
                      <td colSpan={7} className="pb-3">
                        <SubmissionDetails id={r.id} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function SubmissionDetails({ id }: { id: number }) {
  const [d, setD] = useState<AdminSubmissionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<AdminSubmissionDetail>(`/api/admin/submissions/${id}`)
      .then(setD)
      .catch((err) => setError((err as Error).message));
  }, [id]);

  if (error) return <p className="text-xs text-destructive">{error}</p>;
  if (!d)
    return (
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Loader2 className="size-3 animate-spin" /> Loading details…
      </p>
    );

  const items: [string, React.ReactNode][] = [
    ["Creator email", d.creator_email],
    ["Creator joined", when(d.creator_joined_at)],
    ["Creator's submissions (all campaigns)", d.creator_submissions],
    ["Creator's total earned (net)", formatTHB(d.creator_net_earned)],
    ["Video published on YouTube", when(d.video_published_at)],
    ["Video's channel ID", d.video_channel_id ?? "—"],
    ["Views last refreshed", when(d.views_refreshed_at)],
    ["Views already paid", formatNumber(d.paid_views)],
    ["Gross / commission / net", `${formatTHB(d.gross_amount)} / ${formatTHB(d.commission_amount)} / ${formatTHB(d.net_amount)}`],
    ["System check", when(d.system_checked_at)],
    ["Admin review", when(d.reviewed_at)],
    ["Approved", when(d.approved_at)],
  ];
  if (d.rejected_by) items.push([`Rejected by ${d.rejected_by}`, d.rejection_reason ?? "—"]);

  return (
    <dl className="grid gap-x-6 gap-y-1.5 rounded-lg bg-muted/40 p-3 text-xs sm:grid-cols-2">
      {items.map(([label, value]) => (
        <div key={label} className="flex justify-between gap-3">
          <dt className="text-muted-foreground">{label}</dt>
          <dd className="text-right font-medium break-all">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
