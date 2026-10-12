"use client";

// [ANTI-FRAUD] Duplicate-clip warning shown on each card of the admin review queue.
// GET /api/admin/duplicates/{id} — see backend/app/services/duplicate_check.py.
// It only warns; the admin still decides.

import { useEffect, useState } from "react";
import { AlertTriangle, ExternalLink, FlipHorizontal, Loader2, ShieldAlert, ShieldCheck } from "lucide-react";

import { api } from "@/lib/api";
import type { DuplicateMatch, DuplicateReport } from "@/lib/types";
import { cn } from "@/lib/utils";

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

function MatchRow({ match: m }: { match: DuplicateMatch }) {
  const style = levelStyle[m.level];
  return (
    <li className="flex items-center justify-between gap-3 text-xs">
      <span className="min-w-0">
        <span className={cn("font-semibold", style.text)}>{Math.round(m.similarity * 100)}% similar</span>{" "}
        <span className="text-muted-foreground">
          to clip #{m.submission_id} by {m.creator_name} · {m.campaign_title} · {m.matched_pictures}/{m.total_pictures}{" "}
          pictures, closest {m.closest_distance} bits
        </span>
        {m.mirrored && (
          <span className="ml-1 inline-flex items-center gap-0.5 text-muted-foreground">
            <FlipHorizontal className="size-3" /> mirrored
          </span>
        )}
      </span>
      <a
        href={m.video_url}
        target="_blank"
        rel="noreferrer"
        className="inline-flex shrink-0 items-center gap-1 text-muted-foreground hover:text-foreground"
      >
        Open <ExternalLink className="size-3" />
      </a>
    </li>
  );
}
