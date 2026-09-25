import Link from "next/link";
import { Trophy } from "lucide-react";

import { routes } from "@/lib/routes";

export function Logo() {
  return (
    <Link href={routes.discover} className="flex items-center gap-2 font-bold tracking-tight">
      <span className="flex size-7 items-center justify-center rounded-md bg-primary">
        <Trophy className="size-4 text-primary-foreground" />
      </span>
      <span className="text-sm uppercase">AdCup</span>
    </Link>
  );
}
