"use client";

// [PERSON 1] /campaigns/[id] — full campaign page.
//   Creator:      <SubmitContentForm> from Person 2 (YouTube only for now)
//   Owner brand:  fund (Person 3) / edit / pause + read-only submissions (Person 2's API)
//   Guest:        sign-in prompt

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ArrowLeft,
  CalendarClock,
  CheckCircle2,
  CreditCard,
  ExternalLink,
  Eye,
  Loader2,
  Pause,
  Pencil,
  Play,
  ShieldCheck,
  Upload,
} from "lucide-react";
import { toast } from "sonner";

import { CampaignThumbnail, categoryMeta } from "@/components/campaign/campaign-card";
import { CampaignOutlookCard } from "@/components/campaign/campaign-outlook";
import { CampaignStatusBadge } from "@/components/campaign/campaign-status-badge";
import { PlatformIcon, platformLabels } from "@/components/campaign/platform-icon";
import { SubmissionStatusBadge } from "@/components/campaign/submission-status-badge";
import { SubmitContentForm } from "@/components/campaign/submit-content-form";
import { useAuth } from "@/components/providers/auth-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import { routes } from "@/lib/routes";
import type { CampaignDetail, Submission, User } from "@/lib/types";
import { daysLeft, formatNumber, formatTHB, toNumber } from "@/lib/utils";

const COMMISSION_RATE = 0.1; // backend/app/core/config.py
const EXAMPLE_VIEWS = [10_000, 100_000, 1_000_000];

export function CampaignDetailView({ campaignId }: { campaignId: string }) {
  const { user, loading: authLoading } = useAuth();
  const [campaign, setCampaign] = useState<CampaignDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setCampaign(await api<CampaignDetail>(`/api/campaigns/${campaignId}`));
    } catch (err) {
      setError(err instanceof ApiError && err.status === 404 ? "This campaign doesn't exist or was deleted." : (err as Error).message);
    }
  }, [campaignId]);

  useEffect(() => {
    load();
  }, [load]);

  if (error) return <Notice title="Campaign not found" text={error} />;
  if (!campaign || authLoading) return <DetailSkeleton />;

  const isOwner = user?.role === "brand" && user.id === campaign.brand.id;
  if (campaign.status === "draft" && !isOwner && user?.role !== "admin") {
    return <Notice title="Not live yet" text="This campaign hasn't launched. Check back soon." />;
  }

  const meta = categoryMeta[campaign.category];
  const left = daysLeft(campaign.deadline);
  const percent = Math.min(campaign.paid_out_percent, 100);

  return (
    <div className="mx-auto max-w-6xl space-y-6 py-4">
      <Link
        href={isOwner ? routes.brandCampaigns : routes.discover}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> {isOwner ? "My campaigns" : "Discover"}
      </Link>

      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <CampaignThumbnail campaign={campaign} className="size-24" />
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <CampaignStatusBadge status={campaign.status} />
            <Badge variant="outline">
              <meta.icon /> {meta.label}
            </Badge>
            {left !== null && (
              <Badge variant={left <= 3 ? "warning" : "secondary"}>
                <CalendarClock /> {left > 0 ? `${left} day${left === 1 ? "" : "s"} left` : "Ended"}
              </Badge>
            )}
          </div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{campaign.title}</h1>
          <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
            <span>by {campaign.brand.display_name}</span>
            <span className="flex items-center gap-1.5">
              {campaign.platforms.map((p) => (
                <span key={p} className="inline-flex items-center gap-1">
                  <PlatformIcon platform={p} /> {platformLabels[p]}
                </span>
              ))}
            </span>
          </div>
        </div>
      </div>

      {/* Pool stats */}
      <div className="rounded-xl border bg-card p-5">
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <BigStat label="Rate" value={formatTHB(campaign.rate_per_1m_views)} sub="per 1M views" />
          <BigStat label="Total budget" value={formatTHB(campaign.total_budget)} />
          <BigStat label="Remaining pool" value={formatTHB(campaign.remaining_budget)} />
          <BigStat label="Paid out" value={`${Math.round(campaign.paid_out_percent)}%`} sub={formatTHB(campaign.paid_out)} />
        </div>
        <Progress value={percent} className="mt-4 h-2" />
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <div className="space-y-6">
          <Section title="About this campaign">
            <p className="text-sm leading-relaxed whitespace-pre-line text-muted-foreground">{campaign.description}</p>
          </Section>

          <Section title="Content requirements">
            <p className="text-xs text-muted-foreground">An admin checks your video against these before it can earn.</p>
            <p className="rounded-lg bg-muted/50 p-4 text-sm leading-relaxed whitespace-pre-line">{campaign.requirements}</p>
          </Section>

          <Section title="Payout terms">
            <dl className="grid gap-3 text-sm sm:grid-cols-2">
              <Term label="Rate per 1,000 views">{formatTHB(campaign.rate_per_1k_views)}</Term>
              <Term label="Minimum views to qualify">{formatNumber(campaign.min_views)}</Term>
              <Term label="Cap per post">{campaign.cap_per_post ? formatTHB(campaign.cap_per_post) : "No limit"}</Term>
              <Term label="Cap per creator">{campaign.cap_per_profile ? formatTHB(campaign.cap_per_profile) : "No limit"}</Term>
              <Term label="Deadline">
                {campaign.deadline ? new Date(campaign.deadline).toLocaleDateString(undefined, { dateStyle: "medium" }) : "None"}
              </Term>
              <Term label="Platform fee">10% of each payout</Term>
            </dl>
          </Section>

          <HowYouGetPaid campaign={campaign} />

          {isOwner && campaign.is_funded && <OwnerSubmissions campaignId={campaign.id} />}
        </div>

        <aside className="h-fit space-y-4 lg:sticky lg:top-20">
          {isOwner ? (
            <OwnerPanel campaign={campaign} onChanged={load} />
          ) : user?.role === "creator" ? (
            <CreatorPanel campaign={campaign} user={user} />
          ) : !user ? (
            <GuestPanel />
          ) : (
            <div className="rounded-xl border bg-card p-5 text-sm text-muted-foreground">
              Only creators can submit videos to campaigns.
            </div>
          )}
          {campaign.is_funded && !isOwner && <CampaignOutlookCard campaignId={campaign.id} />}
          <EarningsExample campaign={campaign} />
        </aside>
      </div>
    </div>
  );
}

