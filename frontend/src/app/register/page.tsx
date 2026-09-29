import type { Metadata } from "next";
import { Suspense } from "react";

import { RegisterForm } from "@/app/register/register-form";

export const metadata: Metadata = { title: "Create an account" };

// [PERSON 1]
export default function RegisterPage() {
  return (
    <div className="mx-auto max-w-md py-10">
      <Suspense>
        <RegisterForm />
      </Suspense>
    </div>
  );
}
