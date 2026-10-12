// Recognise which platform a pasted video link belongs to, so the submit form can say so before
// the link is sent. Mirrors the backend parsers (services/youtube.py, services/tiktok.py) — the
// backend still decides; this is only an early hint.

import type { Platform } from "@/lib/types";

const patterns: [Platform, RegExp][] = [
  ["youtube", /(?:youtube\.com\/(?:watch\?(?:.*&)?v=|shorts\/|embed\/|live\/|v\/)|youtu\.be\/)[A-Za-z0-9_-]{11}/i],
  ["tiktok", /tiktok\.com\/@[^/?#\s]+\/(?:video|photo)\/\d{8,25}/i],
  ["tiktok", /^https?:\/\/(?:(?:vm|vt)\.tiktok\.com\/|(?:www\.)?tiktok\.com\/t\/)[A-Za-z0-9]+/i], // share links
];

/** The platform of a video link, "unknown" if it isn't one we recognise, or null for an empty input. */
export function detectPlatform(url: string): Platform | "unknown" | null {
  const value = url.trim();
  if (!value) return null;
  return patterns.find(([, re]) => re.test(value))?.[0] ?? "unknown";
}
