"use client";

// [ANTI-FRAUD] Duplicate-clip warning shown on each card of the admin review queue.
// GET /api/admin/duplicates/{id} — see backend/app/services/duplicate_check.py.
// It only warns; the admin still decides.

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, ArrowRight, ExternalLink, FlipHorizontal, Loader2, ShieldAlert, ShieldCheck } from "lucide-react";

import { SubmissionStatusBadge } from "@/components/campaign/submission-status-badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { routes } from "@/lib/routes";
import type { DuplicateMatch, DuplicateReport } from "@/lib/types";
import { cn, formatTHB } from "@/lib/utils";

const levelStyle = {
  copy: {
    icon: ShieldAlert,
    title: "Probably a copy",
    box: "border-destructive/50 bg-destructive/10",
    text: "text-red-400",
  },
  check: {
    icon: AlertTriangle,
    title: "Should check",
    box: "border-amber-500/40 bg-amber-500/10",
    text: "text-amber-400",
  },
} as const;

export function DuplicateWarning({ submissionId }: { submissionId: number }) {
  const [report, setReport] = useState<DuplicateReport | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api<DuplicateReport>(`/api/admin/duplicates/${submissionId}`)
      .then((r) => !cancelled && setReport(r))
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, [submissionId]);

  if (failed || report?.status === "disabled") return null;

  if (report === null) {
    return (
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Loader2 className="size-3 animate-spin" /> Checking for copied clips…
      </p>
    );
  }

  if (report.status !== "ok") {
    return (
      <p className="text-xs text-muted-foreground">
        Duplicate check unavailable {report.status === "no_pictures" ? "(no usable pictures from YouTube)" : "right now"}.
      </p>
    );
  }

  if (report.level === null) {
    return (
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <ShieldCheck className="size-3.5 text-green-400" /> No similar clips found ({report.pictures_checked} pictures
        checked)
      </p>
    );
  }

  const style = levelStyle[report.level];
  return (
    <div className={cn("space-y-2 rounded-lg border p-3", style.box)}>
      <p className={cn("flex items-center gap-1.5 text-sm font-semibold", style.text)}>
        <style.icon className="size-4" /> {style.title}
      </p>
      <ul className="space-y-1.5">
        {report.matches.map((m) => (
          <MatchRow key={m.submission_id} match={m} />
        ))}
      </ul>
      <p className="text-[11px] text-muted-foreground">
        Watch both clips before deciding. Compared {report.pictures_checked} pictures · {report.comparisons} checks in the
        BK-Tree vs {report.linear_comparisons} for checking everything.
      </p>
    </div>
  );
}

function sentWhen(m: DuplicateMatch) {
  const order = m.submitted_earlier ? "earlier" : "later";
  if (m.days_apart < 1) return `sent ${order} the same day`;
  return `sent ${m.days_apart} day${m.days_apart === 1 ? "" : "s"} ${order}`;
}

function MatchRow({ match: m }: { match: DuplicateMatch }) {
  const style = levelStyle[m.level];
  return (
    <li className="space-y-1.5 rounded-md bg-background/40 p-2.5 text-xs">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className={cn("font-semibold", style.text)}>{Math.round(m.similarity * 100)}% similar</span>
        <span className="text-muted-foreground">
          {m.matched_pictures}/{m.total_pictures} pictures · closest {m.closest_distance} bits
        </span>
        {m.mirrored && (
          <span className="inline-flex items-center gap-0.5 text-muted-foreground">
            <FlipHorizontal className="size-3" /> mirrored
          </span>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0 space-y-0.5">
          <p>
            <span className="font-semibold">
              {m.submitted_earlier ? "Likely original:" : "Similar clip (sent after this one):"}
            </span>{" "}
            clip #{m.submission_id} by <span className="font-medium">{m.creator_name}</span>
          </p>
          <p className="flex flex-wrap items-center gap-1.5 text-muted-foreground">
            {m.campaign_title} · {sentWhen(m)} · <SubmissionStatusBadge status={m.status} /> · earned{" "}
            {formatTHB(m.net_paid)}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <a
            href={m.video_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-muted-foreground hover:text-foreground"
            title="Watch on YouTube"
          >
            YouTube <ExternalLink className="size-3" />
          </a>
          <Button asChild size="sm" variant="outline" className="h-7">
            <Link href={`${routes.campaign(m.campaign_id)}?highlight=${m.submission_id}`}>
              View in campaign <ArrowRight />
            </Link>
          </Button>
        </div>
      </div>
    </li>
  );
}
