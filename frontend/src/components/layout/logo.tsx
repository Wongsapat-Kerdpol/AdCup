import Link from "next/link";

import { routes } from "@/lib/routes";

export function Logo() {
  return (
    <Link href={routes.discover} className="flex items-baseline text-[26px] leading-none font-extrabold tracking-tight">
      adcup
      <span className="ml-0.5 inline-block size-2 rounded-full bg-brand" aria-hidden />
    </Link>
  );
}
