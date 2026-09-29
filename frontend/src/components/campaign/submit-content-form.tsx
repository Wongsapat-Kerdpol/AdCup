"use client";

// [PERSON 2] Submit a YouTube link to a campaign. Used on /submissions; Person 1's campaign
// detail page can drop this in too once it exists — it only needs a campaignId.

import { useState } from "react";
import { Loader2, Send } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import type { Submission } from "@/lib/types";

export function SubmitContentForm({
  campaignId,
  onSubmitted,
}: {
  campaignId: number | string;
  onSubmitted?: (submission: Submission) => void;
}) {
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
        placeholder="https://youtube.com/watch?v=..."
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
