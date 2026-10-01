"""Sharing a limited reward pool — pure functions (no DB, no framework).

When the pool covers everything the approved videos have earned ("demand"), everybody is simply
paid in full. When it does not, every video is paid the SAME PERCENTAGE of what it earned
("proportional share"):

    pool 100, earned A=10 B=40 C=100 (total 150) -> everybody gets 66.7%: A=6.67 B=26.67 C=66.67

Approval order and refresh timing don't matter.

All amounts are integers (satang = 1/100 THB) so the split is exact: every share is rounded down,
then the leftover satang go to the largest fractional remainders ("largest remainder method"), so the
shares always add up to exactly the pool.

`first_step_reaching` is a binary search on the answer, used by the campaign outlook.
"""

from collections.abc import Callable, Sequence
from typing import TypeVar

T = TypeVar("T", int, float)


def proportional_share(demands: Sequence[int], pool: int) -> list[int]:
    """Split `pool` over `demands` so everybody gets the same percentage. Same order as `demands`.

    Guarantees: 0 <= result[i] <= demands[i]; sum(result) == min(pool, sum(demands)); every share is
    within 1 satang of demands[i] * pool / total. Leftover satang go to the largest remainders
    (ties: lowest input position), so the result is deterministic. O(n log n) for the sort.
    """
    demands = [max(d, 0) for d in demands]
    pool = max(pool, 0)
    total = sum(demands)
    if total <= pool:
        return list(demands)

    shares = [d * pool // total for d in demands]
    leftover = pool - sum(shares)  # always < number of videos with a non-zero remainder
    by_remainder = sorted(range(len(demands)), key=lambda i: (-(demands[i] * pool % total), i))
    for i in by_remainder[:leftover]:
        shares[i] += 1
    return shares


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
