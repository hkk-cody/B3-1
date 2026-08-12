"""Sentinel-based doubly linked list used by the hash map and LRU."""

from typing import Any, Iterator, Optional


class Node:
    """A node whose position can be changed in constant time."""

    __slots__ = ("prev", "next", "data", "_owner")

    def __init__(self, data: Any = None) -> None:
        self.prev: Optional["Node"] = None
        self.next: Optional["Node"] = None
        self.data = data
        self._owner: Optional["DoublyLinkedList"] = None


class DoublyLinkedList:
    """A doubly linked list with hidden head and tail sentinels."""

    __slots__ = ("_head", "_tail", "_size")

    def __init__(self) -> None:
        self._head = Node()
        self._tail = Node()
        self._head.next = self._tail
        self._tail.prev = self._head
        self._size = 0

    @property
    def front_node(self) -> Optional[Node]:
        node = self._head.next
        if node is self._tail:
            return None
        return node

    @property
    def back_node(self) -> Optional[Node]:
        node = self._tail.prev
        if node is self._head:
            return None
        return node

    def size(self) -> int:
        return self._size

    def __len__(self) -> int:
        return self._size

    def insert_front(self, data: Any) -> Node:
        first = self._head.next
        if first is None:  # The sentinel invariant makes this unreachable.
            raise RuntimeError("corrupt linked list")
        return self._insert_between(data, self._head, first)

    def insert_back(self, data: Any) -> Node:
        last = self._tail.prev
        if last is None:  # The sentinel invariant makes this unreachable.
            raise RuntimeError("corrupt linked list")
        return self._insert_between(data, last, self._tail)

    def remove_front(self) -> Any:
        node = self.front_node
        if node is None:
            return None
        return self.remove_node(node)

    def remove_back(self) -> Any:
        node = self.back_node
        if node is None:
            return None
        return self.remove_node(node)

    def remove_node(self, node: Node) -> Any:
        """Remove a known node without searching for it."""

        self._validate_node(node)
        previous = node.prev
        following = node.next
        if previous is None or following is None:
            raise RuntimeError("corrupt linked list")
        previous.next = following
        following.prev = previous
        node.prev = None
        node.next = None
        node._owner = None
        self._size -= 1
        return node.data

    def move_to_front(self, node: Node) -> Node:
        """Move a known node to the front without changing the size."""

        self._validate_node(node)
        if node.prev is self._head:
            return node

        previous = node.prev
        following = node.next
        first = self._head.next
        if previous is None or following is None or first is None:
            raise RuntimeError("corrupt linked list")

        previous.next = following
        following.prev = previous
        node.prev = self._head
        node.next = first
        self._head.next = node
        first.prev = node
        return node

    def iter_nodes(self) -> Iterator[Node]:
        current = self._head.next
        while current is not None and current is not self._tail:
            following = current.next
            yield current
            current = following

    def __iter__(self) -> Iterator[Any]:
        for node in self.iter_nodes():
            yield node.data

    def _insert_between(self, data: Any, previous: Node, following: Node) -> Node:
        node = Node(data)
        node.prev = previous
        node.next = following
        node._owner = self
        previous.next = node
        following.prev = node
        self._size += 1
        return node

    def _validate_node(self, node: Node) -> None:
        if not isinstance(node, Node) or node._owner is not self:
            raise ValueError("node does not belong to this list")
