"use client";

// [MAIN] Discover / Gallery: category + platform filters, search, sort, grid, load more.
// Filter state lives in the URL (?category=music&platform=tiktok&q=...&sort=...) so it is shareable.

import { useCallback, useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Search, SearchX } from "lucide-react";
import { toast } from "sonner";

import { CampaignCard } from "@/components/campaign/campaign-card";
import { PlatformIcon, platformLabels } from "@/components/campaign/platform-icon";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import type { Campaign, CampaignCategory, CampaignSort, Paginated, Platform } from "@/lib/types";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 24;

const categories: { value: CampaignCategory | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "logo", label: "Logo" },
  { value: "music", label: "Music" },
  { value: "clipping", label: "Clipping" },
  { value: "ugc", label: "UGC" },
];

const platforms: Platform[] = ["youtube", "tiktok"];

const sortOptions: { value: CampaignSort; label: string }[] = [
  { value: "newest", label: "Newest" },
  { value: "highest_rate", label: "Highest rate" },
  { value: "highest_budget", label: "Biggest budget" },
  { value: "most_available", label: "Most budget left" },
  { value: "ending_soon", label: "Ending soon" },
];

function useDebounced<T>(value: T, ms = 300) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

export function DiscoverView() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const category = (params.get("category") as CampaignCategory | null) ?? "all";
  const platform = params.get("platform") as Platform | null;
  const sort = (params.get("sort") as CampaignSort | null) ?? "newest";

  const [searchInput, setSearchInput] = useState(params.get("q") ?? "");
  const search = useDebounced(searchInput.trim());

  const [items, setItems] = useState<Campaign[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);

  const setParam = useCallback(
    (key: string, value: string | null) => {
      const next = new URLSearchParams(params.toString());
      if (value) next.set(key, value);
      else next.delete(key);
      router.replace(`${pathname}${next.size ? `?${next}` : ""}`, { scroll: false });
    },
    [params, pathname, router],
  );

  // Keep the search box in the URL.
  useEffect(() => {
    if ((params.get("q") ?? "") !== search) setParam("q", search || null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  const query = {
    category: category === "all" ? undefined : category,
    platform: platform ?? undefined,
    search: search || undefined,
    sort,
    page_size: PAGE_SIZE,
  };

  useEffect(() => {
    const ctrl = new AbortController();
    setLoading(true);
    api<Paginated<Campaign>>("/api/campaigns", { query: { ...query, page: 1 }, signal: ctrl.signal })
      .then((res) => {
        setItems(res.items);
        setTotal(res.total);
        setPage(1);
      })
      .catch((err) => {
        if (err.name !== "AbortError") toast.error(`Could not load campaigns: ${err.message}`);
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false);
      });
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [category, platform, search, sort]);

  async function loadMore() {
    setLoadingMore(true);
    try {
      const res = await api<Paginated<Campaign>>("/api/campaigns", { query: { ...query, page: page + 1 } });
      setItems((prev) => [...prev, ...res.items]);
      setPage(page + 1);
    } catch (err) {
      toast.error(`Could not load more: ${(err as Error).message}`);
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <div className="min-w-0 space-y-4">
      <div className="space-y-3 rounded-lg border bg-card p-3">
        <div className="flex flex-col gap-2 sm:flex-row">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search campaigns, brands…"
              className="h-10 rounded-full pl-10"
              aria-label="Search campaigns"
            />
          </div>
          <Select value={sort} onValueChange={(v) => setParam("sort", v === "newest" ? null : v)}>
            <SelectTrigger className="h-10 w-full rounded-full sm:w-48" aria-label="Sort by">
              <SelectValue />
            </SelectTrigger>
            <SelectContent align="end">
              {sortOptions.map((o) => (
                <SelectItem key={o.value} value={o.value}>
                  {o.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          {/* Category filter */}
          {categories.map((c) => (
            <FilterChip
              key={c.value}
              active={category === c.value}
              onClick={() => setParam("category", c.value === "all" ? null : c.value)}
            >
              {c.label}
            </FilterChip>
          ))}

          <span className="mx-1 h-5 w-px bg-border" aria-hidden />

          {/* Platform filter */}
          {platforms.map((p) => (
            <FilterChip
              key={p}
              active={platform === p}
              onClick={() => setParam("platform", platform === p ? null : p)}
              title={platformLabels[p]}
            >
              <PlatformIcon platform={p} /> {platformLabels[p]}
            </FilterChip>
          ))}
        </div>
      </div>

      <p className="text-sm text-muted-foreground">
        <span className="font-semibold text-foreground">{loading ? "…" : total}</span> campaigns available
        {!loading && items.length < total && <> · showing {items.length}</>}
      </p>

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-[300px] rounded-lg" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed bg-card py-16 text-center">
          <SearchX className="size-8 text-muted-foreground" />
          <p className="font-semibold">No campaigns found</p>
          <p className="text-sm text-muted-foreground">Try a different search or filter.</p>
        </div>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {items.map((c) => (
              <CampaignCard key={c.id} campaign={c} />
            ))}
          </div>
          {items.length < total && (
            <div className="flex justify-center">
              <Button variant="outline" onClick={loadMore} disabled={loadingMore}>
                {loadingMore ? "Loading…" : "Load more"}
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function FilterChip({ active, className, ...props }: React.ComponentProps<"button"> & { active: boolean }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      className={cn(
        "flex h-8 items-center justify-center gap-1.5 rounded-full border px-3.5 text-sm font-semibold whitespace-nowrap transition-colors",
        active
          ? "border-foreground bg-foreground text-background"
          : "border-input bg-card text-muted-foreground hover:border-foreground/40 hover:text-foreground",
        className,
      )}
      {...props}
    />
  );
}
