// [MAIN] Shared campaign card — used by Discover, brand dashboards, submissions, etc.
//
//   <CampaignCard campaign={c} />
//   <CampaignCard campaign={c} href={routes.brandCampaigns} footer={<Badge>Pending</Badge>} />
//
// Marketplace "gig" layout: cover on top, brand + title, price row at the bottom.
// `badge` renders over the cover, top-right (e.g. submission status from Person 2),
// `footer` renders under the price row (e.g. action buttons).

import Link from "next/link";
import { Disc3, Film, Scissors, Sparkles, type LucideIcon } from "lucide-react";

import { PlatformIcon } from "@/components/campaign/platform-icon";
import { Progress } from "@/components/ui/progress";
import { routes } from "@/lib/routes";
import type { Campaign, CampaignCategory } from "@/lib/types";
import { cn, formatTHB } from "@/lib/utils";

// `swatch` + `ink` are the cover color and category icon color shown when the brand didn't upload a thumbnail.
export const categoryMeta: Record<CampaignCategory, { label: string; icon: LucideIcon; swatch: string; ink: string }> = {
  logo: { label: "Logo", icon: Sparkles, swatch: "bg-violet-100", ink: "text-violet-500/70" },
  music: { label: "Music", icon: Disc3, swatch: "bg-rose-100", ink: "text-rose-500/70" },
  clipping: { label: "Clipping", icon: Scissors, swatch: "bg-sky-100", ink: "text-sky-500/70" },
  ugc: { label: "UGC", icon: Film, swatch: "bg-emerald-100", ink: "text-emerald-600/70" },
};

function progressColor(percent: number) {
  if (percent >= 100) return "bg-progress-full";
  if (percent >= 80) return "bg-progress-warn";
  return "bg-progress-ok";
}

/** The brand's own thumbnail, or a color block with the category icon. Fills its parent. */
function Cover({ campaign }: { campaign: Campaign }) {
  return campaign.thumbnail_url ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={campaign.thumbnail_url} alt="" className="size-full object-cover" />
  ) : (
    <CategoryCover category={campaign.category} />
  );
}

function CategoryCover({ category }: { category: CampaignCategory }) {
  const meta = categoryMeta[category];
  return (
    <div className={cn("flex size-full items-center justify-center", meta.swatch)}>
      {/* Scales with the cover: big on Discover cards, small in the square thumbnail. */}
      <meta.icon className={cn("aspect-square h-[36%] w-auto", meta.ink)} strokeWidth={1.5} aria-hidden />
    </div>
  );
}

/** Small square cover for headers and summaries (checkout, detail page). */
export function CampaignThumbnail({ campaign, className }: { campaign: Campaign; className?: string }) {
  return (
    <div className={cn("relative size-16 shrink-0 overflow-hidden rounded-lg border", className)}>
      <Cover campaign={campaign} />
    </div>
  );
}

export function BrandAvatar({ brand, className }: { brand: Campaign["brand"]; className?: string }) {
  return (
    <span
      className={cn(
        "flex size-6 shrink-0 items-center justify-center overflow-hidden rounded-full bg-foreground text-[11px] font-bold text-background",
        className,
      )}
    >
      {brand.avatar_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={brand.avatar_url} alt="" className="size-full object-cover" />
      ) : (
        brand.display_name.slice(0, 1).toUpperCase()
      )}
    </span>
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
  const meta = categoryMeta[campaign.category];

  return (
    <div
      className={cn(
        "group relative flex flex-col overflow-hidden rounded-lg border bg-card transition-[border-color,box-shadow] hover:border-foreground/25 hover:shadow-md",
        className,
      )}
    >
      {/* Stretched link keeps the whole card clickable while footer buttons stay interactive. */}
      <Link href={href ?? routes.campaign(campaign.id)} className="absolute inset-0 z-0" aria-label={campaign.title} />

      <div className="relative aspect-[16/9] border-b">
        <Cover campaign={campaign} />
        <span className="absolute top-2 left-2 rounded-full bg-white/95 px-2 py-0.5 text-[11px] font-semibold shadow-sm">
          {meta.label}
        </span>
        {badge && <div className="absolute top-2 right-2 z-10 rounded-md bg-white shadow-sm">{badge}</div>}
      </div>

      <div className="flex flex-1 flex-col gap-2 p-3">
        <div className="flex items-center gap-2">
          <BrandAvatar brand={campaign.brand} />
          <span className="truncate text-sm font-semibold">{campaign.brand.display_name}</span>
          <span className="ml-auto flex shrink-0 items-center gap-1.5 text-muted-foreground">
            {campaign.platforms.map((p) => (
              <PlatformIcon key={p} platform={p} />
            ))}
          </span>
        </div>

        <h3 className="line-clamp-2 text-[15px] leading-snug group-hover:underline">{campaign.title}</h3>

        <div className="mt-auto space-y-1 pt-1">
          <Progress value={percent} indicatorClassName={progressColor(campaign.paid_out_percent)} />
          <p className="text-xs text-muted-foreground">
            <span className="font-semibold text-foreground">{Math.round(campaign.paid_out_percent)}%</span> of{" "}
            {formatTHB(campaign.total_budget)} paid out
          </p>
        </div>
      </div>

      <div className="flex items-baseline justify-between gap-2 border-t px-3 py-2.5">
        <span className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">Earn</span>
        <span>
          <span className="text-base font-bold">{formatTHB(campaign.rate_per_1m_views)}</span>
          <span className="text-xs text-muted-foreground"> / 1M views</span>
        </span>
      </div>

      {footer && <div className="relative z-10 px-3 pb-3">{footer}</div>}
    </div>
  );
}
