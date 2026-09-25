import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Backend sends Decimals as strings — accept both. */
export function toNumber(value: string | number | null | undefined): number {
  if (value === null || value === undefined) return 0;
  return typeof value === "number" ? value : Number(value);
}

/** ฿25,000 — or ฿25K with compact=true. */
export function formatTHB(value: string | number, opts: { compact?: boolean } = {}) {
  const n = toNumber(value);
  return (
    "฿" +
    new Intl.NumberFormat("en-US", {
      notation: opts.compact ? "compact" : "standard",
      maximumFractionDigits: opts.compact ? 1 : n % 1 === 0 ? 0 : 2,
    }).format(n)
  );
}

export function formatNumber(value: string | number) {
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(
    toNumber(value),
  );
}

export function daysLeft(deadline: string | null): number | null {
  if (!deadline) return null;
  return Math.ceil((new Date(deadline).getTime() - Date.now()) / 86_400_000);
}
