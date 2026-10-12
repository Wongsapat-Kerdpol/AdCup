"use client";

// [PERSON 1] Create / edit campaign form. Used by /campaigns/new and /brand/campaigns/[id]/edit.
// Rules mirror CampaignCreate in backend/app/schemas/campaign_manage.py — keep them in sync.
// After create -> /campaigns/{id}/fund (Person 3 mock checkout).

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Info, Loader2, Lock } from "lucide-react";
import { toast } from "sonner";

import { CampaignCard, categoryMeta } from "@/components/campaign/campaign-card";
import { PlatformIcon, platformLabels } from "@/components/campaign/platform-icon";
import { useAuth } from "@/components/providers/auth-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { routes } from "@/lib/routes";
import type { Campaign, CampaignCategory, CampaignDetail, CampaignInput, Platform } from "@/lib/types";
import { cn, formatNumber, formatTHB } from "@/lib/utils";

const DEFAULT_MIN_VIEWS = 1000; // backend/app/core/config.py
const SUPPORTED_PLATFORMS: Platform[] = ["youtube", "tiktok"]; // SUPPORTED_SUBMISSION_PLATFORMS
const ALL_PLATFORMS: Platform[] = ["youtube", "tiktok"];
const MONEY_RE = /^\d+(\.\d{1,2})?$/;

type Values = {
  title: string;
  description: string;
  requirements: string;
  category: CampaignCategory;
  thumbnail_url: string;
  rate: string;
  budget: string;
  capPost: string;
  capProfile: string;
  minViews: string;
  deadline: string; // yyyy-mm-dd (local)
};
type Errors = Partial<Record<keyof Values, string>>;

function toValues(c?: CampaignDetail): Values {
  return {
    title: c?.title ?? "",
    description: c?.description ?? "",
    requirements: c?.requirements ?? "",
    category: c?.category ?? "ugc",
    thumbnail_url: c?.thumbnail_url ?? "",
    rate: c ? String(Number(c.rate_per_1k_views)) : "",
    budget: c ? String(Number(c.total_budget)) : "",
    capPost: c?.cap_per_post ? String(Number(c.cap_per_post)) : "",
    capProfile: c?.cap_per_profile ? String(Number(c.cap_per_profile)) : "",
    minViews: String(c?.min_views ?? DEFAULT_MIN_VIEWS),
    deadline: c?.deadline ? new Date(c.deadline).toLocaleDateString("en-CA") : "",
  };
}

function toPayload(v: Values, platforms: Platform[]): CampaignInput {
  return {
    title: v.title.trim(),
    description: v.description.trim(),
    requirements: v.requirements.trim(),
    category: v.category,
    platforms,
    thumbnail_url: v.thumbnail_url.trim() || null,
    rate_per_1k_views: v.rate.trim(),
    total_budget: v.budget.trim(),
    cap_per_post: v.capPost.trim() || null,
    cap_per_profile: v.capProfile.trim() || null,
    min_views: Number(v.minViews),
    // End of the chosen day in the brand's timezone, sent as UTC.
    deadline: v.deadline ? new Date(`${v.deadline}T23:59:59`).toISOString() : null,
  };
}

function validate(v: Values, checkDeadline: boolean): Errors {
  const e: Errors = {};
  const len = (s: string) => s.trim().length;
  if (len(v.title) < 3) e.title = "At least 3 characters";
  else if (len(v.title) > 200) e.title = "At most 200 characters";
  if (len(v.description) < 10) e.description = "At least 10 characters";
  if (len(v.requirements) < 10) e.requirements = "Tell the reviewer what must be in the video (10+ characters)";
  if (v.thumbnail_url.trim() && !/^https?:\/\//.test(v.thumbnail_url.trim())) e.thumbnail_url = "Must start with http:// or https://";

  const money = (s: string, field: keyof Values, required: boolean) => {
    if (!s.trim()) {
      if (required) e[field] = "Required";
      return null;
    }
    if (!MONEY_RE.test(s.trim()) || Number(s) <= 0) {
      e[field] = "A positive amount, max 2 decimals";
      return null;
    }
    return Number(s);
  };
  const rate = money(v.rate, "rate", true);
  const budget = money(v.budget, "budget", true);
  const capPost = money(v.capPost, "capPost", false);
  const capProfile = money(v.capProfile, "capProfile", false);
  if (rate !== null && rate > 100_000) e.rate = "At most ฿100,000 per 1K views";
  if (budget !== null && budget > 100_000_000) e.budget = "At most ฿100,000,000";
  if (budget !== null && capPost !== null && capPost > budget) e.capPost = "Can't be more than the total budget";
  if (budget !== null && capProfile !== null && capProfile > budget) e.capProfile = "Can't be more than the total budget";
  if (capPost !== null && capProfile !== null && capPost > capProfile && !e.capPost) e.capPost = "Can't be more than the cap per creator";

  if (!/^\d+$/.test(v.minViews.trim())) e.minViews = "A whole number, 0 or more";
  if (checkDeadline && v.deadline && new Date(`${v.deadline}T23:59:59`) <= new Date()) e.deadline = "Must be in the future";
  return e;
}

/** FastAPI 422 errors arrive JSON-encoded in ApiError.message — pull out the first readable message. */
function readableError(err: unknown): string {
  const message = (err as Error).message;
  try {
    const detail = JSON.parse(message);
    if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg).replace(/^Value error, /, "");
  } catch {}
  return message;
}

