"use client";

// [PERSON 2] Submit a video link to a campaign. Used on /submissions and the campaign detail page.
// The backend detects the platform from the link (Person 3); `platforms` only tunes the placeholder.

import { useState } from "react";
import { Loader2, Send } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import type { Platform, Submission } from "@/lib/types";

const examples: Partial<Record<Platform, string>> = {
  youtube: "https://youtube.com/watch?v=...",
  tiktok: "https://www.tiktok.com/@you/video/...",
};

export function SubmitContentForm({
  campaignId,
  platforms = ["youtube"],
  onSubmitted,
}: {
  campaignId: number | string;
  platforms?: Platform[];
  onSubmitted?: (submission: Submission) => void;
}) {
  const placeholder = platforms.length === 1 ? (examples[platforms[0]] ?? "Paste your video link") : "Paste your video link";
  const [videoUrl, setVideoUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    if (!videoUrl.trim()) return;
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
      toast.error(err instanceof ApiError ? err.message : "Could not submit that video");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-2 sm:flex-row">
      <Input
        placeholder={placeholder}
        aria-label="Video link"
        value={videoUrl}
        onChange={(e) => setVideoUrl(e.target.value)}
        disabled={submitting}
        onKeyDown={(e) => e.key === "Enter" && submit()}
      />
      <Button onClick={submit} disabled={submitting || !videoUrl.trim()}>
        {submitting ? <Loader2 className="animate-spin" /> : <Send />}
        Submit video
      </Button>
    </div>
  );
}
