import Link from "next/link";

import { Button } from "@/components/ui/button";
import { routes } from "@/lib/routes";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center gap-3 py-24 text-center">
      <p className="text-5xl font-bold text-primary">404</p>
      <p className="text-muted-foreground">This page doesn&apos;t exist.</p>
      <Button asChild variant="outline">
        <Link href={routes.discover}>Back to Discover</Link>
      </Button>
    </div>
  );
}
