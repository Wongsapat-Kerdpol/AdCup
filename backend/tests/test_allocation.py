"""Pure-function tests for the proportional split and the binary search on the answer (no database needed)."""

import random

from app.services.allocation import first_step_reaching, proportional_share


def test_worked_example_from_the_docs():
    # pool 100, earned 10 / 40 / 100 (in satang: x100) -> everybody gets 66.67%
    assert proportional_share([1000, 4000, 10000], 10000) == [667, 2667, 6666]


def test_exact_shares_when_the_percentage_is_round():
    # earned 0.50 / 2.00 / 5.00 from a pool of 3.00 -> everybody gets exactly 40%
    assert proportional_share([50, 200, 500], 300) == [20, 80, 200]


def test_pool_that_covers_everyone_pays_in_full():
    assert proportional_share([5, 0, 12], 100) == [5, 0, 12]


def test_empty_and_zero_pool():
    assert proportional_share([], 10) == []
    assert proportional_share([5, 5], 0) == [0, 0]


def test_leftover_satang_go_to_the_largest_remainders_then_the_lowest_positions():
    assert proportional_share([9, 9, 9], 10) == [4, 3, 3]
    assert proportional_share([1, 100], 77) == [1, 76]  # 0.76 vs 76.24 -> the small one has the larger remainder


def test_zero_demand_never_receives_anything():
    result = proportional_share([0, 30, 0, 70], 50)
    assert result[0] == 0 and result[2] == 0 and sum(result) == 50


def test_random_cases_keep_every_guarantee():
    rng = random.Random(42)
    for _ in range(5000):
        n = rng.randint(0, 20)
        demands = [rng.choice([0, rng.randint(0, 5000), rng.randint(0, 5)]) for _ in range(n)]
        pool = rng.randint(0, 40_000)
        total = sum(demands)

        shares = proportional_share(demands, pool)

        assert len(shares) == n
        assert sum(shares) == min(pool, total)  # the pool is spent exactly
        assert all(0 <= got <= asked for got, asked in zip(shares, demands))
        if total > pool:  # everybody gets the same percentage, to within 1 satang
            assert all(abs(got * total - asked * pool) < total for got, asked in zip(shares, demands))


def test_first_step_reaching_binary_searches_a_growing_function():
    assert first_step_reaching(10, lambda t: t * 2, 0, 30) == 5
    assert first_step_reaching(0, lambda t: t, 0, 30) == 0
    assert first_step_reaching(1000, lambda t: t, 0, 30) is None
