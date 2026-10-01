"""Fair sharing of a limited reward pool — pure functions (no DB, no framework).

Why this exists
---------------
A campaign has a fixed pool. Every approved video has *earned* some amount ("demand"). When the
pool covers every demand, everybody is simply paid in full. When it does not, someone has to be
cut — the question is who.

We use **max-min fairness** ("water-filling"): nobody receives more than they earned, small
earners are paid in full first, and whatever is left is split equally among the rest.

    pool 100, earned A=40 B=25 C=30 D=20 E=15 (total 130)
    -> E=15, D=20 (paid in full), A=B=C=21.67 (equal share of the remaining 65)

Finding the "water level" quickly
---------------------------------
Sort the demands, build prefix sums, then binary-search the level: O(n log n) to build, then O(log n)
per question once built. The textbook "redistribute until stable" loop
(`max_min_fair_share_iterative`, kept as the reference implementation the tests compare against)
costs O(n * passes) per question; passes <= n but is only a handful on realistic data, so for a
single split the loop is just as fast (often faster). The sorted version wins when many questions
are asked about the same demands, or demands are inserted/removed between questions.

All amounts are integers (satang = 1/100 THB) so the split is exact and always sums to the pool.
"""

from collections.abc import Callable, Sequence
from typing import TypeVar

T = TypeVar("T", int, float)


def max_min_fair_share(demands: Sequence[int], pool: int) -> list[int]:
    """Split `pool` over `demands` (max-min fair). Result is in the same order as `demands`.

    Guarantees: 0 <= result[i] <= demands[i]; sum(result) == min(pool, sum(demands)); a person who
    asked for less never gets less than someone who asked for more. Leftover satang (when the
    equal share doesn't divide evenly) go to the lowest input positions, so ties are deterministic.
    """
    n = len(demands)
    pool = max(pool, 0)
    demands = [max(d, 0) for d in demands]
    if sum(demands) <= pool:
        return list(demands)

    order = sorted(range(n), key=demands.__getitem__)  # indices, smallest demand first
    d = [demands[i] for i in order]
    prefix = [0] * (n + 1)  # prefix[k] = sum of the k smallest demands
    for i, value in enumerate(d):
        prefix[i + 1] = prefix[i] + value

    # f(k) = what is spent if the k smallest are paid in full and everyone else is capped at d[k].
    # f is non-decreasing in k (f(k+1) - f(k) = (n-k-1) * (d[k+1] - d[k]) >= 0), so the first k
    # with f(k) >= pool can be found by binary search. f(n-1) = total demand > pool, so it exists.
    lo, hi = 0, n - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if prefix[mid] + (n - mid) * d[mid] >= pool:
            hi = mid
        else:
            lo = mid + 1
    k = lo

    # The k smallest are paid in full; the other m share what is left, equally.
    tail = order[k:]
    base, extra = divmod(pool - prefix[k], len(tail))
    result = [0] * n
    for i in order[:k]:
        result[i] = demands[i]
    for rank, i in enumerate(sorted(tail)):  # lowest input position gets the spare satang
        result[i] = base + (1 if rank < extra else 0)
    return result


def max_min_fair_share_iterative(demands: Sequence[int], pool: int) -> list[int]:
    """Reference implementation: hand out an equal share, pay off whoever asked for less,
    redistribute the leftover, repeat. O(n * passes), passes <= n (a handful in practice).
    Same result as `max_min_fair_share`."""
    n = len(demands)
    alloc = [0] * n
    active = [i for i in range(n) if demands[i] > 0]
    remaining = max(pool, 0)
    while active and remaining > 0:
        share, extra = divmod(remaining, len(active))
        satisfied = [i for i in active if demands[i] - alloc[i] <= share]
        if not satisfied:
            for rank, i in enumerate(active):
                alloc[i] += share + (1 if rank < extra else 0)
            break
        for i in satisfied:
            remaining -= demands[i] - alloc[i]
            alloc[i] = demands[i]
        done = set(satisfied)
        active = [i for i in active if i not in done]
    return alloc


def proportional_share(demands: Sequence[int], pool: int) -> list[int]:
    """The simple alternative: everyone is cut by the same percentage (floors; a few satang may
    stay unspent). Used only to compare fairness in the report."""
    total = sum(demands)
    if total <= pool:
        return list(demands)
    return [d * max(pool, 0) // total for d in demands]


def first_step_reaching(target: T, value_at: Callable[[int], T], lo: int, hi: int) -> int | None:
    """Smallest step t in [lo, hi] with value_at(t) >= target, or None if even value_at(hi) is
    below it. `value_at` must be non-decreasing (binary search on the answer), e.g. "money claimed
    by day t", which only ever grows. O(log(hi - lo)) calls instead of scanning every day."""
    if value_at(hi) < target:
        return None
    while lo < hi:
        mid = (lo + hi) // 2
        if value_at(mid) >= target:
            hi = mid
        else:
            lo = mid + 1
    return lo
