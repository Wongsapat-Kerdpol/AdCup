import type { Metadata } from "next";
import { Suspense } from "react";

import { DevLogin } from "@/app/login/dev-login";
import { LoginForm } from "@/app/login/login-form";

export const metadata: Metadata = { title: "Sign in" };

// [PERSON 1] Keep <DevLogin /> below the form while developing; remove it before the final demo.
export default function LoginPage() {
  return (
    <div className="mx-auto max-w-md space-y-6 py-10">
      <Suspense>
        <LoginForm />
        <DevLogin />
      </Suspense>
    </div>
  );
}
