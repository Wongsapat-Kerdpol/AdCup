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
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
        {/* Platform filter */}
        <div className="flex w-fit items-center gap-1 rounded-lg border bg-card p-1">
          <FilterChip active={!platform} onClick={() => setParam("platform", null)}>
            All platforms
          </FilterChip>
          {platforms.map((p) => (
            <FilterChip
              key={p}
              active={platform === p}
              onClick={() => setParam("platform", platform === p ? null : p)}
              title={platformLabels[p]}
            >
              <PlatformIcon platform={p} />
            </FilterChip>
          ))}
        </div>

        {/* Category filter */}
        <div className="flex items-center gap-1 overflow-x-auto">
          {categories.map((c) => (
            <FilterChip
              key={c.value}
              variant="underline"
              active={category === c.value}
              onClick={() => setParam("category", c.value === "all" ? null : c.value)}
            >
              {c.label}
            </FilterChip>
          ))}
        </div>

        <div className="flex items-center gap-2 lg:ml-auto">
          <div className="relative flex-1 lg:w-64 lg:flex-none">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search for a campaign..."
              className="pl-9"
              aria-label="Search campaigns"
            />
          </div>
          <Select value={sort} onValueChange={(v) => setParam("sort", v === "newest" ? null : v)}>
            <SelectTrigger className="w-44" aria-label="Sort by">
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
      </div>

      <p className="text-xs text-muted-foreground">
        Showing <span className="font-semibold text-foreground">{loading ? "…" : items.length}</span> of{" "}
        <span className="font-semibold text-foreground">{loading ? "…" : total}</span> campaigns
      </p>

      {loading ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-[138px] rounded-xl" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed py-16 text-center">
          <SearchX className="size-8 text-muted-foreground" />
          <p className="font-medium">No campaigns found</p>
          <p className="text-sm text-muted-foreground">Try a different search or filter.</p>
        </div>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
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

function FilterChip({
  active,
  variant = "pill",
  className,
  ...props
}: React.ComponentProps<"button"> & { active: boolean; variant?: "pill" | "underline" }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      className={cn(
        "flex h-8 items-center justify-center rounded-md px-3 text-sm whitespace-nowrap transition-colors",
        variant === "pill" &&
          (active ? "border border-primary/60 bg-primary/15 text-foreground" : "text-muted-foreground hover:bg-accent"),
        variant === "underline" &&
          (active
            ? "rounded-none border-b-2 border-foreground text-foreground"
            : "text-muted-foreground hover:text-foreground"),
        className,
      )}
      {...props}
    />
  );
}
