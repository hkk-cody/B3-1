"""FNV-1a 해싱과 연결 리스트 체이닝을 사용하는 문자열 키 해시맵."""

from typing import Any, Iterator, Optional

from mini_redis.linked_list import DoublyLinkedList, Node


class HashEntry:
    __slots__ = ("key", "value")

    def __init__(self, key: str, value: Any) -> None:
        self.key = key
        self.value = value


class HashMap:
    """내부 저장을 dict에 위임하지 않고 직접 구현한 해시맵."""

    DEFAULT_CAPACITY = 8
    MAX_LOAD_FACTOR = 0.75
    _FNV_OFFSET_BASIS = 14695981039346656037
    _FNV_PRIME = 1099511628211
    _MASK_64 = (1 << 64) - 1

    __slots__ = ("_buckets", "_size")

    def __init__(self, initial_capacity: int = DEFAULT_CAPACITY) -> None:
        if initial_capacity <= 0:
            raise ValueError("initial capacity must be positive")
        self._buckets = [None] * initial_capacity
        self._size = 0

    @property
    def capacity(self) -> int:
        return len(self._buckets)

    def size(self) -> int:
        return self._size

    def put(self, key: str, value: Any) -> Any:
        self._validate_key(key)
        if value is None:
            raise ValueError("None values are not supported")

        index = self._bucket_index(key)
        node = self._find_node(self._buckets[index], key)
        if node is not None:
            previous = node.data.value
            node.data.value = value
            return previous

        if (self._size + 1) / self.capacity > self.MAX_LOAD_FACTOR:
            self._resize(self.capacity * 2)
            index = self._bucket_index(key)

        bucket = self._buckets[index]
        if bucket is None:
            bucket = DoublyLinkedList()
            self._buckets[index] = bucket
        bucket.insert_back(HashEntry(key, value))
        self._size += 1
        return None

    def get(self, key: str) -> Any:
        self._validate_key(key)
        bucket = self._buckets[self._bucket_index(key)]
        node = self._find_node(bucket, key)
        if node is None:
            return None
        return node.data.value

    def remove(self, key: str) -> Any:
        self._validate_key(key)
        index = self._bucket_index(key)
        bucket = self._buckets[index]
        node = self._find_node(bucket, key)
        if node is None or bucket is None:
            return None

        entry = bucket.remove_node(node)
        self._size -= 1
        if bucket.size() == 0:
            self._buckets[index] = None
        return entry.value

    def contains(self, key: str) -> bool:
        self._validate_key(key)
        bucket = self._buckets[self._bucket_index(key)]
        return self._find_node(bucket, key) is not None

    def keys(self) -> Iterator[str]:
        for bucket in self._buckets:
            if bucket is None:
                continue
            for node in bucket.iter_nodes():
                yield node.data.key

    def _hash(self, key: str) -> int:
        value = self._FNV_OFFSET_BASIS
        for byte in key.encode("utf-8"):
            value ^= byte
            value = (value * self._FNV_PRIME) & self._MASK_64
        return value

    def _bucket_index(self, key: str) -> int:
        return self._hash(key) % self.capacity

    @staticmethod
    def _find_node(bucket: Optional[DoublyLinkedList], key: str) -> Optional[Node]:
        if bucket is None:
            return None
        for node in bucket.iter_nodes():
            if node.data.key == key:
                return node
        return None

    def _resize(self, capacity: int) -> None:
        old_buckets = self._buckets
        self._buckets = [None] * capacity
        old_size = self._size
        self._size = 0

        for bucket in old_buckets:
            if bucket is None:
                continue
            for node in bucket.iter_nodes():
                entry = node.data
                self._insert_without_resize(entry.key, entry.value)

        if self._size != old_size:
            raise RuntimeError("hash map resize lost entries")

    def _insert_without_resize(self, key: str, value: Any) -> None:
        index = self._bucket_index(key)
        bucket = self._buckets[index]
        if bucket is None:
            bucket = DoublyLinkedList()
            self._buckets[index] = bucket
        bucket.insert_back(HashEntry(key, value))
        self._size += 1

    @staticmethod
    def _validate_key(key: str) -> None:
        if not isinstance(key, str):
            raise TypeError("hash map keys must be strings")
