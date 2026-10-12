"use client";

// [PERSON 2] Round-2 admin review queue: brand requirements next to the video, approve
// (starts earning immediately) or reject with a reason.

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, ClipboardList, Link2, Loader2, ThumbsDown, ThumbsUp, User, XCircle } from "lucide-react";
import { toast } from "sonner";

import { signalLabel } from "@/components/admin/linked-accounts-view";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import { routes } from "@/lib/routes";
import type { SubmissionForReview } from "@/lib/types";
import { formatNumber, formatTHB } from "@/lib/utils";

export function ReviewQueue() {
  const [queue, setQueue] = useState<SubmissionForReview[] | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [rejectingId, setRejectingId] = useState<number | null>(null);
  const [reason, setReason] = useState("");

  const load = useCallback(async () => {
    try {
      setQueue(await api<SubmissionForReview[]>("/api/admin/review"));
    } catch (err) {
      toast.error(`Could not load the review queue: ${(err as Error).message}`);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function approve(id: number) {
    setBusyId(id);
    try {
      await api(`/api/admin/review/${id}/approve`, { method: "POST" });
      toast.success("Approved — the submission starts earning immediately");
      await load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not approve this submission");
    } finally {
      setBusyId(null);
    }
  }

  async function reject(id: number) {
    if (!reason.trim()) return;
    setBusyId(id);
    try {
      await api(`/api/admin/review/${id}/reject`, { method: "POST", body: { reason: reason.trim() } });
      toast.success("Rejected");
      setRejectingId(null);
      setReason("");
      await load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not reject this submission");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 py-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Review queue</h1>
        <p className="text-sm text-muted-foreground">
          Submissions that passed the automatic system check, waiting on a content review.
        </p>
      </div>

      {queue === null ? (
        <div className="space-y-3">
          <Skeleton className="h-64 rounded-xl" />
          <Skeleton className="h-64 rounded-xl" />
        </div>
      ) : queue.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed py-12 text-center">
          <ClipboardList className="size-8 text-muted-foreground" />
          <p className="font-medium">Nothing to review</p>
          <p className="text-sm text-muted-foreground">Submissions land here once they pass the system check.</p>
        </div>
      ) : (
        <ul className="space-y-4">
          {queue.map((s) => (
            <li key={s.id} className="space-y-3 rounded-xl border bg-card p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-medium">{s.campaign_title}</p>
                  <p className="flex items-center gap-1 text-xs text-muted-foreground">
                    <User className="size-3" /> {s.creator_name} · {formatNumber(s.view_count)} views
                  </p>
                </div>
              </div>

              <LinkNotices submission={s} />

              <div className="grid gap-3 sm:grid-cols-[1fr_260px]">
                <div className="space-y-1 rounded-lg bg-muted/40 p-3 text-sm">
                  <p className="text-xs font-semibold text-muted-foreground">Brand requirements</p>
                  <p className="whitespace-pre-line">{s.campaign_requirements || "No specific requirements listed."}</p>
                </div>
                {s.external_video_id ? (
                  <div className="aspect-video overflow-hidden rounded-lg bg-black">
                    <iframe
                      src={`https://www.youtube.com/embed/${s.external_video_id}`}
                      title={s.video_title ?? "Submitted video"}
                      className="size-full"
                      allow="encrypted-media"
                      allowFullScreen
                    />
                  </div>
                ) : (
                  <a
                    href={s.video_url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex aspect-video items-center justify-center rounded-lg border border-dashed text-xs text-muted-foreground hover:text-foreground"
                  >
                    Open video link
                  </a>
                )}
              </div>

              {rejectingId === s.id ? (
                <div className="space-y-2">
                  <Textarea
                    placeholder="Reason for rejection, e.g. the product isn't visible in the video"
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    disabled={busyId === s.id}
                  />
                  <div className="flex justify-end gap-2">
                    <Button variant="ghost" size="sm" onClick={() => setRejectingId(null)} disabled={busyId === s.id}>
                      Cancel
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => reject(s.id)}
                      disabled={busyId === s.id || !reason.trim()}
                    >
                      {busyId === s.id ? <Loader2 className="animate-spin" /> : <XCircle />}
                      Confirm reject
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="flex justify-end gap-2 border-t pt-3">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setRejectingId(s.id);
                      setReason("");
                    }}
                    disabled={busyId === s.id}
                  >
                    <ThumbsDown /> Reject
                  </Button>
                  <Button size="sm" onClick={() => approve(s.id)} disabled={busyId === s.id}>
                    {busyId === s.id ? <Loader2 className="animate-spin" /> : <ThumbsUp />}
                    Approve
                  </Button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// Linked account detection. Approve / Reject still judge only the content; whether accounts are one
// person is decided on the Linked accounts page.
function LinkNotices({ submission: s }: { submission: SubmissionForReview }) {
  const suspected = s.open_flags.filter((f) => f.kind === "suspected");
  const overage = s.open_flags.find((f) => f.kind === "overage");
  if (s.linked_accounts.length === 0 && suspected.length === 0 && !overage) return null;

  const decide = (
    <Link href={routes.adminLinkedAccounts} className="font-medium underline-offset-2 hover:underline">
      Decide in Linked accounts →
    </Link>
  );
  return (
    <div className="space-y-2 text-sm">
      {s.linked_accounts.map((a) => (
        <div key={a.user_id} className="flex items-start gap-2 rounded-lg border border-rose-500/40 bg-rose-500/10 p-3">
          <Link2 className="mt-0.5 size-4 shrink-0 text-rose-400" />
          <p>
            <span className="font-semibold">Linked account.</span> Same person as{" "}
            <strong>
              {a.display_name} (#{a.user_id})
            </strong>
            . Matched: {a.matched.map(signalLabel).join(", ") || "through another linked account"}.{" "}
            {s.cap_per_profile
              ? `This person has earned ${formatTHB(s.group_gross_in_campaign)} of the ${formatTHB(s.cap_per_profile)} cap per profile in this campaign.`
              : `This person has earned ${formatTHB(s.group_gross_in_campaign)} in this campaign (no cap per profile).`}
          </p>
        </div>
      ))}
      {overage && (
        <div className="flex items-start gap-2 rounded-lg border border-rose-500/40 bg-rose-500/10 p-3">
          <Link2 className="mt-0.5 size-4 shrink-0 text-rose-400" />
          <p>
            This person was paid {overage.amount ? formatTHB(overage.amount) : "more"} over the cap per profile before
            the accounts were linked. {decide}
          </p>
        </div>
      )}
      {suspected.map((f) => (
        <div key={f.id} className="flex items-start gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-400" />
          <p>
            Possible link with{" "}
            <strong>
              {f.other_display_name} (#{f.other_user_id})
            </strong>
            : {f.reasons.map(signalLabel).join(", ")}. Not merged. Caps are still separate. {decide}
          </p>
        </div>
      ))}
    </div>
  );
}
