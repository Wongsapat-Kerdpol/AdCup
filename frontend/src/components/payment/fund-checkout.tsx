"use client";

// [PERSON 3] Mock checkout for /campaigns/[id]/fund.
// The brand "pays" the full budget; the backend marks the campaign funded + active and writes
// Transaction(type=campaign_fund). No real money moves and no card data is collected.

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, CheckCircle2, CreditCard, Info, Loader2, QrCode, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

import { CampaignThumbnail } from "@/components/campaign/campaign-card";
import { useAuth } from "@/components/providers/auth-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import { routes } from "@/lib/routes";
import type { CampaignDetail, CheckoutResponse, PaymentMethod } from "@/lib/types";
import { cn, formatNumber, formatTHB } from "@/lib/utils";

const methods: { value: PaymentMethod; label: string; hint: string; icon: typeof QrCode }[] = [
  { value: "promptpay", label: "PromptPay QR", hint: "Scan with any banking app", icon: QrCode },
  { value: "card", label: "Credit / debit card", hint: "Test card, nothing is charged", icon: CreditCard },
];

export function FundCheckout({ campaignId }: { campaignId: string }) {
  const { user } = useAuth();
  const [campaign, setCampaign] = useState<CampaignDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [method, setMethod] = useState<PaymentMethod>("promptpay");
  const [paying, setPaying] = useState(false);
  const [receipt, setReceipt] = useState<CheckoutResponse | null>(null);

  useEffect(() => {
    api<CampaignDetail>(`/api/campaigns/${campaignId}`)
      .then(setCampaign)
      .catch((err) => setLoadError(err instanceof ApiError && err.status === 404 ? "Campaign not found." : err.message));
  }, [campaignId]);

  async function pay() {
    setPaying(true);
    try {
      // Short pause so the mock feels like a payment gateway round-trip.
      await new Promise((r) => setTimeout(r, 1200));
      const res = await api<CheckoutResponse>(`/api/payments/checkout/${campaignId}`, {
        method: "POST",
        body: { method },
      });
      setReceipt(res);
      toast.success("Campaign funded — it is now live on Discover");
    } catch (err) {
      toast.error(`Payment failed: ${(err as Error).message}`);
    } finally {
      setPaying(false);
    }
  }

  if (loadError) return <Notice title="Can't open checkout" text={loadError} />;
  if (!campaign || !user) return <CheckoutSkeleton />;
  if (campaign.brand.id !== user.id) return <Notice title="Not your campaign" text="You can only fund campaigns you created." />;
  if (receipt) return <Receipt campaign={campaign} receipt={receipt} />;
  if (campaign.is_funded) {
    return (
      <Notice
        title="Already funded"
        text="This campaign's budget is already locked in the pool."
        action={<Link href={routes.campaign(campaign.id)}>View campaign</Link>}
      />
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 py-6">
      <div className="space-y-1">
        <Link
          href={routes.campaign(campaign.id)}
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" /> Back to campaign
        </Link>
        <h1 className="text-2xl font-bold tracking-tight">Fund campaign</h1>
        <p className="text-sm text-muted-foreground">
          Lock the reward budget into the pool. The campaign goes live as soon as payment succeeds.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        {/* Payment method */}
        <section className="space-y-4 rounded-xl border bg-card p-5">
          <h2 className="font-semibold">Payment method</h2>
          <div className="grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label="Payment method">
            {methods.map((m) => (
              <button
                key={m.value}
                type="button"
                role="radio"
                aria-checked={method === m.value}
                onClick={() => setMethod(m.value)}
                disabled={paying}
                className={cn(
                  "flex items-start gap-3 rounded-lg border p-3 text-left transition-colors",
                  method === m.value ? "border-primary/60 bg-primary/10" : "hover:bg-accent",
                )}
              >
                <m.icon className="mt-0.5 size-5 shrink-0 text-primary" />
                <span>
                  <span className="block text-sm font-medium">{m.label}</span>
                  <span className="block text-xs text-muted-foreground">{m.hint}</span>
                </span>
              </button>
            ))}
          </div>

          {method === "promptpay" ? <MockQr amount={campaign.total_budget} /> : <MockCard />}

          <p className="flex items-start gap-2 rounded-lg bg-amber-500/10 p-3 text-xs text-amber-700">
            <Info className="mt-0.5 size-4 shrink-0" />
            Simulated checkout for the course project — no real money is transferred.
          </p>
        </section>

        {/* Order summary */}
        <aside className="h-fit space-y-4 rounded-xl border bg-card p-5">
          <h2 className="font-semibold">Order summary</h2>
          <div className="flex gap-3">
            <CampaignThumbnail campaign={campaign} className="size-12" />
            <div className="min-w-0">
              <p className="line-clamp-2 text-sm font-medium">{campaign.title}</p>
              <p className="text-xs text-muted-foreground">{campaign.brand.display_name}</p>
            </div>
          </div>

          <dl className="space-y-2 border-t pt-4 text-sm">
            <Row label="Rate">{formatTHB(campaign.rate_per_1m_views)} / 1M views</Row>
            <Row label="Min. views to qualify">{formatNumber(campaign.min_views)}</Row>
            {campaign.cap_per_post && <Row label="Cap per post">{formatTHB(campaign.cap_per_post)}</Row>}
            {campaign.cap_per_profile && <Row label="Cap per creator">{formatTHB(campaign.cap_per_profile)}</Row>}
            {campaign.deadline && <Row label="Deadline">{new Date(campaign.deadline).toLocaleDateString()}</Row>}
          </dl>

          <div className="flex items-end justify-between border-t pt-4">
            <span className="text-sm text-muted-foreground">Total to pay</span>
            <span className="text-2xl font-bold">{formatTHB(campaign.total_budget)}</span>
          </div>
          <p className="text-xs text-muted-foreground">
            The platform&apos;s 10% commission is taken from creator payouts, not added to your budget.
          </p>

          <Button size="lg" className="w-full" onClick={pay} disabled={paying}>
            {paying ? (
              <>
                <Loader2 className="animate-spin" /> Processing…
              </>
            ) : (
              <>
                <ShieldCheck /> Pay {formatTHB(campaign.total_budget)}
              </>
            )}
          </Button>
        </aside>
      </div>
    </div>
  );
}

function Receipt({ campaign, receipt }: { campaign: CampaignDetail; receipt: CheckoutResponse }) {
  return (
    <div className="mx-auto max-w-md space-y-5 py-10 text-center">
      <CheckCircle2 className="mx-auto size-14 text-green-700" />
      <div className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">Payment successful</h1>
        <p className="text-sm text-muted-foreground">
          <span className="font-medium text-foreground">{campaign.title}</span> is now live and accepting submissions.
        </p>
      </div>
      <dl className="space-y-2 rounded-xl border bg-card p-4 text-left text-sm">
        <Row label="Amount">{formatTHB(receipt.amount)}</Row>
        <Row label="Method">{methods.find((m) => m.value === receipt.method)?.label}</Row>
        <Row label="Reference">
          <span className="font-mono text-xs">{receipt.reference}</span>
        </Row>
        <Row label="Paid at">{new Date(receipt.paid_at).toLocaleString()}</Row>
        <Row label="Status">
          <Badge variant="success">{receipt.campaign_status}</Badge>
        </Row>
      </dl>
      <div className="flex justify-center gap-2">
        <Button asChild variant="outline">
          <Link href={routes.brandCampaigns}>My campaigns</Link>
        </Button>
        <Button asChild>
          <Link href={routes.campaign(campaign.id)}>View campaign</Link>
        </Button>
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right font-medium">{children}</dd>
    </div>
  );
}

/** Decorative QR-like pattern. Not scannable on purpose — this is a mock. */
function MockQr({ amount }: { amount: string }) {
  const n = 21;
  const finder = (x: number, y: number) =>
    [
      [0, 0],
      [n - 7, 0],
      [0, n - 7],
    ].some(([fx, fy]) => x >= fx && x < fx + 7 && y >= fy && y < fy + 7);
  const cells: [number, number][] = [];
  for (let y = 0; y < n; y++)
    for (let x = 0; x < n; x++) if (!finder(x, y) && (x * 7 + y * 13 + x * y) % 5 < 2) cells.push([x, y]);

  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed p-4">
      <svg viewBox={`-1 -1 ${n + 2} ${n + 2}`} className="size-40 rounded bg-white" aria-label="Demo QR code">
        {[
          [0, 0],
          [n - 7, 0],
          [0, n - 7],
        ].map(([x, y]) => (
          <g key={`${x}-${y}`}>
            <rect x={x} y={y} width={7} height={7} fill="#000" />
            <rect x={x + 1} y={y + 1} width={5} height={5} fill="#fff" />
            <rect x={x + 2} y={y + 2} width={3} height={3} fill="#000" />
          </g>
        ))}
        {cells.map(([x, y]) => (
          <rect key={`${x}-${y}`} x={x} y={y} width={1} height={1} fill="#000" />
        ))}
      </svg>
      <p className="text-sm font-medium">{formatTHB(amount)}</p>
      <p className="text-xs text-muted-foreground">Demo QR — press Pay to simulate a successful scan.</p>
    </div>
  );
}

