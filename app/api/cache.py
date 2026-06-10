"""LRU cache for query results, keyed by canonical query hash + snapshot
version (pattern: router's route cache).

Cache invalidates implicitly when the snapshot version moves: the key
includes it. Eviction is plain LRU over a bounded dict.
"""

from __future__ import annotations

from collections import OrderedDict


class LRU[T]:
    def __init__(self, max_size: int = 2000) -> None:
        self._items: OrderedDict[str, T] = OrderedDict()
        self._max = max_size

    def get(self, key: str) -> T | None:
        if key not in self._items:
            return None
        self._items.move_to_end(key)
        return self._items[key]

    def put(self, key: str, value: T) -> None:
        if key in self._items:
            self._items.move_to_end(key)
        self._items[key] = value
        while len(self._items) > self._max:
            self._items.popitem(last=False)

    def clear(self) -> None:
        self._items.clear()

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, key: str) -> bool:
        return key in self._items