export function CampaignForm({ campaign }: { campaign?: CampaignDetail }) {
  const { user } = useAuth();
  const router = useRouter();
  const editing = !!campaign;
  const moneyLocked = !!campaign?.is_funded; // backend rejects money changes after funding
  const initial = useMemo(() => toValues(campaign), [campaign]);
  const initialPlatforms = useMemo<Platform[]>(() => {
    const kept = (campaign?.platforms ?? []).filter((p) => SUPPORTED_PLATFORMS.includes(p));
    return kept.length ? kept : ["youtube"];
  }, [campaign]);
  const [platforms, setPlatforms] = useState<Platform[]>(initialPlatforms);

  function togglePlatform(p: Platform) {
    setPlatforms((current) =>
      current.includes(p)
        ? current.length > 1 // a campaign must accept at least one platform
          ? current.filter((x) => x !== p)
          : current
        : SUPPORTED_PLATFORMS.filter((x) => x === p || current.includes(x)), // keep a stable order
    );
  }

  const [values, setValues] = useState<Values>(initial);
  const [errors, setErrors] = useState<Errors>({});
  const [saving, setSaving] = useState(false);

  function set<K extends keyof Values>(field: K, value: Values[K]) {
    setValues((v) => ({ ...v, [field]: value }));
    if (errors[field]) setErrors((e) => ({ ...e, [field]: undefined }));
  }
  const bind = (field: keyof Values) => ({
    id: field,
    value: values[field],
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => set(field, e.target.value),
    "aria-invalid": !!errors[field],
  });

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const found = validate(values, values.deadline !== initial.deadline);
    setErrors(found);
    if (Object.keys(found).length) {
      toast.error("Please fix the highlighted fields");
      return;
    }

    setSaving(true);
    try {
      if (!campaign) {
        const created = await api<CampaignDetail>("/api/brand/campaigns", {
          method: "POST",
          body: toPayload(values, platforms),
        });
        toast.success("Campaign created — fund it to go live");
        router.push(routes.fundCampaign(created.id));
        return;
      }
      // PATCH only what changed, so untouched fields (e.g. a funded campaign's money rules) aren't re-sent.
      const next = toPayload(values, platforms);
      const before = toPayload(initial, initialPlatforms);
      const changes = Object.fromEntries(
        (Object.keys(next) as (keyof CampaignInput)[])
          .filter((k) => JSON.stringify(next[k]) !== JSON.stringify(before[k]))
          .map((k) => [k, next[k]]),
      );
      if (Object.keys(changes).length === 0) {
        toast.info("No changes to save");
        setSaving(false);
        return;
      }
      await api<CampaignDetail>(`/api/brand/campaigns/${campaign.id}`, { method: "PATCH", body: changes });
      toast.success("Campaign updated");
      router.push(routes.campaign(campaign.id));
    } catch (err) {
      toast.error(readableError(err));
      setSaving(false);
    }
  }

  // Live preview built from the form, shaped like the Discover card.
  const rate = Number(values.rate) || 0;
  const budget = Number(values.budget) || 0;
  const preview: Campaign = {
    id: campaign?.id ?? 0,
    title: values.title.trim() || "Your campaign title",
    category: values.category,
    platforms,
    thumbnail_url: /^https?:\/\//.test(values.thumbnail_url.trim()) ? values.thumbnail_url.trim() : null,
    status: campaign?.status ?? "draft",
    total_budget: String(budget),
    paid_out: campaign?.paid_out ?? "0",
    paid_out_percent: campaign?.paid_out_percent ?? 0,
    remaining_budget: String(budget),
    rate_per_1k_views: String(rate),
    rate_per_1m_views: String(rate * 1000),
    deadline: values.deadline || null,
    created_at: campaign?.created_at ?? new Date().toISOString(),
    brand: { id: user?.id ?? 0, display_name: user?.display_name ?? "Your brand", avatar_url: user?.avatar_url ?? null },
  };
  const coveredViews = rate > 0 ? (budget / rate) * 1000 : 0;

  return (
    <div className="mx-auto max-w-6xl space-y-6 py-6">
      <div className="space-y-1">
        <Link
          href={editing ? routes.campaign(campaign.id) : routes.brandCampaigns}
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" /> {editing ? "Back to campaign" : "My campaigns"}
        </Link>
        <h1 className="text-2xl font-bold tracking-tight">{editing ? "Edit campaign" : "Create a campaign"}</h1>
        <p className="text-sm text-muted-foreground">
          {editing
            ? "Changes show up for creators right away."
            : "Set your content rules and pay rate. You'll fund the budget on the next step, then it goes live."}
        </p>
      </div>

      <form onSubmit={handleSubmit} noValidate className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <div className="space-y-6">
          {/* Basics */}
          <Section title="Campaign details">
            <FormField label="Title" htmlFor="title" error={errors.title}>
              <Input {...bind("title")} placeholder="Siam Coffee — Morning Ritual [UGC]" maxLength={200} />
            </FormField>

            <FormField label="Category" error={errors.category}>
              <div role="radiogroup" aria-label="Category" className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {(Object.keys(categoryMeta) as CampaignCategory[]).map((cat) => {
                  const meta = categoryMeta[cat];
                  const active = values.category === cat;
                  return (
                    <button
                      key={cat}
                      type="button"
                      role="radio"
                      aria-checked={active}
                      onClick={() => set("category", cat)}
                      className={cn(
                        "flex items-center gap-2 rounded-lg border p-3 text-sm font-medium transition-colors hover:bg-accent",
                        active && "border-primary bg-primary/10 hover:bg-primary/10",
                      )}
                    >
                      <meta.icon className={cn("size-4", active ? "text-primary" : "text-muted-foreground")} />
                      {meta.label}
                    </button>
                  );
                })}
              </div>
            </FormField>

            <FormField label="Description" htmlFor="description" error={errors.description} hint="What is the campaign about?">
              <Textarea
                {...bind("description")}
                rows={4}
                maxLength={5000}
                placeholder="Create an original short video featuring our new cold brew…"
              />
            </FormField>

            <FormField
              label="Thumbnail URL"
              htmlFor="thumbnail_url"
              error={errors.thumbnail_url}
              hint="Optional. Without one, the card shows a plain color."
            >
              <Input {...bind("thumbnail_url")} placeholder="https://…/cover.jpg" maxLength={500} />
            </FormField>
          </Section>

          {/* Requirements */}
          <Section
            title="Content requirements"
            description="An admin checks every approved video against these before it can earn. Be specific."
          >
            <FormField label="Requirements" htmlFor="requirements" error={errors.requirements} hint="One rule per line.">
              <Textarea
                {...bind("requirements")}
                rows={5}
                maxLength={5000}
                placeholder={"• Show the bottle clearly for at least 3 seconds\n• Mention @siamcoffee in the description\n• Original content only, no reposts"}
              />
            </FormField>
          </Section>

          {/* Money */}
          <Section
            title="Budget & payout"
            description="Creators earn per view from a shared pool, paid out to everyone together in payout rounds. A 10% platform fee comes out of creator payouts, not your budget."
          >
            {moneyLocked && (
              <p className="flex items-start gap-2 rounded-lg bg-muted p-3 text-xs text-muted-foreground">
                <Lock className="mt-0.5 size-3.5 shrink-0" />
                This campaign is funded, so its budget and payout rules are locked.
              </p>
            )}
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField
                label="Rate per 1,000 views"
                htmlFor="rate"
                error={errors.rate}
                hint={rate > 0 ? `= ${formatTHB(rate * 1000)} per 1M views` : "THB"}
              >
                <MoneyInput {...bind("rate")} placeholder="25" disabled={moneyLocked} />
              </FormField>
              <FormField label="Total budget" htmlFor="budget" error={errors.budget} hint="The amount you'll fund.">
                <MoneyInput {...bind("budget")} placeholder="50000" disabled={moneyLocked} />
              </FormField>
              <FormField label="Cap per post" htmlFor="capPost" error={errors.capPost} hint="Optional. Max one video can earn.">
                <MoneyInput {...bind("capPost")} placeholder="No limit" disabled={moneyLocked} />
              </FormField>
              <FormField
                label="Cap per creator"
                htmlFor="capProfile"
                error={errors.capProfile}
                hint="Optional. Max one creator can earn in total."
              >
                <MoneyInput {...bind("capProfile")} placeholder="No limit" disabled={moneyLocked} />
              </FormField>
              <FormField
                label="Minimum views to qualify"
                htmlFor="minViews"
                error={errors.minViews}
                hint="Videos below this wait before admin review."
              >
                <Input {...bind("minViews")} type="number" inputMode="numeric" min={0} step={1} disabled={moneyLocked} />
              </FormField>
            </div>
          </Section>

          {/* Schedule + platforms */}
          <Section title="Schedule & platforms">
            <FormField
              label="Deadline"
              htmlFor="deadline"
              error={errors.deadline}
              hint="Optional. Submissions close at the end of this day."
            >
              <Input
                {...bind("deadline")}
                type="date"
                min={new Date(Date.now() + 86_400_000).toLocaleDateString("en-CA")}
                className="w-fit"
              />
            </FormField>
            <FormField label="Platforms" hint="Where creators may post. Pick at least one.">
              <div className="flex flex-wrap gap-2">
                {ALL_PLATFORMS.map((p) => {
                  const supported = SUPPORTED_PLATFORMS.includes(p);
                  const selected = platforms.includes(p);
                  if (!supported) {
                    return (
                      <span
                        key={p}
                        className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm text-muted-foreground opacity-60"
                      >
                        <PlatformIcon platform={p} />
                        {platformLabels[p]}
                        <span className="text-[10px] uppercase">Soon</span>
                      </span>
                    );
                  }
                  return (
                    <button
                      key={p}
                      type="button"
                      aria-pressed={selected}
                      onClick={() => togglePlatform(p)}
                      className={cn(
                        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition-colors",
                        selected ? "border-primary bg-primary/10" : "text-muted-foreground hover:bg-accent",
                      )}
                    >
                      <PlatformIcon platform={p} />
                      {platformLabels[p]}
                    </button>
                  );
                })}
              </div>
            </FormField>
          </Section>
        </div>

        {/* Preview + submit */}
        <aside className="h-fit space-y-4 lg:sticky lg:top-20">
          <div className="space-y-2">
            <p className="text-sm font-medium">Preview on Discover</p>
            <CampaignCard campaign={preview} className="pointer-events-none" />
          </div>

          <div className="space-y-2 rounded-xl border bg-card p-4 text-sm">
            <Row label="Rate">{rate > 0 ? `${formatTHB(rate * 1000)} / 1M views` : "—"}</Row>
            <Row label="Budget">{budget > 0 ? formatTHB(budget) : "—"}</Row>
            <Row label="Pays for about">{coveredViews > 0 ? `${formatNumber(coveredViews)} views` : "—"}</Row>
          </div>

          {!editing && (
            <p className="flex items-start gap-2 text-xs text-muted-foreground">
              <Info className="mt-0.5 size-3.5 shrink-0" />
              Saved as a draft. It only shows on Discover after you fund it.
            </p>
          )}

          <Button type="submit" size="lg" className="w-full" disabled={saving}>
            {saving && <Loader2 className="animate-spin" />}
            {editing ? "Save changes" : "Create & continue to payment"}
          </Button>
        </aside>
      </form>
    </div>
  );
}

function Section({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <section className="space-y-4 rounded-xl border bg-card p-5">
      <div className="space-y-1">
        <h2 className="font-semibold">{title}</h2>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </div>
      {children}
    </section>
  );
}

function FormField({
  label,
  htmlFor,
  hint,
  error,
  children,
}: {
  label: string;
  htmlFor?: string;
  hint?: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <label htmlFor={htmlFor} className="text-sm font-medium">
        {label}
      </label>
      {children}
      {error ? (
        <p className="text-xs text-destructive">{error}</p>
      ) : (
        hint && <p className="text-xs text-muted-foreground">{hint}</p>
      )}
    </div>
  );
}

function MoneyInput(props: React.ComponentProps<typeof Input>) {
  return (
    <div className="relative">
      <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-sm text-muted-foreground">฿</span>
      <Input {...props} inputMode="decimal" className="pl-7" />
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right font-medium">{children}</span>
    </div>
  );
}