function CreatorPanel({ campaign, user }: { campaign: CampaignDetail; user: User }) {
  const [submitted, setSubmitted] = useState(false);

  if (campaign.status !== "active") {
    return (
      <Panel title="Submit your video">
        <p className="text-sm text-muted-foreground">
          This campaign is {campaign.status === "paused" ? "paused" : "closed"} and not accepting submissions.
        </p>
      </Panel>
    );
  }
  if (!user.youtube_channel_id) {
    return (
      <Panel title="Submit your video">
        <p className="text-sm text-muted-foreground">
          Connect your YouTube channel first — we use it to confirm the video is yours and to track its views.
        </p>
        <Button asChild className="w-full">
          <Link href={routes.settings}>
            <PlatformIcon platform="youtube" className="size-4" /> Connect YouTube
          </Link>
        </Button>
      </Panel>
    );
  }
  return (
    <Panel title="Submit your video">
      <p className="text-sm text-muted-foreground">
        Post an original video on your channel <span className="text-foreground">{user.youtube_channel_title}</span>,
        then paste the link.
      </p>
      <SubmitContentForm campaignId={campaign.id} onSubmitted={() => setSubmitted(true)} />
      {submitted && (
        <p className="flex items-center gap-2 text-sm text-green-400">
          <CheckCircle2 className="size-4" /> Submitted!{" "}
          <Link href={routes.submissions} className="underline">
            Track it in My Submissions
          </Link>
        </p>
      )}
    </Panel>
  );
}

