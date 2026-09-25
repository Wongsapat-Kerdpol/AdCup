import type { Metadata } from "next";
import { Suspense } from "react";

import { DevLogin } from "@/app/login/dev-login";
import { ComingSoon } from "@/components/layout/coming-soon";

export const metadata: Metadata = { title: "Sign in" };

// TODO(Person 1): replace ComingSoon with the real email/password form
// (POST /api/auth/login -> useAuth().login(res) -> router.push(next ?? "/discover")).
// Keep <DevLogin /> below it while developing; remove it before the final demo.
export default function LoginPage() {
  return (
    <div className="mx-auto max-w-md">
      <ComingSoon
        owner="Person 1 — Auth"
        title="Sign in"
        todo={["Email + password form with validation", "Link to /register", "Redirect to ?next= after login"]}
      />
      <Suspense>
        <DevLogin />
      </Suspense>
    </div>
  );
}
