import { RequireAuth } from "@/components/auth/require-auth";
import { SubmissionsView } from "@/components/campaign/submissions-view";

export default function SubmissionsPage() {
  return (
    <RequireAuth roles={["creator"]}>
      <SubmissionsView />
    </RequireAuth>
  );
}
