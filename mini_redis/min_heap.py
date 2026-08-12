"""Array-backed minimum heap with explicit heapify operations."""

from typing import Any


class MinHeap:
    """A minimum heap for values that implement the less-than operator."""

    __slots__ = ("_items",)

    def __init__(self) -> None:
        self._items = []

    def size(self) -> int:
        return len(self._items)

    def peek(self) -> Any:
        if not self._items:
            return None
        return self._items[0]

    def push(self, item: Any) -> None:
        self._items.append(item)
        self._heapify_up(len(self._items) - 1)

    def pop(self) -> Any:
        if not self._items:
            return None
        if len(self._items) == 1:
            return self._items.pop()

        root = self._items[0]
        self._items[0] = self._items.pop()
        self._heapify_down(0)
        return root

    def _heapify_up(self, index: int) -> None:
        while index > 0:
            parent = (index - 1) // 2
            if not self._items[index] < self._items[parent]:
                break
            self._items[index], self._items[parent] = (
                self._items[parent],
                self._items[index],
            )
            index = parent

    def _heapify_down(self, index: int) -> None:
        length = len(self._items)
        while True:
            smallest = index
            left = index * 2 + 1
            right = left + 1

            if left < length and self._items[left] < self._items[smallest]:
                smallest = left
            if right < length and self._items[right] < self._items[smallest]:
                smallest = right
            if smallest == index:
                return

            self._items[index], self._items[smallest] = (
                self._items[smallest],
                self._items[index],
            )
            index = smallest
