"use client";

// [PERSON 2] Submit a video link to a campaign. Used on /submissions and the campaign detail page.
// `platforms` = the platforms this campaign accepts. As soon as a link is pasted, the form says which
// platform it is and whether it can be submitted (accepted by the campaign + account connected).
// The backend still checks everything again (routers/submissions.py).

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertTriangle, CheckCircle2, Loader2, Send, XCircle } from "lucide-react";
import { toast } from "sonner";

import { PlatformIcon, platformLabels } from "@/components/campaign/platform-icon";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import { detectPlatform } from "@/lib/platform-links";
import { routes } from "@/lib/routes";
import type { Platform, PlatformStatus, Submission } from "@/lib/types";
import { joinLabels, usePlatforms } from "@/lib/use-platforms";
import { cn } from "@/lib/utils";

const examples: Partial<Record<Platform, string>> = {
  youtube: "https://youtube.com/watch?v=...",
  tiktok: "https://www.tiktok.com/@you/video/...",
};

// Same text as backend routers/submissions.py PAYOUT_ACCOUNT_REQUIRED (linked account detection, spec D8).
const PAYOUT_ACCOUNT_REQUIRED = "Set up your payout account in Settings first";

type Hint = { tone: "ok" | "warn" | "error"; text: string; platform?: Platform; settings?: boolean; blocks: boolean };

function linkHint(url: string, accepted: Platform[], statuses: PlatformStatus[] | null): Hint | null {
  const platform = detectPlatform(url);
  if (platform === null) return null;
  const usable = (statuses ?? []).filter((s) => s.supported && accepted.includes(s.name));
  if (platform === "unknown") {
    const labels = joinLabels(usable.map((s) => s.label)) || "video";
    // Not blocking: the backend may still recognise it (e.g. a link format we don't parse here).
    return { tone: "error", text: `This doesn't look like a ${labels} video link`, blocks: false };
  }
  const label = platformLabels[platform];
  const status = statuses?.find((s) => s.name === platform);
  if (!status?.supported) {
    return { tone: "error", text: `${label} links aren't supported yet`, platform, blocks: true };
  }
  if (!accepted.includes(platform)) {
    return { tone: "error", text: `This campaign doesn't accept ${label} links`, platform, blocks: true };
  }
  if (!status.connected) {
    return {
      tone: "warn",
      text: `${label} link — connect your ${status.account_label} first`,
      platform,
      settings: true,
      blocks: true,
    };
  }
  return { tone: "ok", text: `${label} link — ready to submit`, platform, blocks: false };
}

const toneStyle = {
  ok: { icon: CheckCircle2, cls: "text-green-700" },
  warn: { icon: AlertTriangle, cls: "text-amber-700" },
  error: { icon: XCircle, cls: "text-red-600" },
} as const;

export function SubmitContentForm({
  campaignId,
  platforms = ["youtube"],
  onSubmitted,
}: {
  campaignId: number | string;
  platforms?: Platform[];
  onSubmitted?: (submission: Submission) => void;
}) {
  const router = useRouter();
  const { platforms: statuses } = usePlatforms();
  const [videoUrl, setVideoUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Placeholder: only the platforms this creator can submit to right now.
  const ready = (statuses ?? []).filter((s) => s.supported && s.connected && platforms.includes(s.name));
  const placeholder =
    ready.length === 1
      ? (examples[ready[0].name] ?? `Paste your ${ready[0].label} link`)
      : ready.length > 1
        ? `Paste your ${joinLabels(ready.map((s) => s.label))} link`
        : "Paste your video link";

  const hint = linkHint(videoUrl, platforms, statuses);

  async function submit() {
    if (!videoUrl.trim() || hint?.blocks) return;
    setSubmitting(true);
    try {
      const submission = await api<Submission>("/api/submissions", {
        method: "POST",
        body: { campaign_id: Number(campaignId), video_url: videoUrl.trim() },
      });
      toast.success("Video submitted — running the system check now");
      setVideoUrl("");
      onSubmitted?.(submission);
    } catch (err) {
      if (err instanceof ApiError && err.message === PAYOUT_ACCOUNT_REQUIRED) {
        toast.error(err.message, { action: { label: "Open Settings", onClick: () => router.push(routes.settings) } });
      } else {
        toast.error(err instanceof ApiError ? err.message : "Could not submit that video");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-1.5">
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input
          placeholder={placeholder}
          aria-label="Video link"
          aria-describedby={hint ? "video-link-hint" : undefined}
          aria-invalid={hint?.blocks || undefined}
          value={videoUrl}
          onChange={(e) => setVideoUrl(e.target.value)}
          disabled={submitting}
          onKeyDown={(e) => e.key === "Enter" && submit()}
        />
        <Button onClick={submit} disabled={submitting || !videoUrl.trim() || hint?.blocks}>
          {submitting ? <Loader2 className="animate-spin" /> : <Send />}
          Submit video
        </Button>
      </div>
      {hint && <LinkHint hint={hint} />}
    </div>
  );
}

function LinkHint({ hint }: { hint: Hint }) {
  const { icon: Icon, cls } = toneStyle[hint.tone];
  return (
    <p id="video-link-hint" className={cn("flex flex-wrap items-center gap-1.5 text-xs", cls)}>
      {hint.platform ? <PlatformIcon platform={hint.platform} /> : <Icon className="size-3.5" />}
      {hint.text}
      {hint.settings && (
        <Link href={routes.settings} className="font-medium underline underline-offset-2">
          Open Settings
        </Link>
      )}
    </p>
  );
}
