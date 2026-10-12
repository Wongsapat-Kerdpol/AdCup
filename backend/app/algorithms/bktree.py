"""BK-Tree (Burkhard & Keller, 1973) over 64-bit fingerprints with Hamming distance.

Every node stores one fingerprint and keeps its children in "drawers" labelled by their distance
to it. To find everything within `radius` of X: compare X with the node (distance d) and only open
the drawers d - radius ... d + radius. Any other drawer can be skipped safely (triangle
inequality): if X is d away from the node and a child is k away from it, X and that child are at
least |d - k| apart.

Delete is "lazy": a node is only flagged as deleted, because removing it would orphan its whole
subtree (every child's position depends on its distance to this node).
"""

from collections.abc import Callable, Hashable
from dataclasses import dataclass, field

from app.algorithms.dhash import hamming


@dataclass
class _Node:
    value: int
    owners: list[Hashable] = field(default_factory=list)  # e.g. submission ids sharing this fingerprint
    children: dict[int, "_Node"] = field(default_factory=dict)  # distance -> child
    deleted: bool = False


class BKTree:
    def __init__(self, distance: Callable[[int, int], int] = hamming):
        self._distance = distance
        self.root: _Node | None = None
        self.size = 0  # nodes in the tree (including lazily deleted ones)
        self.comparisons = 0  # distance calls made by search() — to compare with a linear scan

    # INSERT
    def insert(self, value: int, owner: Hashable) -> None:
        if self.root is None:
            self.root = _Node(value, [owner])
            self.size = 1
            return
        node = self.root
        while True:
            d = self._distance(value, node.value)
            if d == 0:  # same fingerprint already stored: just add the owner
                if owner not in node.owners:
                    node.owners.append(owner)
                node.deleted = False
                return
            child = node.children.get(d)
            if child is None:
                node.children[d] = _Node(value, [owner])
                self.size += 1
                return
            node = child

    # SEARCH
    def search(self, value: int, radius: int) -> list[tuple[Hashable, int]]:
        """Every (owner, distance) whose fingerprint is within `radius` of `value`."""
        results: list[tuple[Hashable, int]] = []
        stack = [self.root] if self.root else []
        while stack:
            node = stack.pop()
            d = self._distance(value, node.value)
            self.comparisons += 1
            if d <= radius and not node.deleted:
                results.extend((owner, d) for owner in node.owners)
            low, high = d - radius, d + radius
            for dist, child in node.children.items():
                if low <= dist <= high:  # every other drawer cannot contain an answer
                    stack.append(child)
        return results

    # DELETE (lazy)
    def delete_owner(self, owner: Hashable) -> int:
        """Remove `owner` everywhere; nodes left without owners are flagged deleted. Returns how many
        fingerprints were removed."""
        removed = 0
        stack = [self.root] if self.root else []
        while stack:
            node = stack.pop()
            if owner in node.owners:
                node.owners.remove(owner)
                removed += 1
                if not node.owners:
                    node.deleted = True
            stack.extend(node.children.values())
        return removed
