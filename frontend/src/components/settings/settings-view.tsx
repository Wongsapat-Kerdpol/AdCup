"use client";

// [PERSON 3] Settings: profile summary + YouTube connect/disconnect (+ payout account, linked account detection).
// Connect: GET /api/youtube/connect -> redirect to Google -> backend callback -> back here with
// ?youtube=<result>, which we turn into a toast and then strip from the URL.

import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { CheckCircle2, ExternalLink, Landmark, Loader2, ShieldCheck, Unlink } from "lucide-react";
import { toast } from "sonner";

import { PlatformIcon } from "@/components/campaign/platform-icon";
import { useAuth } from "@/components/providers/auth-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/lib/api";
import type { PayoutMethod, PayoutMethodResponse, User } from "@/lib/types";

const callbackMessages: Record<string, { ok: boolean; text: string }> = {
  connected: { ok: true, text: "YouTube channel connected" },
  denied: { ok: false, text: "Connection cancelled on Google" },
  no_channel: { ok: false, text: "That Google account has no YouTube channel — create one first or pick another account" },
  channel_taken: { ok: false, text: "That channel is already linked to another AdCup account" },
  missing_scope: {
    ok: false,
    text: "Tick “View your YouTube account” on Google's screen — we need it to confirm your channel",
  },
  expired: { ok: false, text: "The connect link expired — please try again" },
  error: { ok: false, text: "Could not connect YouTube — please try again" },
};

export function SettingsView() {
  const { user, refresh } = useAuth();
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const handled = useRef(false);

  // Result of the OAuth round-trip.
  useEffect(() => {
    const result = params.get("youtube");
    if (!result || handled.current) return;
    handled.current = true;
    const msg = callbackMessages[result] ?? callbackMessages.error;
    if (msg.ok) toast.success(msg.text);
    else toast.error(msg.text);
    refresh();
    router.replace(pathname, { scroll: false });
  }, [params, pathname, refresh, router]);

  if (!user) return null;

  return (
    <div className="mx-auto max-w-2xl space-y-6 py-6">
      <h1 className="text-2xl font-bold tracking-tight">Settings</h1>

      <section className="space-y-3 rounded-xl border bg-card p-5">
        <h2 className="font-semibold">Account</h2>
        <dl className="space-y-2 text-sm">
          <Row label="Name">{user.display_name}</Row>
          <Row label="Email">{user.email}</Row>
          <Row label="Role">
            <Badge variant="secondary" className="capitalize">
              {user.role}
            </Badge>
          </Row>
        </dl>
      </section>

      {user.role === "creator" ? (
        <>
          <YouTubeCard user={user} onChange={refresh} />
          <PayoutAccountCard />
        </>
      ) : (
        <section className="rounded-xl border border-dashed bg-card p-5 text-sm text-muted-foreground">
          YouTube linking is only needed for creator accounts.
        </section>
      )}
    </div>
  );
}

