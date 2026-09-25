"use client";

// [PERSON 3] Admin analytics: headline commission revenue, key figures, 14-day payout chart,
// submissions per status (links to Person 2's review queue) and campaign performance.

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Banknote, Coins, Landmark, RefreshCw, Users } from "lucide-react";
import { toast } from "sonner";

import { SubmissionStatusBadge } from "@/components/campaign/submission-status-badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { routes } from "@/lib/routes";
import type { AdminStats, SubmissionStatus } from "@/lib/types";
import { cn, formatNumber, formatTHB, toNumber } from "@/lib/utils";

// Single-series data color, validated against the dark card surface (dataviz lightness/contrast checks).
const DATA_COLOR = "#3b82f6";

export function AdminDashboard() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      setStats(await api<AdminStats>("/api/admin/stats"));
    } catch (err) {
      toast.error(`Could not load analytics: ${(err as Error).message}`);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (!stats) return <DashboardSkeleton />;
  const { users, money } = stats;

  return (
    <div className="mx-auto max-w-6xl space-y-6 py-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Analytics</h1>
          <p className="text-sm text-muted-foreground">Platform health, money flow and campaign performance.</p>
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          <RefreshCw className={cn(loading && "animate-spin")} /> Refresh
        </Button>
      </div>

      {/* Headline + key figures */}
      <div className="grid gap-4 lg:grid-cols-[1.2fr_2fr]">
        <section className="flex flex-col justify-between gap-4 rounded-xl border bg-card p-5">
          <div>
            <p className="text-sm text-muted-foreground">Commission revenue</p>
            <p className="text-5xl font-bold tracking-tight">{formatTHB(money.commission_revenue)}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              10% of {formatTHB(money.total_paid_out)} paid out to creators
            </p>
          </div>
          <div className="rounded-lg bg-muted/50 p-3 text-sm">
            <span className="text-muted-foreground">Projected: </span>
            <span className="font-semibold">+{formatTHB(money.projected_commission)}</span>
            <span className="text-muted-foreground">
              {" "}
              if the {formatTHB(money.locked_in_pools, { compact: true })} still in active pools is paid out
            </span>
          </div>
        </section>

        <section className="grid grid-cols-2 gap-3">
          <Stat
            icon={Users}
            label="Active users (30 days)"
            value={formatNumber(users.active_last_30d)}
            note={`${users.total} total · ${users.new_last_30d} new`}
          />
          <Stat
            icon={Landmark}
            label="Funded by brands"
            value={formatTHB(money.total_funded, { compact: true })}
            note={`${money.transaction_count} transactions in total`}
          />
          <Stat
            icon={Coins}
            label="Paid out to creators"
            value={formatTHB(money.total_paid_out, { compact: true })}
            note="gross, before commission"
          />
          <Stat
            icon={Banknote}
            label="Cashed out"
            value={formatTHB(money.total_withdrawn, { compact: true })}
            note="creator withdrawals"
          />
        </section>
      </div>

      {/* Daily chart */}
      <DailyPayoutChart daily={stats.daily} />

      <div className="grid gap-4 lg:grid-cols-[1fr_2fr]">
        {/* Submissions per status */}
        <section className="space-y-3 rounded-xl border bg-card p-5">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Submissions</h2>
            <Link href={routes.adminReview} className="flex items-center gap-1 text-sm text-primary hover:underline">
              Review queue <ArrowRight className="size-3.5" />
            </Link>
          </div>
          <StatusBars counts={stats.submissions_by_status} />
          <div className="border-t pt-3">
            <p className="mb-2 text-xs text-muted-foreground">Users by role</p>
            <dl className="grid grid-cols-3 gap-2 text-center">
              {(["creator", "brand", "admin"] as const).map((role) => (
                <div key={role} className="rounded-lg bg-muted/50 py-2">
                  <dd className="text-lg font-semibold">{users.by_role[role]}</dd>
                  <dt className="text-xs text-muted-foreground capitalize">{role}s</dt>
                </div>
              ))}
            </dl>
          </div>
        </section>

        {/* Campaign performance */}
        <section className="space-y-3 rounded-xl border bg-card p-5">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Campaign performance</h2>
            <span className="text-xs text-muted-foreground">
              {stats.campaigns_by_status.active} active · {stats.campaigns_by_status.draft} draft ·{" "}
              {stats.campaigns_by_status.completed} completed
            </span>
          </div>
          {stats.top_campaigns.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">No funded campaigns yet.</p>
          ) : (
            <div className="-mx-5 overflow-x-auto">
              <table className="w-full min-w-[560px] text-sm">
                <thead>
                  <tr className="border-b text-left text-xs text-muted-foreground">
                    <th className="px-5 pb-2 font-medium">Campaign</th>
                    <th className="pb-2 font-medium">Paid out</th>
                    <th className="pb-2 text-right font-medium">Submissions</th>
                    <th className="px-5 pb-2 text-right font-medium">Views</th>
                  </tr>
                </thead>
                <tbody className="divide-y tabular-nums">
                  {stats.top_campaigns.map((c) => (
                    <tr key={c.id}>
                      <td className="max-w-[220px] px-5 py-2.5">
                        <Link href={routes.campaign(c.id)} className="block truncate font-medium hover:underline">
                          {c.title}
                        </Link>
                        <span className="text-xs text-muted-foreground">{c.brand_name}</span>
                      </td>
                      <td className="w-44 py-2.5">
                        <div className="mb-1 flex justify-between text-xs">
                          <span className="font-medium">{Math.round(c.paid_out_percent)}%</span>
                          <span className="text-muted-foreground">of {formatTHB(c.total_budget, { compact: true })}</span>
                        </div>
                        <Progress value={c.paid_out_percent} />
                      </td>
                      <td className="py-2.5 text-right">
                        {c.approved}
                        <span className="text-muted-foreground"> / {c.submissions}</span>
                        <div className="text-xs text-muted-foreground">approved</div>
                      </td>
                      <td className="px-5 py-2.5 text-right">{formatNumber(c.views)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function Stat({ icon: Icon, label, value, note }: { icon: typeof Users; label: string; value: string; note: string }) {
  return (
    <div className="rounded-xl border bg-card p-4">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Icon className="size-4 text-primary" /> {label}
      </div>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
      <p className="text-xs text-muted-foreground">{note}</p>
    </div>
  );
}

const STATUS_ORDER: SubmissionStatus[] = ["pending", "under_review", "approved", "rejected"];

function StatusBars({ counts }: { counts: Record<SubmissionStatus, number> }) {
  const max = Math.max(...STATUS_ORDER.map((s) => counts[s]), 1);
  return (
    <ul className="space-y-2.5">
      {STATUS_ORDER.map((s) => (
        <li key={s} className="space-y-1">
          <div className="flex items-center justify-between text-sm">
            <SubmissionStatusBadge status={s} />
            <span className="font-medium tabular-nums">{counts[s]}</span>
          </div>
          {/* Magnitude only; identity is carried by the badge label, so every bar shares one hue. */}
          <div className="h-1.5 rounded-full bg-muted">
            <div
              className="h-full rounded-full"
              style={{ width: `${(counts[s] / max) * 100}%`, background: DATA_COLOR }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}

/** Clean axis ticks (0, 500, 1,000 …) whose top is the first clean value at or above max. */
function niceTicks(max: number) {
  if (max <= 0) return [0, 1, 2, 3, 4];
  const rough = max / 5;
  const pow = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * pow).find((s) => s >= rough) ?? rough;
  return Array.from({ length: Math.ceil(max / step) + 1 }, (_, i) => i * step);
}

function DailyPayoutChart({ daily }: { daily: AdminStats["daily"] }) {
  const [hover, setHover] = useState<number | null>(null);
  const [asTable, setAsTable] = useState(false);
  const values = daily.map((d) => toNumber(d.paid_out));
  const ticks = niceTicks(Math.max(...values));
  const top = ticks[ticks.length - 1];
  const fmtDay = (iso: string, opts: Intl.DateTimeFormatOptions) =>
    new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-GB", { timeZone: "UTC", ...opts });

  return (
    <section className="space-y-3 rounded-xl border bg-card p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold">Paid out to creators per day</h2>
          <p className="text-xs text-muted-foreground">Gross payouts, last 14 days (UTC)</p>
        </div>
        <Button variant="ghost" size="sm" onClick={() => setAsTable((v) => !v)}>
          {asTable ? "Show chart" : "Show table"}
        </Button>
      </div>

      {asTable ? (
        <div className="-mx-5 overflow-x-auto">
          <table className="w-full text-sm tabular-nums">
            <thead>
              <tr className="border-b text-left text-xs text-muted-foreground">
                <th className="px-5 pb-2 font-medium">Day</th>
                <th className="pb-2 text-right font-medium">Paid out</th>
                <th className="pb-2 text-right font-medium">Commission</th>
                <th className="px-5 pb-2 text-right font-medium">Funded</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {daily.map((d) => (
                <tr key={d.day}>
                  <td className="px-5 py-1.5">{fmtDay(d.day, { day: "numeric", month: "short" })}</td>
                  <td className="py-1.5 text-right">{formatTHB(d.paid_out)}</td>
                  <td className="py-1.5 text-right">{formatTHB(d.commission)}</td>
                  <td className="px-5 py-1.5 text-right">{formatTHB(d.funded)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="flex gap-2 pt-3">
          {/* Y axis */}
          <div className="relative h-48 w-12 shrink-0 text-right text-[11px] text-muted-foreground tabular-nums">
            {ticks.map((t) => (
              <span key={t} className="absolute right-0 -translate-y-1/2" style={{ bottom: `${(t / top) * 100}%` }}>
                {formatTHB(t, { compact: true })}
              </span>
            ))}
          </div>

          <div className="min-w-0 flex-1">
            <div className="relative h-48" onMouseLeave={() => setHover(null)}>
              {/* Hairline grid */}
              {ticks.map((t) => (
                <div
                  key={t}
                  className="absolute inset-x-0 border-t border-border"
                  style={{ bottom: `${(t / top) * 100}%` }}
                />
              ))}

              <div className="absolute inset-0 flex items-end">
                {daily.map((d, i) => (
                  // The whole column slot is the hover target, wider than the bar itself.
                  <div
                    key={d.day}
                    className="relative flex h-full flex-1 items-end justify-center"
                    onMouseEnter={() => setHover(i)}
                    onFocus={() => setHover(i)}
                    onBlur={() => setHover(null)}
                    tabIndex={0}
                    aria-label={`${fmtDay(d.day, { day: "numeric", month: "short" })}: ${formatTHB(d.paid_out)} paid out`}
                  >
                    {hover === i && <div className="absolute inset-y-0 w-full rounded bg-accent/50" />}
                    <div
                      className="relative w-full max-w-6 rounded-t-[4px]"
                      style={{ height: `${(values[i] / top) * 100}%`, background: DATA_COLOR, margin: "0 1px" }}
                    />
                  </div>
                ))}
              </div>

              {hover !== null && (
                <div
                  className="pointer-events-none absolute top-0 z-10 w-44 -translate-x-1/2 rounded-lg border bg-popover p-2.5 text-xs shadow-lg"
                  style={{ left: `clamp(88px, ${((hover + 0.5) / daily.length) * 100}%, calc(100% - 88px))` }}
                >
                  <p className="mb-1 font-medium">
                    {fmtDay(daily[hover].day, { weekday: "short", day: "numeric", month: "short" })}
                  </p>
                  <TooltipRow label="Paid out" value={daily[hover].paid_out} swatch />
                  <TooltipRow label="Commission" value={daily[hover].commission} />
                  <TooltipRow label="Funded" value={daily[hover].funded} />
                </div>
              )}
            </div>

            {/* X axis */}
            <div className="mt-1.5 flex text-[11px] text-muted-foreground tabular-nums">
              {daily.map((d, i) => (
                <span key={d.day} className={cn("flex-1 text-center", i % 2 === 1 && "max-sm:invisible")}>
                  {fmtDay(d.day, { day: "numeric" })}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function TooltipRow({ label, value, swatch }: { label: string; value: string; swatch?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="flex items-center gap-1.5 text-muted-foreground">
        {swatch && <span className="size-2 rounded-sm" style={{ background: DATA_COLOR }} />}
        {label}
      </span>
      <span className="font-medium tabular-nums">{formatTHB(value)}</span>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="mx-auto max-w-6xl space-y-6 py-6">
      <Skeleton className="h-8 w-48" />
      <div className="grid gap-4 lg:grid-cols-[1.2fr_2fr]">
        <Skeleton className="h-52 rounded-xl" />
        <Skeleton className="h-52 rounded-xl" />
      </div>
      <Skeleton className="h-72 rounded-xl" />
    </div>
  );
}
