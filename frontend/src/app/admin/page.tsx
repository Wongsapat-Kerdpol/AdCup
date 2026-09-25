import type { Metadata } from "next";

import { AdminDashboard } from "@/components/admin/admin-dashboard";
import { RequireAuth } from "@/components/auth/require-auth";

export const metadata: Metadata = { title: "Analytics" };

// [PERSON 3] Admin analytics dashboard.
export default function AdminPage() {
  return (
    <RequireAuth roles={["admin"]}>
      <AdminDashboard />
    </RequireAuth>
  );
}
