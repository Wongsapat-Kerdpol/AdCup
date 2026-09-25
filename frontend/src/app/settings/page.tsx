import { RequireAuth } from "@/components/auth/require-auth";
import { ComingSoon } from "@/components/layout/coming-soon";

// TODO(Person 3)
export default function SettingsPage() {
  return (
    <RequireAuth>
      <ComingSoon
        owner="Person 3 — YouTube OAuth"
        title="Settings"
        todo={["Connect YouTube (Google OAuth) -> shows linked channel", "Disconnect channel"]}
      />
    </RequireAuth>
  );
}
