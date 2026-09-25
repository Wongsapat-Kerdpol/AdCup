// Placeholder for pages another team member will build. Delete it from your page when you start.

import { Construction } from "lucide-react";

import { Badge } from "@/components/ui/badge";

export function ComingSoon({ title, owner, todo }: { title: string; owner: string; todo: string[] }) {
  return (
    <div className="mx-auto max-w-2xl space-y-4 py-10">
      <Badge variant="warning">{owner}</Badge>
      <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
      <div className="rounded-xl border border-dashed bg-card p-5">
        <div className="mb-3 flex items-center gap-2 text-sm font-medium">
          <Construction className="size-4 text-primary" /> Not built yet — TODO
        </div>
        <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
          {todo.map((t) => (
            <li key={t}>{t}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