/** Read-only Stripe-style test card, so nobody types a real card number into the demo. */
function MockCard() {
  return (
    <div className="space-y-2 rounded-lg border border-dashed p-4 text-sm">
      <Field label="Card number" value="4242 4242 4242 4242" />
      <div className="grid grid-cols-2 gap-2">
        <Field label="Expiry" value="12 / 34" />
        <Field label="CVC" value="123" />
      </div>
      <p className="text-xs text-muted-foreground">Test card only — fields are locked.</p>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="mb-1 text-xs text-muted-foreground">{label}</div>
      <div className="rounded-md border bg-muted/40 px-3 py-2 font-mono text-muted-foreground">{value}</div>
    </div>
  );
}

function Notice({ title, text, action }: { title: string; text: string; action?: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-md space-y-3 py-16 text-center">
      <h1 className="text-xl font-bold">{title}</h1>
      <p className="text-sm text-muted-foreground">{text}</p>
      {action ? (
        <Button asChild variant="outline">
          {action}
        </Button>
      ) : (
        <Button asChild variant="outline">
          <Link href={routes.brandCampaigns}>My campaigns</Link>
        </Button>
      )}
    </div>
  );
}

function CheckoutSkeleton() {
  return (
    <div className="mx-auto grid max-w-4xl gap-6 py-6 lg:grid-cols-[1fr_340px]">
      <Skeleton className="h-80 rounded-xl" />
      <Skeleton className="h-80 rounded-xl" />
    </div>
  );
}
