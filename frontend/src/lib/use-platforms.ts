"use client";

// [PERSON 3] Which video platforms exist, which accept submissions, and which ones the current
// user has connected. Backed by GET /api/platforms so the backend stays the single source of truth.
//   const { platforms, reload } = usePlatforms();

import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/providers/auth-provider";
import { api } from "@/lib/api";
import type { PlatformStatus } from "@/lib/types";

export function usePlatforms() {
  const { user } = useAuth();
  const [platforms, setPlatforms] = useState<PlatformStatus[] | null>(null);

  const reload = useCallback(async () => {
    if (!user) return setPlatforms(null);
    try {
      setPlatforms(await api<PlatformStatus[]>("/api/platforms"));
    } catch {
      setPlatforms([]);
    }
  }, [user]);

  useEffect(() => {
    reload();
  }, [reload]);

  return { platforms, reload };
}

/** "YouTube or TikTok" */
export function joinLabels(labels: string[]) {
  return labels.length <= 1 ? (labels[0] ?? "") : `${labels.slice(0, -1).join(", ")} or ${labels.at(-1)}`;
}
