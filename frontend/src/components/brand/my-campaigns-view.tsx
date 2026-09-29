"use client";

// [PERSON 1] /brand/campaigns — the brand's own campaigns (drafts included) with spend and submission stats.
// Brands only watch submissions here; admins approve them (Person 2's review queue).

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { CreditCard, Eye, Loader2, Megaphone, Pause, Pencil, Play, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { CampaignCard } from "@/components/campaign/campaign-card";
import { CampaignStatusBadge } from "@/components/campaign/campaign-status-badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { routes } from "@/lib/routes";
import type { BrandCampaign, CampaignStatus } from "@/lib/types";
import { cn, formatNumber, formatTHB, toNumber } from "@/lib/utils";

const tabs: { value: CampaignStatus | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "active", label: "Live" },
  { value: "draft", label: "Drafts" },
  { value: "paused", label: "Paused" },
  { value: "completed", label: "Completed" },
];

export function MyCampaignsView() {
  const [campaigns, setCampaigns] = useState<BrandCampaign[] | null>(null);
  const [tab, setTab] = useState<CampaignStatus | "all">("all");

  const load = useCallback(async () => {
    try {
      setCampaigns(await api<BrandCampaign[]>("/api/brand/campaigns"));
    } catch (err) {
      toast.error(`Could not load your campaigns: ${(err as Error).message}`);
      setCampaigns([]);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (!campaigns) return <DashboardSkeleton />;

  const funded = campaigns.filter((c) => c.is_funded);
  const totals = {
    live: campaigns.filter((c) => c.status === "active").length,
    budget: funded.reduce((s, c) => s + toNumber(c.total_budget), 0),
    paid: funded.reduce((s, c) => s + toNumber(c.paid_out), 0),
    views: campaigns.reduce((s, c) => s + c.stats.total_views, 0),
    submissions: campaigns.reduce(
      (s, c) => s + Object.values(c.stats.submissions).reduce((a, b) => a + b, 0),
      0,
    ),
  };
  const shown = tab === "all" ? campaigns : campaigns.filter((c) => c.status === tab);

  return (
    <div className="space-y-6 py-2">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">My campaigns</h1>
          <p className="text-sm text-muted-foreground">Track spend and submissions across your campaigns.</p>
        </div>
        <Button asChild>
          <Link href={routes.newCampaign}>
            <Plus /> New campaign
          </Link>
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Live campaigns" value={`${totals.live} / ${campaigns.length}`} />
        <Stat label="Paid out" value={formatTHB(totals.paid)} sub={`of ${formatTHB(totals.budget)} funded`} />
        <Stat label="Views on approved videos" value={formatNumber(totals.views)} />
        <Stat label="Submissions" value={String(totals.submissions)} />
      </div>

      {campaigns.length === 0 ? (
        <EmptyState />
      ) : (
        <>
          <div className="flex flex-wrap gap-1.5">
            {tabs.map((t) => {
              const count = t.value === "all" ? campaigns.length : campaigns.filter((c) => c.status === t.value).length;
              return (
                <button
                  key={t.value}
                  onClick={() => setTab(t.value)}
                  className={cn(
                    "rounded-full border px-3 py-1 text-sm transition-colors hover:bg-accent",
                    tab === t.value && "border-primary bg-primary/10 text-foreground",
                  )}
                >
                  {t.label} <span className="text-muted-foreground">{count}</span>
                </button>
              );
            })}
          </div>

          {shown.length === 0 ? (
            <p className="py-10 text-center text-sm text-muted-foreground">No campaigns here.</p>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {shown.map((c) => (
                <CampaignCard
                  key={c.id}
                  campaign={c}
                  badge={<CampaignStatusBadge status={c.status} />}
                  footer={<CampaignFooter campaign={c} onChanged={load} />}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function CampaignFooter({ campaign: c, onChanged }: { campaign: BrandCampaign; onChanged: () => Promise<void> }) {
  const [busy, setBusy] = useState<"status" | "delete" | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const s = c.stats.submissions;

  async function setStatus(status: "active" | "paused") {
    setBusy("status");
    try {
      await api(`/api/brand/campaigns/${c.id}`, { method: "PATCH", body: { status } });
      toast.success(status === "paused" ? "Campaign paused — hidden from Discover" : "Campaign is live again");
      await onChanged();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function remove() {
    setBusy("delete");
    try {
      await api(`/api/brand/campaigns/${c.id}`, { method: "DELETE" });
      toast.success("Draft deleted");
      await onChanged();
    } catch (err) {
      toast.error((err as Error).message);
      setBusy(null);
    }
  }

  return (
    <div className="space-y-3 border-t pt-3">
      {c.is_funded ? (
        <div className="grid grid-cols-4 gap-1 text-center text-xs">
          <MiniStat label="Checking" value={s.pending} />
          <MiniStat label="In review" value={s.under_review} />
          <MiniStat label="Earning" value={s.approved} />
          <MiniStat label="Creators" value={c.stats.creators} />
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">Not visible to creators until you fund it.</p>
      )}

      <div className="flex flex-wrap gap-2">
        {!c.is_funded && (
          <Button asChild size="sm">
            <Link href={routes.fundCampaign(c.id)}>
              <CreditCard /> Fund {formatTHB(c.total_budget, { compact: true })}
            </Link>
          </Button>
        )}
        {c.is_funded && (
          <Button asChild size="sm" variant="secondary">
            <Link href={`${routes.campaign(c.id)}#submissions`}>
              <Eye /> Submissions
            </Link>
          </Button>
        )}
        {c.status !== "completed" && (
          <Button asChild size="sm" variant="outline">
            <Link href={routes.editCampaign(c.id)}>
              <Pencil /> Edit
            </Link>
          </Button>
        )}
        {c.status === "active" && (
          <Button size="sm" variant="ghost" disabled={!!busy} onClick={() => setStatus("paused")}>
            {busy === "status" ? <Loader2 className="animate-spin" /> : <Pause />} Pause
          </Button>
        )}
        {c.status === "paused" && (
          <Button size="sm" variant="ghost" disabled={!!busy} onClick={() => setStatus("active")}>
            {busy === "status" ? <Loader2 className="animate-spin" /> : <Play />} Resume
          </Button>
        )}
        {!c.is_funded &&
          (confirmDelete ? (
            <span className="flex items-center gap-1">
              <Button size="sm" variant="destructive" disabled={!!busy} onClick={remove}>
                {busy === "delete" && <Loader2 className="animate-spin" />} Delete draft
              </Button>
              <Button size="sm" variant="ghost" disabled={!!busy} onClick={() => setConfirmDelete(false)}>
                Cancel
              </Button>
            </span>
          ) : (
            <Button size="sm" variant="ghost" onClick={() => setConfirmDelete(true)} aria-label="Delete draft">
              <Trash2 />
            </Button>
          ))}
      </div>
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl border bg-card p-4">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-xl font-bold">{value}</div>
      {sub && <div className="text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md bg-muted/50 py-1.5">
      <div className="font-semibold">{value}</div>
      <div className="text-muted-foreground">{label}</div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed py-16 text-center">
      <Megaphone className="size-8 text-primary" />
      <div>
        <p className="font-medium">No campaigns yet</p>
        <p className="text-sm text-muted-foreground">Create one, fund it, and creators can start posting.</p>
      </div>
      <Button asChild>
        <Link href={routes.newCampaign}>
          <Plus /> Create your first campaign
        </Link>
      </Button>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6 py-2">
      <Skeleton className="h-10 w-60" />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-20 rounded-xl" />
        ))}
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-56 rounded-xl" />
        ))}
      </div>
    </div>
  );
}
