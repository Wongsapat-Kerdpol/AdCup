import type { Metadata } from "next";
import { Suspense } from "react";

import { RequireAuth } from "@/components/auth/require-auth";
import { SettingsView } from "@/components/settings/settings-view";

export const metadata: Metadata = { title: "Settings" };

// [PERSON 3] Account settings + YouTube channel linking (Google OAuth).
export default function SettingsPage() {
  return (
    <RequireAuth>
      <Suspense>
        <SettingsView />
      </Suspense>
    </RequireAuth>
  );
}
