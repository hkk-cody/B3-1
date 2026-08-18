"""해시맵 및 LRU에서 사용되는 센티널 기반 이중 연결 리스트."""

from typing import Any, Iterator, Optional


class Node:
    """O(1) 상수 시간 내에 위치를 변경할 수 있는 노드."""

    __slots__ = ("prev", "next", "data", "_owner")

    def __init__(self, data: Any = None) -> None:
        self.prev: Optional["Node"] = None
        self.next: Optional["Node"] = None
        self.data = data
        self._owner: Optional["DoublyLinkedList"] = None


class DoublyLinkedList:
    """숨겨진 head 및 tail 센티널 노드를 가진 이중 연결 리스트."""

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
        if first is None:  # 센티널 불변 조건으로 인해 도달할 수 없습니다.
            raise RuntimeError("corrupt linked list")
        return self._insert_between(data, self._head, first)

    def insert_back(self, data: Any) -> Node:
        last = self._tail.prev
        if last is None:  # 센티널 불변 조건으로 인해 도달할 수 없습니다.
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
        """탐색 없이 주어진 노드를 즉시 제거합니다."""

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
        """크기(size)를 변경하지 않고 주어진 노드를 맨 앞으로 이동합니다."""

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
