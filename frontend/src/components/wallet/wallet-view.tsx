"use client";

// [PERSON 3] Creator wallet. Balance grows with every payout increment (Person 2's engine);
// cash out is a mock that only debits the balance and writes a withdrawal transaction.

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowDownLeft,
  ArrowUpRight,
  Banknote,
  Clock,
  Loader2,
  Lock,
  Percent,
  TrendingUp,
  Wallet as WalletIcon,
} from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/components/providers/auth-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { routes } from "@/lib/routes";
import type { Wallet, WalletTransaction, WithdrawResponse } from "@/lib/types";
import { cn, formatNumber, formatTHB, toNumber } from "@/lib/utils";

export function WalletView() {
  const { refresh: refreshUser } = useAuth();
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [amount, setAmount] = useState("");
  const [withdrawing, setWithdrawing] = useState(false);

  const load = useCallback(async () => {
    try {
      const w = await api<Wallet>("/api/wallet");
      setWallet(w);
      setAmount(w.can_withdraw ? String(toNumber(w.balance)) : "");
    } catch (err) {
      toast.error(`Could not load wallet: ${(err as Error).message}`);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (!wallet) return <WalletSkeleton />;

  const balance = toNumber(wallet.balance);
  const min = toNumber(wallet.min_withdrawal);
  const value = Number(amount);
  const amountError =
    amount === "" || Number.isNaN(value)
      ? "Enter an amount"
      : value < min
        ? `Minimum is ${formatTHB(min)}`
        : value > balance
          ? "More than your balance"
          : !/^\d+(\.\d{1,2})?$/.test(amount)
            ? "Up to 2 decimal places"
            : null;

  async function withdraw() {
    if (amountError) return;
    setWithdrawing(true);
    try {
      const res = await api<WithdrawResponse>("/api/wallet/withdraw", { method: "POST", body: { amount } });
      toast.success(`Cash out of ${formatTHB(res.transaction.net_amount)} requested (${res.transaction.reference})`);
      await Promise.all([load(), refreshUser()]); // refreshUser keeps the header balance in sync
    } catch (err) {
      toast.error(`Cash out failed: ${(err as Error).message}`);
    } finally {
      setWithdrawing(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 py-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Wallet</h1>
        <p className="text-sm text-muted-foreground">
          Earnings from approved videos land here every time their views are refreshed (after the 10% commission).
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
        {/* Balance + cash out */}
        <section className="space-y-4 rounded-xl border border-primary/25 bg-gradient-to-br from-primary/15 via-card to-card p-5">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <WalletIcon className="size-4 text-primary" /> Available balance
          </div>
          <div className="text-4xl font-bold tracking-tight">{formatTHB(balance)}</div>

          {wallet.withdrawals_on_hold ? (
            // Linked account detection: the reason is never shown to the creator (spec D16).
            <div className="space-y-3">
              <div className="flex items-start gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
                <Clock className="mt-0.5 size-4 shrink-0 text-amber-400" />
                <p>Withdrawals are on hold while we review your account. This usually takes 1–2 days.</p>
              </div>
              <Button disabled>
                <Banknote /> Cash out
              </Button>
            </div>
          ) : wallet.can_withdraw ? (
            <div className="space-y-2">
              <label htmlFor="amount" className="text-sm font-medium">
                Cash out amount (THB)
              </label>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Input
                    id="amount"
                    inputMode="decimal"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value.replace(/[^\d.]/g, ""))}
                    aria-invalid={!!amountError}
                    disabled={withdrawing}
                    className="pr-14"
                  />
                  <button
                    type="button"
                    onClick={() => setAmount(String(balance))}
                    disabled={withdrawing}
                    className="absolute top-1/2 right-2 -translate-y-1/2 rounded px-2 py-0.5 text-xs font-medium text-primary hover:bg-primary/10"
                  >
                    Max
                  </button>
                </div>
                <Button onClick={withdraw} disabled={!!amountError || withdrawing}>
                  {withdrawing ? <Loader2 className="animate-spin" /> : <Banknote />}
                  Cash out
                </Button>
              </div>
              <p className={cn("text-xs", amountError ? "text-destructive" : "text-muted-foreground")}>
                {amountError ?? `Minimum ${formatTHB(min)}. Simulated — no real bank transfer.`}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-1.5 text-muted-foreground">
                  <Lock className="size-3.5" /> Cash out unlocks at {formatTHB(min)}
                </span>
                <span className="font-medium">{formatTHB(Math.max(min - balance, 0))} to go</span>
              </div>
              <Progress value={(balance / min) * 100} />
            </div>
          )}
        </section>

        {/* Lifetime totals */}
        <section className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
          <Stat icon={TrendingUp} label="Total earned (net)" value={wallet.total_earned} />
          <Stat icon={Percent} label="Platform commission (10%)" value={wallet.total_commission} />
          <Stat icon={ArrowUpRight} label="Cashed out" value={wallet.total_withdrawn} />
        </section>
      </div>

      {/* History */}
      <section className="space-y-3">
        <h2 className="font-semibold">Transaction history</h2>
        {wallet.transactions.length === 0 ? (
          <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed py-12 text-center">
            <WalletIcon className="size-8 text-muted-foreground" />
            <p className="font-medium">No earnings yet</p>
            <p className="text-sm text-muted-foreground">
              Submit a video to a campaign — once it&apos;s approved, payouts show up here.
            </p>
            <Button asChild variant="outline" size="sm" className="mt-1">
              <Link href={routes.discover}>Find a campaign</Link>
            </Button>
          </div>
        ) : (
          <ul className="divide-y rounded-xl border bg-card">
            {wallet.transactions.map((tx) => (
              <TransactionRow key={tx.id} tx={tx} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function TransactionRow({ tx }: { tx: WalletTransaction }) {
  const incoming = tx.type === "payout";
  const title =
    tx.type === "payout"
      ? `Payout · ${tx.campaign_title ?? `Campaign #${tx.campaign_id}`}`
      : tx.type === "withdrawal"
        ? "Cash out"
        : `Campaign funding · ${tx.campaign_title ?? `#${tx.campaign_id}`}`;

  const details = [
    new Date(tx.created_at).toLocaleString(),
    tx.views_from !== null && tx.views_to !== null
      ? `${formatNumber(tx.views_from)} → ${formatNumber(tx.views_to)} views`
      : null,
    tx.reference,
  ].filter(Boolean);

  return (
    <li className="flex items-center gap-3 p-3 sm:p-4">
      <div
        className={cn(
          "flex size-9 shrink-0 items-center justify-center rounded-full",
          incoming ? "bg-green-500/15 text-green-400" : "bg-muted text-muted-foreground",
        )}
      >
        {incoming ? <ArrowDownLeft className="size-4" /> : <ArrowUpRight className="size-4" />}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{title}</p>
        <p className="truncate text-xs text-muted-foreground">{details.join(" · ")}</p>
      </div>
      <div className="shrink-0 text-right">
        <p className={cn("text-sm font-semibold", incoming && "text-green-400")}>
          {incoming ? "+" : "−"}
          {formatTHB(tx.net_amount)}
        </p>
        {incoming && toNumber(tx.commission_amount) > 0 && (
          <p className="text-xs text-muted-foreground">
            {formatTHB(tx.gross_amount)} − {formatTHB(tx.commission_amount)} fee
          </p>
        )}
        {tx.status !== "completed" && <p className="text-xs text-amber-400">{tx.status}</p>}
      </div>
    </li>
  );
}

function Stat({ icon: Icon, label, value }: { icon: typeof TrendingUp; label: string; value: string }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border bg-card p-4">
      <Icon className="size-5 shrink-0 text-primary" />
      <div>
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-lg font-semibold">{formatTHB(value)}</p>
      </div>
    </div>
  );
}

function WalletSkeleton() {
  return (
    <div className="mx-auto max-w-5xl space-y-6 py-6">
      <Skeleton className="h-8 w-40" />
      <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
        <Skeleton className="h-48 rounded-xl" />
        <Skeleton className="h-48 rounded-xl" />
      </div>
      <Skeleton className="h-64 rounded-xl" />
    </div>
  );
}
