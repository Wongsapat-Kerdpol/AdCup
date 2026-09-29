"use client";

// [PERSON 1] Sign-up: pick Creator or Brand (?role= pre-selects), then name / email / password.
// POST /api/auth/register -> useAuth().login(res). Rules mirror RegisterRequest in backend/app/schemas/user.py.

import { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Building2, Eye, EyeOff, Loader2, Video } from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/components/providers/auth-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import { routes } from "@/lib/routes";
import type { TokenResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

type SignupRole = "creator" | "brand";
type Field = "display_name" | "email" | "password" | "confirm";

const roleOptions: { value: SignupRole; label: string; hint: string; icon: typeof Video }[] = [
  { value: "creator", label: "Creator", hint: "Post videos, earn per view", icon: Video },
  { value: "brand", label: "Brand", hint: "Launch campaigns, pay for views", icon: Building2 },
];

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function validate(v: Record<Field, string>): Partial<Record<Field, string>> {
  const errors: Partial<Record<Field, string>> = {};
  const name = v.display_name.trim();
  if (name.length < 2) errors.display_name = "At least 2 characters";
  else if (name.length > 100) errors.display_name = "At most 100 characters";
  if (!EMAIL_RE.test(v.email.trim())) errors.email = "Enter a valid email address";
  if (v.password.length < 8) errors.password = "At least 8 characters";
  else if (new TextEncoder().encode(v.password).length > 72) errors.password = "Password is too long";
  if (v.confirm !== v.password) errors.confirm = "Passwords don't match";
  return errors;
}

export function RegisterForm() {
  const { login } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next");
  const [role, setRole] = useState<SignupRole>(params.get("role") === "brand" ? "brand" : "creator");
  const [values, setValues] = useState<Record<Field, string>>({ display_name: "", email: "", password: "", confirm: "" });
  const [errors, setErrors] = useState<Partial<Record<Field, string>>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);

  function set(field: Field) {
    return (e: React.ChangeEvent<HTMLInputElement>) => {
      setValues((v) => ({ ...v, [field]: e.target.value }));
      if (errors[field]) setErrors((er) => ({ ...er, [field]: undefined }));
    };
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const found = validate(values);
    setErrors(found);
    setFormError(null);
    if (Object.keys(found).length) return;

    setBusy(true);
    try {
      const res = await api<TokenResponse>("/api/auth/register", {
        method: "POST",
        body: { display_name: values.display_name.trim(), email: values.email.trim(), password: values.password, role },
      });
      login(res);
      toast.success(`Welcome to AdCup, ${res.user.display_name}!`);
      const fallback = role === "brand" ? routes.brandCampaigns : routes.discover;
      router.push(next && next.startsWith("/") && !next.startsWith("//") ? next : fallback);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) setErrors({ email: err.message });
      else if (err instanceof ApiError && err.status === 422) setFormError("Please check the form and try again");
      else setFormError((err as Error).message);
      setBusy(false);
    }
  }

  const loginHref = next ? `${routes.login}?next=${encodeURIComponent(next)}` : routes.login;

  return (
    <div className="rounded-xl border bg-card p-6 shadow-sm">
      <div className="mb-6 space-y-1 text-center">
        <h1 className="text-2xl font-bold tracking-tight">Create an account</h1>
        <p className="text-sm text-muted-foreground">Join AdCup as a creator or a brand</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <div role="radiogroup" aria-label="Account type" className="grid grid-cols-2 gap-2">
          {roleOptions.map(({ value, label, hint, icon: Icon }) => (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={role === value}
              onClick={() => setRole(value)}
              className={cn(
                "flex flex-col items-start gap-1 rounded-lg border p-3 text-left transition-colors hover:bg-accent",
                role === value && "border-primary bg-primary/10 hover:bg-primary/10",
              )}
            >
              <Icon className={cn("size-5", role === value ? "text-primary" : "text-muted-foreground")} />
              <span className="text-sm font-medium">{label}</span>
              <span className="text-xs text-muted-foreground">{hint}</span>
            </button>
          ))}
        </div>

        <FormField id="display_name" label={role === "brand" ? "Brand name" : "Display name"} error={errors.display_name}>
          <Input
            id="display_name"
            autoComplete={role === "brand" ? "organization" : "nickname"}
            placeholder={role === "brand" ? "Siam Coffee Co." : "Mint Creates"}
            value={values.display_name}
            onChange={set("display_name")}
            aria-invalid={!!errors.display_name}
            maxLength={100}
          />
        </FormField>

        <FormField id="email" label="Email" error={errors.email}>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            value={values.email}
            onChange={set("email")}
            aria-invalid={!!errors.email}
          />
        </FormField>

        <FormField id="password" label="Password" error={errors.password}>
          <div className="relative">
            <Input
              id="password"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              placeholder="At least 8 characters"
              value={values.password}
              onChange={set("password")}
              aria-invalid={!!errors.password}
              className="pr-10"
            />
            <button
              type="button"
              onClick={() => setShowPassword((s) => !s)}
              className="absolute inset-y-0 right-0 flex items-center px-3 text-muted-foreground hover:text-foreground"
              aria-label={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
        </FormField>

        <FormField id="confirm" label="Confirm password" error={errors.confirm}>
          <Input
            id="confirm"
            type={showPassword ? "text" : "password"}
            autoComplete="new-password"
            placeholder="Repeat your password"
            value={values.confirm}
            onChange={set("confirm")}
            aria-invalid={!!errors.confirm}
          />
        </FormField>

        {formError && <p className="text-sm text-destructive">{formError}</p>}

        <Button type="submit" className="w-full" disabled={busy}>
          {busy && <Loader2 className="animate-spin" />}
          Create {role} account
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link href={loginHref} className="font-medium text-primary hover:underline">
          Sign in
        </Link>
      </p>
    </div>
  );
}

function FormField({
  id,
  label,
  error,
  children,
}: {
  id: string;
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      {children}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}