function OwnerPanel({ campaign, onChanged }: { campaign: CampaignDetail; onChanged: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);

  async function setStatus(status: "active" | "paused") {
    setBusy(true);
    try {
      await api(`/api/brand/campaigns/${campaign.id}`, { method: "PATCH", body: { status } });
      toast.success(status === "paused" ? "Campaign paused — hidden from Discover" : "Campaign is live again");
      await onChanged();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel title="Manage campaign">
      {!campaign.is_funded ? (
        <>
          <p className="text-sm text-muted-foreground">
            This is a draft. Fund the budget to publish it on Discover and start accepting videos.
          </p>
          <Button asChild className="w-full">
            <Link href={routes.fundCampaign(campaign.id)}>
              <CreditCard /> Fund {formatTHB(campaign.total_budget)}
            </Link>
          </Button>
        </>
      ) : (
        <p className="text-sm text-muted-foreground">
          {campaign.status === "active" && "Live on Discover. Admins review every video before it earns."}
          {campaign.status === "paused" && "Paused: hidden from Discover and not accepting new videos."}
          {campaign.status === "completed" && "This campaign has ended."}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {campaign.status !== "completed" && (
          <Button asChild variant="outline" size="sm">
            <Link href={routes.editCampaign(campaign.id)}>
              <Pencil /> Edit
            </Link>
          </Button>
        )}
        {campaign.status === "active" && (
          <Button variant="outline" size="sm" disabled={busy} onClick={() => setStatus("paused")}>
            {busy ? <Loader2 className="animate-spin" /> : <Pause />} Pause
          </Button>
        )}
        {campaign.status === "paused" && (
          <Button variant="outline" size="sm" disabled={busy} onClick={() => setStatus("active")}>
            {busy ? <Loader2 className="animate-spin" /> : <Play />} Resume
          </Button>
        )}
      </div>
    </Panel>
  );
}

function GuestPanel() {
  const pathname = usePathname();
  return (
    <Panel title="Want to earn from this?">
      <p className="text-sm text-muted-foreground">Sign in as a creator to submit your video.</p>
      <div className="flex gap-2">
        <Button asChild className="flex-1">
          <Link href={`${routes.login}?next=${encodeURIComponent(pathname)}`}>Sign in</Link>
        </Button>
        <Button asChild variant="outline" className="flex-1">
          <Link href={`${routes.register}?next=${encodeURIComponent(pathname)}`}>Sign up</Link>
        </Button>
      </div>
    </Panel>
  );
}

/** Read-only for brands: admins approve/reject (Person 2's review queue). */
function OwnerSubmissions({ campaignId }: { campaignId: number }) {
  const [subs, setSubs] = useState<Submission[] | null>(null);

  useEffect(() => {
    api<Submission[]>(`/api/submissions/campaign/${campaignId}`)
      .then(setSubs)
      .catch((err) => {
        toast.error(`Could not load submissions: ${(err as Error).message}`);
        setSubs([]);
      });
  }, [campaignId]);

  return (
    <section id="submissions" className="scroll-mt-20 space-y-4 rounded-xl border bg-card p-5">
      <div>
        <h2 className="font-semibold">Submissions {subs && <span className="text-muted-foreground">({subs.length})</span>}</h2>
        <p className="text-sm text-muted-foreground">Read-only. Our admins check each video against your requirements.</p>
      </div>
      {!subs ? (
        <Skeleton className="h-24" />
      ) : subs.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">No videos submitted yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground">
              <tr className="border-b">
                <th className="py-2 pr-3 font-medium">Video</th>
                <th className="py-2 pr-3 font-medium">Status</th>
                <th className="py-2 pr-3 text-right font-medium">Views</th>
                <th className="py-2 text-right font-medium">Paid</th>
              </tr>
            </thead>
            <tbody>
              {subs.map((s) => (
                <tr key={s.id} className="border-b last:border-0">
                  <td className="max-w-64 py-2.5 pr-3">
                    <a
                      href={s.video_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 hover:text-primary"
                    >
                      <span className="truncate">{s.video_title ?? s.video_url}</span>
                      <ExternalLink className="size-3 shrink-0" />
                    </a>
                    {s.rejection_reason && <p className="text-xs text-muted-foreground">{s.rejection_reason}</p>}
                  </td>
                  <td className="py-2.5 pr-3">
                    <SubmissionStatusBadge status={s.status} />
                  </td>
                  <td className="py-2.5 pr-3 text-right tabular-nums">{formatNumber(s.view_count)}</td>
                  <td className="py-2.5 text-right tabular-nums">{formatTHB(s.gross_amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function HowYouGetPaid({ campaign }: { campaign: CampaignDetail }) {
  const steps = [
    {
      icon: Upload,
      title: "Post & submit",
      text: "Upload an original video to your YouTube channel and submit the link here.",
    },
    {
      icon: ShieldCheck,
      title: "System check",
      text: `We confirm it's your video, posted after launch, and has at least ${formatNumber(campaign.min_views)} views.`,
    },
    {
      icon: Eye,
      title: "Admin review",
      text: "An admin watches the video and checks it against the requirements above.",
    },
    {
      icon: CheckCircle2,
      title: "Earn as views grow",
      text: `Every new 1,000 views pays ${formatTHB(campaign.rate_per_1k_views)} (minus the 10% fee) into your wallet at the next payout round.`,
    },
  ];
  return (
    <Section title="How you get paid">
      <ol className="grid gap-3 sm:grid-cols-2">
        {steps.map((s, i) => (
          <li key={s.title} className="flex gap-3 rounded-lg bg-muted/40 p-3">
            <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
              <s.icon className="size-4" />
            </span>
            <div>
              <p className="text-sm font-medium">
                {i + 1}. {s.title}
              </p>
              <p className="text-xs text-muted-foreground">{s.text}</p>
            </div>
          </li>
        ))}
      </ol>
      <p className="text-xs text-muted-foreground">
        Everyone approved is paid together in payout rounds. If the pool can&apos;t cover everyone, smaller earners are
        paid in full first and the rest is split equally — approval order doesn&apos;t matter. Once the pool runs out,
        the campaign ends.
      </p>
    </Section>
  );
}

function EarningsExample({ campaign }: { campaign: CampaignDetail }) {
  const rate = toNumber(campaign.rate_per_1k_views);
  const capPost = campaign.cap_per_post ? toNumber(campaign.cap_per_post) : Infinity;
  return (
    <div className="space-y-3 rounded-xl border bg-card p-5">
      <h2 className="text-sm font-semibold">What one video could earn</h2>
      <dl className="space-y-2 text-sm">
        {EXAMPLE_VIEWS.map((views) => {
          const gross = Math.min((views / 1000) * rate, capPost);
          const capped = gross === capPost;
          return (
            <div key={views} className="flex items-center justify-between gap-3">
              <dt className="text-muted-foreground">{formatNumber(views)} views</dt>
              <dd className="text-right font-medium">
                {formatTHB(Math.round(gross * (1 - COMMISSION_RATE) * 100) / 100)}
                {capped && <span className="ml-1 text-xs text-muted-foreground">(cap)</span>}
              </dd>
            </div>
          );
        })}
      </dl>
      <p className="text-xs text-muted-foreground">After the 10% platform fee, while the pool lasts.</p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3 rounded-xl border bg-card p-5">
      <h2 className="font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-3 rounded-xl border bg-card p-5">
      <h2 className="font-semibold">{title}</h2>
      {children}
    </div>
  );
}

function BigStat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-xl font-bold">{value}</div>
      {sub && <div className="text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}

function Term({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg bg-muted/40 px-3 py-2">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right font-medium">{children}</dd>
    </div>
  );
}

function Notice({ title, text }: { title: string; text: string }) {
  return (
    <div className="mx-auto max-w-md space-y-3 py-16 text-center">
      <h1 className="text-xl font-bold">{title}</h1>
      <p className="text-sm text-muted-foreground">{text}</p>
      <Button asChild variant="outline">
        <Link href={routes.discover}>Browse campaigns</Link>
      </Button>
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="mx-auto max-w-6xl space-y-6 py-4">
      <div className="flex gap-4">
        <Skeleton className="size-24 rounded-lg" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-8 w-3/4" />
        </div>
      </div>
      <Skeleton className="h-28 rounded-xl" />
      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <Skeleton className="h-96 rounded-xl" />
        <Skeleton className="h-60 rounded-xl" />
      </div>
    </div>
  );
}
