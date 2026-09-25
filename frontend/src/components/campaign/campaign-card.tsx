// [MAIN] Shared campaign card — used by Discover, brand dashboards, submissions, etc.
//
//   <CampaignCard campaign={c} />
//   <CampaignCard campaign={c} href={routes.brandCampaigns} footer={<Badge>Pending</Badge>} />
//
// `badge` renders top-right (e.g. submission status from Person 2),
// `footer` renders below the progress bar (e.g. action buttons).

import Link from "next/link";
import { Disc3, Film, Scissors, Sparkles, type LucideIcon } from "lucide-react";

import { PlatformIcon } from "@/components/campaign/platform-icon";
import { Progress } from "@/components/ui/progress";
import { routes } from "@/lib/routes";
import type { Campaign, CampaignCategory } from "@/lib/types";
import { cn, formatTHB } from "@/lib/utils";

export const categoryMeta: Record<CampaignCategory, { label: string; icon: LucideIcon; gradient: string }> = {
  logo: { label: "Logo", icon: Sparkles, gradient: "from-violet-600 to-indigo-900" },
  music: { label: "Music", icon: Disc3, gradient: "from-rose-600 to-orange-900" },
  clipping: { label: "Clipping", icon: Scissors, gradient: "from-sky-600 to-cyan-900" },
  ugc: { label: "UGC", icon: Film, gradient: "from-emerald-600 to-teal-900" },
};

function progressColor(percent: number) {
  if (percent >= 100) return "bg-progress-full";
  if (percent >= 80) return "bg-progress-warn";
  return "bg-progress-ok";
}

export function CampaignThumbnail({ campaign, className }: { campaign: Campaign; className?: string }) {
  const meta = categoryMeta[campaign.category];
  return (
    <div className={cn("relative size-16 shrink-0 overflow-hidden rounded-lg", className)}>
      {campaign.thumbnail_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={campaign.thumbnail_url} alt="" className="size-full object-cover" />
      ) : (
        <div className={cn("flex size-full items-center justify-center bg-gradient-to-br", meta.gradient)}>
          <meta.icon className="size-7 text-white/85" />
        </div>
      )}
      <span className="absolute inset-x-0 bottom-0 bg-black/70 py-0.5 text-center text-[10px] font-semibold text-primary">
        {meta.label}
      </span>
    </div>
  );
}

export function CampaignCard({
  campaign,
  href,
  badge,
  footer,
  className,
}: {
  campaign: Campaign;
  href?: string;
  badge?: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
}) {
  const percent = Math.min(campaign.paid_out_percent, 100);

  return (
    <div
      className={cn(
        "group relative flex flex-col gap-3 rounded-xl border bg-card p-3 transition-colors hover:border-primary/40 hover:bg-accent/40",
        className,
      )}
    >
      {/* Stretched link keeps the whole card clickable while footer buttons stay interactive. */}
      <Link href={href ?? routes.campaign(campaign.id)} className="absolute inset-0 z-0 rounded-xl" aria-label={campaign.title} />

      <div className="flex gap-3">
        <CampaignThumbnail campaign={campaign} />
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <h3 className="line-clamp-2 text-sm leading-snug font-semibold">{campaign.title}</h3>
            {badge && <div className="relative z-10 shrink-0">{badge}</div>}
          </div>
          <p className="mt-0.5 truncate text-xs text-muted-foreground">{campaign.brand.display_name}</p>
          <div className="mt-1.5 flex items-center gap-1.5 text-muted-foreground">
            {campaign.platforms.map((p) => (
              <PlatformIcon key={p} platform={p} />
            ))}
          </div>
        </div>
      </div>

      <div>
        <div className="mb-1.5 flex items-end justify-between text-xs">
          <div>
            <div className="text-muted-foreground">Paid out</div>
            <div>
              <span className="font-semibold">{Math.round(campaign.paid_out_percent)}%</span>
              <span className="text-muted-foreground"> / {formatTHB(campaign.total_budget)}</span>
            </div>
          </div>
          <div className="text-right">
            <div className="text-muted-foreground">Rate</div>
            <div>
              <span className="font-semibold">{formatTHB(campaign.rate_per_1m_views)}</span>
              <span className="text-muted-foreground"> / 1M</span>
            </div>
          </div>
        </div>
        <Progress value={percent} indicatorClassName={progressColor(campaign.paid_out_percent)} />
      </div>

      {footer && <div className="relative z-10">{footer}</div>}
    </div>
  );
}