function YouTubeCard({ user, onChange }: { user: User; onChange: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const connected = !!user.youtube_channel_id;

  async function connect() {
    setBusy(true);
    try {
      const { auth_url } = await api<{ auth_url: string }>("/api/youtube/connect");
      window.location.href = auth_url; // leaves the app; busy state stays on until the page unloads
    } catch (err) {
      toast.error((err as Error).message);
      setBusy(false);
    }
  }

  async function disconnect() {
    setBusy(true);
    try {
      await api<User>("/api/youtube/disconnect", { method: "POST" });
      await onChange();
      toast.success("YouTube channel disconnected");
    } catch (err) {
      toast.error(`Could not disconnect: ${(err as Error).message}`);
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  }

  return (
    <section className="space-y-4 rounded-xl border bg-card p-5">
      <div className="flex items-center gap-2">
        <PlatformIcon platform="youtube" />
        <h2 className="font-semibold">YouTube channel</h2>
        {connected && (
          <Badge variant="success" className="ml-auto">
            <CheckCircle2 /> Connected
          </Badge>
        )}
      </div>

      {connected ? (
        <>
          <div className="flex items-center justify-between gap-3 rounded-lg bg-muted/50 p-3">
            <div className="min-w-0">
              <p className="truncate font-medium">{user.youtube_channel_title}</p>
              <p className="truncate font-mono text-xs text-muted-foreground">{user.youtube_channel_id}</p>
            </div>
            <Button asChild variant="ghost" size="sm">
              <a href={`https://www.youtube.com/channel/${user.youtube_channel_id}`} target="_blank" rel="noreferrer">
                View <ExternalLink />
              </a>
            </Button>
          </div>
          <p className="text-sm text-muted-foreground">
            Only videos from this channel pass the system check when you submit them to a campaign.
          </p>
          {confirming ? (
            <div className="flex flex-wrap items-center gap-2 rounded-lg border border-destructive/40 p-3 text-sm">
              <span className="mr-auto">Disconnect? Pending submissions from this channel will fail the ownership check.</span>
              <Button variant="ghost" size="sm" onClick={() => setConfirming(false)} disabled={busy}>
                Cancel
              </Button>
              <Button variant="destructive" size="sm" onClick={disconnect} disabled={busy}>
                {busy && <Loader2 className="animate-spin" />} Disconnect
              </Button>
            </div>
          ) : (
            <Button variant="outline" onClick={() => setConfirming(true)}>
              <Unlink /> Disconnect channel
            </Button>
          )}
        </>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">
            Connect the channel you post on. We use it to confirm the videos you submit are really yours — required
            before a submission can pass the system check.
          </p>
          <ul className="space-y-1.5 text-sm text-muted-foreground">
            <li className="flex items-start gap-2">
              <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary" /> Read-only access — AdCup can&apos;t upload,
              edit or delete anything
            </li>
            <li className="flex items-start gap-2">
              <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary" /> You can disconnect at any time
            </li>
          </ul>
          <Button onClick={connect} disabled={busy}>
            {busy ? <Loader2 className="animate-spin" /> : <PlatformIcon platform="youtube" />}
            Connect YouTube
          </Button>
        </>
      )}
    </section>
  );
}

// Linked account detection: where payouts go. Required before the first submission; the backend
// only ever returns a masked number.
function PayoutAccountCard() {
  const [data, setData] = useState<PayoutMethodResponse | null>(null);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [method, setMethod] = useState<PayoutMethod>("promptpay");
  const [promptpayId, setPromptpayId] = useState("");
  const [bankCode, setBankCode] = useState("");
  const [accountNumber, setAccountNumber] = useState("");
  const [accountName, setAccountName] = useState("");

  useEffect(() => {
    api<PayoutMethodResponse>("/api/payout-method")
      .then((res) => {
        setData(res);
        setEditing(!res.account);
      })
      .catch((err) => toast.error(`Could not load payout account: ${(err as Error).message}`));
  }, []);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const body =
        method === "promptpay"
          ? { method, promptpay_id: promptpayId, account_name: accountName }
          : { method, bank_code: bankCode, account_number: accountNumber, account_name: accountName };
      const res = await api<PayoutMethodResponse>("/api/payout-method", { method: "PUT", body });
      setData(res);
      setEditing(false);
      setPromptpayId("");
      setAccountNumber("");
      toast.success("Payout account saved");
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const account = data?.account;
  const bankName = (code: string | null) => data?.banks.find((b) => b.code === code)?.name ?? code;

  return (
    <section className="space-y-4 rounded-xl border bg-card p-5">
      <div className="flex items-center gap-2">
        <Landmark className="size-5 text-primary" />
        <h2 className="font-semibold">Payout account</h2>
        {account && (
          <Badge variant="success" className="ml-auto">
            <CheckCircle2 /> Set up
          </Badge>
        )}
      </div>

      {!data ? (
        <Loader2 className="size-5 animate-spin text-muted-foreground" />
      ) : account && !editing ? (
        <>
          <div className="flex items-center justify-between gap-3 rounded-lg bg-muted/50 p-3">
            <div className="min-w-0">
              <p className="truncate font-medium">{account.account_name}</p>
              <p className="truncate text-sm text-muted-foreground">
                {account.method === "promptpay" ? "PromptPay" : bankName(account.bank_code)} · {account.account_masked}
              </p>
            </div>
            <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
              Change
            </Button>
          </div>
          <p className="text-sm text-muted-foreground">Your earnings are paid to this account when you cash out.</p>
        </>
      ) : (
        <form onSubmit={save} className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Required before your first submission. Earnings are paid to this account when you cash out.
          </p>
          <div role="radiogroup" aria-label="Payout method" className="grid grid-cols-2 gap-2">
            {(["promptpay", "bank"] as const).map((m) => (
              <Button
                key={m}
                type="button"
                role="radio"
                aria-checked={method === m}
                variant={method === m ? "default" : "outline"}
                onClick={() => setMethod(m)}
              >
                {m === "promptpay" ? "PromptPay" : "Bank account"}
              </Button>
            ))}
          </div>
          {method === "promptpay" ? (
            <Field label="PromptPay ID" htmlFor="promptpay-id">
              <Input
                id="promptpay-id"
                inputMode="numeric"
                placeholder="Phone number or 13-digit ID number"
                value={promptpayId}
                onChange={(e) => setPromptpayId(e.target.value)}
                required
              />
            </Field>
          ) : (
            <>
              <Field label="Bank">
                <Select value={bankCode} onValueChange={setBankCode}>
                  <SelectTrigger className="w-full" aria-label="Bank">
                    <SelectValue placeholder="Choose a bank" />
                  </SelectTrigger>
                  <SelectContent>
                    {data.banks.map((b) => (
                      <SelectItem key={b.code} value={b.code}>
                        {b.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
              <Field label="Account number" htmlFor="account-number">
                <Input
                  id="account-number"
                  inputMode="numeric"
                  placeholder="10–12 digits"
                  value={accountNumber}
                  onChange={(e) => setAccountNumber(e.target.value)}
                  required
                />
              </Field>
            </>
          )}
          <Field label="Account name" htmlFor="account-name">
            <Input
              id="account-name"
              placeholder="Name on the account"
              value={accountName}
              onChange={(e) => setAccountName(e.target.value)}
              required
              minLength={2}
            />
          </Field>
          <div className="flex justify-end gap-2">
            {account && (
              <Button type="button" variant="ghost" onClick={() => setEditing(false)} disabled={busy}>
                Cancel
              </Button>
            )}
            <Button type="submit" disabled={busy || (method === "bank" && !bankCode)}>
              {busy && <Loader2 className="animate-spin" />} Save payout account
            </Button>
          </div>
        </form>
      )}
    </section>
  );
}

function Field({ label, htmlFor, children }: { label: string; htmlFor?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="text-sm font-medium">
        {label}
      </label>
      {children}
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="truncate font-medium">{children}</dd>
    </div>
  );
}
