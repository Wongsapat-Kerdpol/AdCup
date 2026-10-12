"use client";

// Linked account detection: admins decide whether accounts are the same person (spec section 9).
// Content approval stays in the review queue. Only signal TYPES are shown, never the values.

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Check, Link2, Loader2, ShieldAlert, Users } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import type { LinkedUser, LinkFlag, LinksResponse } from "@/lib/types";
import { cn, formatTHB } from "@/lib/utils";

const labels: Record<string, string> = {
  payout_account: "Payout account",
  google_sub: "Google account",
  email_norm: "Email",
  device_id: "Same device",
  ip: "Same IP",
  signup_time: "Signed up within 10 min",
  submit_time: "Submitted within 1 h",
  manual: "Confirmed by admin",
};

export function signalLabel(type: string) {
  return labels[type] ?? type;
}

const suspectedChecks = ["device_id", "ip", "signup_time", "submit_time"];

export function userLabel(u: LinkedUser) {
  return `${u.display_name} (#${u.id})`;
}

export function LinkedAccountsView() {
  const [data, setData] = useState<LinksResponse | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await api<LinksResponse>("/api/admin/links"));
    } catch (err) {
      toast.error(`Could not load linked accounts: ${(err as Error).message}`);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function act(flag: LinkFlag, action: string, success: string, body?: unknown) {
    setBusy(`${flag.id}:${action}`);
    try {
      await api(`/api/admin/link-flags/${flag.id}/${action}`, { method: "POST", body });
      toast.success(success);
      await load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save the decision");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8 py-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Linked accounts</h1>
        <p className="text-sm text-muted-foreground">
          Accounts of one person share one cap per profile. Strong matches are linked automatically; these need a
          decision. Withdrawals of the accounts involved wait until you decide.
        </p>
      </div>

      <section className="space-y-3">
        <h2 className="font-semibold">Needs a decision</h2>
        {data === null ? (
          <Skeleton className="h-40 rounded-xl" />
        ) : data.flags.length === 0 ? (
          <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed py-10 text-center">
            <Check className="size-8 text-muted-foreground" />
            <p className="font-medium">Nothing to decide</p>
            <p className="text-sm text-muted-foreground">New flags show up here when accounts look linked.</p>
          </div>
        ) : (
          <ul className="space-y-4">
            {data.flags.map((flag) => (
              <li key={flag.id}>
                {flag.kind === "suspected" ? (
                  <SuspectedCard flag={flag} busy={busy} act={act} />
                ) : flag.kind === "hub" ? (
                  <HubCard flag={flag} busy={busy} act={act} />
                ) : (
                  <OverageCard flag={flag} busy={busy} act={act} />
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="font-semibold">Linked groups</h2>
        {data === null ? (
          <Skeleton className="h-24 rounded-xl" />
        ) : data.groups.length === 0 ? (
          <p className="text-sm text-muted-foreground">No accounts are linked yet.</p>
        ) : (
          <ul className="divide-y rounded-xl border bg-card">
            {data.groups.map((g) => (
              <li key={g.group_id} className="flex flex-wrap items-center gap-x-3 gap-y-1.5 p-3 text-sm">
                <Users className="size-4 text-muted-foreground" />
                <span className="font-medium">Profile #{g.group_id}</span>
                <span className="text-muted-foreground">{g.members.map(userLabel).join(", ")}</span>
                <span className="ml-auto flex flex-wrap gap-1">
                  {g.matched.map((m) => (
                    <Badge key={m} variant="secondary">
                      {signalLabel(m)}
                    </Badge>
                  ))}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

type Act = (flag: LinkFlag, action: string, success: string, body?: unknown) => Promise<void>;
type CardProps = { flag: LinkFlag; busy: string | null; act: Act };

function ActionButton({
  flag,
  busy,
  action,
  onClick,
  children,
  variant,
}: {
  flag: LinkFlag;
  busy: string | null;
  action: string;
  onClick: () => void;
  children: React.ReactNode;
  variant?: "default" | "outline";
}) {
  return (
    <Button size="sm" variant={variant} onClick={onClick} disabled={busy !== null}>
      {busy === `${flag.id}:${action}` && <Loader2 className="animate-spin" />}
      {children}
    </Button>
  );
}

function FlagCard({
  tone,
  icon: Icon,
  title,
  children,
  actions,
}: {
  tone: "amber" | "rose";
  icon: typeof AlertTriangle;
  title: React.ReactNode;
  children: React.ReactNode;
  actions: React.ReactNode;
}) {
  const amber = tone === "amber";
  return (
    <div
      className={cn(
        "space-y-3 rounded-xl border p-4",
        amber ? "border-amber-500/40 bg-amber-500/5" : "border-rose-500/40 bg-rose-500/5",
      )}
    >
      <div className="flex items-start gap-2">
        <Icon className={cn("mt-0.5 size-4 shrink-0", amber ? "text-amber-700" : "text-rose-600")} />
        <div className="text-sm font-medium">{title}</div>
      </div>
      <div className="space-y-2 text-sm">{children}</div>
      <div className="flex flex-wrap justify-end gap-2 border-t pt-3">{actions}</div>
    </div>
  );
}

function SuspectedCard({ flag, busy, act }: CardProps) {
  const [a, b] = flag.users;
  return (
    <FlagCard
      tone="amber"
      icon={AlertTriangle}
      title={
        <>
          Possible link: {a && userLabel(a)} and {b && userLabel(b)}
          <Badge variant="warning" className="ml-2">
            Score {flag.score}
          </Badge>
        </>
      }
      actions={
        <>
          <ActionButton
            flag={flag}
            busy={busy}
            action="dismiss"
            variant="outline"
            onClick={() => act(flag, "dismiss", "Marked as different people — withdrawals released")}
          >
            Different people
          </ActionButton>
          <ActionButton
            flag={flag}
            busy={busy}
            action="confirm"
            onClick={() => act(flag, "confirm", "Linked — they now share one cap per profile")}
          >
            <Link2 /> Same person: merge caps
          </ActionButton>
        </>
      }
    >
      <p className="text-muted-foreground">
        Found in {flag.campaign_title ?? "a campaign"}. Not merged: their caps are still separate.
      </p>
      <table className="w-full text-left text-xs">
        <tbody className="divide-y">
          {suspectedChecks.map((check) => {
            const same = flag.reasons.includes(check);
            return (
              <tr key={check}>
                <td className="py-1.5 text-muted-foreground">{signalLabel(check)}</td>
                <td className={cn("py-1.5 text-right font-medium", same ? "text-amber-700" : "text-muted-foreground")}>
                  {same ? "Same" : "Different"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </FlagCard>
  );
}

function HubCard({ flag, busy, act }: CardProps) {
  const payout = flag.signal_type === "payout_account";
  return (
    <FlagCard
      tone={payout ? "rose" : "amber"}
      icon={ShieldAlert}
      title={`One ${signalLabel(flag.signal_type ?? "").toLowerCase()} is used by ${flag.users.length} accounts`}
      actions={
        payout ? (
          <ActionButton
            flag={flag}
            busy={busy}
            action="release"
            onClick={() => act(flag, "release", "Withdrawals released")}
          >
            Release withdrawals
          </ActionButton>
        ) : (
          <ActionButton
            flag={flag}
            busy={busy}
            action="ignore-signal"
            onClick={() => act(flag, "ignore-signal", "Signal ignored — the accounts are no longer linked by it")}
          >
            Agency / manager: ignore this signal
          </ActionButton>
        )
      }
    >
      <p className="text-muted-foreground">{flag.users.map(userLabel).join(", ")}</p>
      <p className="text-muted-foreground">
        {payout
          ? "They are paid to the same account, so they share one cap per profile. Withdrawals are on hold until you check it is not a mule account."
          : flag.signal_type === "google_sub"
            ? "Not linked by this signal: an agency or manager may run several creators' channels. Withdrawals are not held."
            : "Linked by this signal. Ignore it if these really are different people. Withdrawals are not held."}
      </p>
    </FlagCard>
  );
}

function OverageCard({ flag, busy, act }: CardProps) {
  return (
    <FlagCard
      tone="rose"
      icon={ShieldAlert}
      title={`Paid over the cap per profile in ${flag.campaign_title ?? "a campaign"}`}
      actions={
        <>
          <Button size="sm" variant="outline" disabled title="Coming later">
            Reverse
          </Button>
          <ActionButton
            flag={flag}
            busy={busy}
            action="resolve-overage"
            onClick={() => act(flag, "resolve-overage", "Kept — withdrawals released", { action: "keep" })}
          >
            Keep paid amount
          </ActionButton>
        </>
      }
    >
      <p className="text-muted-foreground">
        These accounts were paid separately before they were linked: {flag.users.map(userLabel).join(", ")}. Their
        next payouts in this campaign are already ฿0.
      </p>
      <dl className="grid grid-cols-3 gap-2 text-center text-xs">
        <Figure label="Group paid" value={flag.group_gross} />
        <Figure label="Cap per profile" value={flag.cap_per_profile} />
        <Figure label="Over by" value={flag.amount} strong />
      </dl>
    </FlagCard>
  );
}

function Figure({ label, value, strong }: { label: string; value: string | null; strong?: boolean }) {
  return (
    <div className="rounded-lg bg-muted/40 p-2">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className={strong ? "font-semibold text-rose-600" : "font-medium"}>{value ? formatTHB(value) : "—"}</dd>
    </div>
  );
}
