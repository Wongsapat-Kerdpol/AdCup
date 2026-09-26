import { RequireAuth } from "@/components/auth/require-auth";
import { ReviewQueue } from "@/components/admin/review-queue";

export default function AdminReviewPage() {
  return (
    <RequireAuth roles={["admin"]}>
      <ReviewQueue />
    </RequireAuth>
  );
}
