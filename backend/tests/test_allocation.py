"""Pure-function tests for the fair-share algorithms (no database needed)."""

import random

from app.services.allocation import (
    first_step_reaching,
    max_min_fair_share,
    max_min_fair_share_iterative,
    proportional_share,
)


def test_worked_example_from_the_docs():
    # pool 100, earned A=40 B=25 C=30 D=20 E=15 -> E and D paid in full, A/B/C share the other 65
    result = max_min_fair_share([40, 25, 30, 20, 15], 100)
    assert result[3] == 20 and result[4] == 15
    assert sum(result) == 100
    assert max(result[:3]) - min(result[:3]) <= 1


def test_pool_that_covers_everyone_pays_in_full():
    assert max_min_fair_share([5, 0, 12], 100) == [5, 0, 12]


def test_empty_and_zero_pool():
    assert max_min_fair_share([], 10) == []
    assert max_min_fair_share([5, 5], 0) == [0, 0]


def test_leftover_satang_go_to_the_lowest_positions():
    assert max_min_fair_share([9, 9, 9], 10) == [4, 3, 3]


def test_matches_the_reference_implementation_and_keeps_its_guarantees():
    rng = random.Random(42)
    for _ in range(3000):
        n = rng.randint(0, 15)
        demands = [rng.choice([0, rng.randint(0, 40), rng.randint(0, 4)]) for _ in range(n)]
        pool = rng.randint(0, 150)

        fast = max_min_fair_share(demands, pool)

        assert fast == max_min_fair_share_iterative(demands, pool)
        assert sum(fast) == min(pool, sum(demands))
        assert all(0 <= got <= asked for got, asked in zip(fast, demands))
        cut = [got for got, asked in zip(fast, demands) if got < asked]
        assert max(cut, default=0) - min(cut, default=0) <= 1  # everyone who is cut ends up equal


def test_proportional_cuts_everyone_by_the_same_percentage():
    result = proportional_share([40, 25, 30, 20, 15], 100)
    assert result == [30, 19, 23, 15, 11]  # 76.9% each (floored), vs. max-min's 22/22/21/20/15


def test_first_step_reaching_binary_searches_a_growing_function():
    assert first_step_reaching(10, lambda t: t * 2, 0, 30) == 5
    assert first_step_reaching(0, lambda t: t, 0, 30) == 0
    assert first_step_reaching(1000, lambda t: t, 0, 30) is None
