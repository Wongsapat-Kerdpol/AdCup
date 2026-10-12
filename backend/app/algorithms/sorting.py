"""Merge sort — stable, O(n log n). Used to rank possible copies from most to least similar."""

from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")


def merge_sort(items: list[T], key: Callable[[T], Any], descending: bool = False) -> list[T]:
    if len(items) <= 1:
        return list(items)
    mid = len(items) // 2
    left = merge_sort(items[:mid], key, descending)
    right = merge_sort(items[mid:], key, descending)

    out: list[T] = []
    i = j = 0
    while i < len(left) and j < len(right):
        a, b = key(left[i]), key(right[j])
        take_left = a >= b if descending else a <= b  # ">=" / "<=" keeps equal items in order (stable)
        if take_left:
            out.append(left[i])
            i += 1
        else:
            out.append(right[j])
            j += 1
    return out + left[i:] + right[j:]
