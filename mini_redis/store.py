"""LRU 제거 및 힙 기반 TTL 만료 처리를 지원하는 Mini Redis 스토리지 엔진."""

import time
from typing import Callable, Iterator, Optional

from mini_redis.hash_map import HashMap
from mini_redis.linked_list import DoublyLinkedList, Node
from mini_redis.min_heap import MinHeap


NANOSECONDS_PER_SECOND = 1_000_000_000
MIN_EXPIRE_SECONDS = -(1 << 63)
MAX_EXPIRE_SECONDS = (1 << 63) - 1


class OutOfMemoryError(Exception):
    """단일 항목의 크기가 maxmemory 제한을 초과하여 저장할 수 없을 때 발생합니다."""


class ExpiryOutOfRangeError(ValueError):
    """만료 시간(초)이 지원되는 정수 범위를 벗어날 때 발생합니다."""


class MemoryInfo:
    __slots__ = ("used_memory", "maxmemory", "evicted_keys")

    def __init__(self, used_memory: int, maxmemory: int, evicted_keys: int) -> None:
        self.used_memory = used_memory
        self.maxmemory = maxmemory
        self.evicted_keys = evicted_keys


class CacheEntry:
    __slots__ = ("key", "value", "lru_node", "expire_at", "ttl_version")

    def __init__(self, key: str, value: str) -> None:
        self.key = key
        self.value = value
        self.lru_node: Optional[Node] = None
        self.expire_at: Optional[int] = None
        self.ttl_version = 0


class ExpiryRecord:
    __slots__ = ("expire_at", "ttl_version", "key")

    def __init__(self, expire_at: int, ttl_version: int, key: str) -> None:
        self.expire_at = expire_at
        self.ttl_version = ttl_version
        self.key = key

    def __lt__(self, other: "ExpiryRecord") -> bool:
        if self.expire_at != other.expire_at:
            return self.expire_at < other.expire_at
        if self.ttl_version != other.ttl_version:
            return self.ttl_version < other.ttl_version
        return self.key < other.key


class MiniRedis:
    """직접 구현한 커스텀 자료구조로만 구성된 인메모리 문자열 저장소."""

    __slots__ = (
        "_data",
        "_lru",
        "_expiry_heap",
        "_clock",
        "_used_memory",
        "_maxmemory",
        "_evicted_keys",
    )

    def __init__(self, clock: Optional[Callable[[], float]] = None) -> None:
        self._data = HashMap()
        self._lru = DoublyLinkedList()
        self._expiry_heap = MinHeap()
        if clock is None:
            self._clock = time.monotonic_ns
        else:
            self._clock = lambda: int(clock() * NANOSECONDS_PER_SECOND)
        self._used_memory = 0
        self._maxmemory = 0
        self._evicted_keys = 0

    @property
    def used_memory(self) -> int:
        return self._used_memory

    @property
    def maxmemory(self) -> int:
        return self._maxmemory

    @property
    def evicted_keys(self) -> int:
        return self._evicted_keys

    def set(self, key: str, value: str) -> None:
        self._validate_string(key, "key")
        self._validate_string(value, "value")
        self._purge_expired(self._clock())

        new_size = self._entry_size(key, value)
        if self._maxmemory > 0 and new_size > self._maxmemory:
            raise OutOfMemoryError()

        entry = self._data.get(key)
        if entry is None:
            entry = CacheEntry(key, value)
            entry.lru_node = self._lru.insert_front(entry)
            self._data.put(key, entry)
            self._used_memory += new_size
        else:
            old_size = self._entry_size(entry.key, entry.value)
            entry.value = value
            entry.expire_at = None
            entry.ttl_version += 1
            if entry.lru_node is None:
                raise RuntimeError("cache entry is missing its LRU node")
            self._lru.move_to_front(entry.lru_node)
            self._used_memory += new_size - old_size

        self._evict_to_limit()

    def get(self, key: str) -> Optional[str]:
        self._validate_string(key, "key")
        self._purge_expired(self._clock())
        entry = self._data.get(key)
        if entry is None:
            return None
        if entry.lru_node is None:
            raise RuntimeError("cache entry is missing its LRU node")
        self._lru.move_to_front(entry.lru_node)
        return entry.value

    def delete(self, key: str) -> int:
        self._validate_string(key, "key")
        self._purge_expired(self._clock())
        entry = self._data.get(key)
        if entry is None:
            return 0
        self._delete_entry(entry)
        return 1

    def exists(self, key: str) -> int:
        self._validate_string(key, "key")
        self._purge_expired(self._clock())
        return 1 if self._data.contains(key) else 0

    def dbsize(self) -> int:
        self._purge_expired(self._clock())
        return self._data.size()

    def keys(self) -> Iterator[str]:
        self._purge_expired(self._clock())
        return self._data.keys()

    def expire(self, key: str, seconds: int) -> int:
        self._validate_string(key, "key")
        self._validate_expire_seconds(seconds)
        now = self._clock()
        self._purge_expired(now)
        entry = self._data.get(key)
        if entry is None:
            return 0
        if seconds <= 0:
            self._delete_entry(entry)
            return 1

        expire_at = now + seconds * NANOSECONDS_PER_SECOND
        entry.ttl_version += 1
        entry.expire_at = expire_at
        self._expiry_heap.push(
            ExpiryRecord(entry.expire_at, entry.ttl_version, entry.key)
        )
        return 1

    def ttl(self, key: str) -> int:
        self._validate_string(key, "key")
        now = self._clock()
        self._purge_expired(now)
        entry = self._data.get(key)
        if entry is None:
            return -2
        if entry.expire_at is None:
            return -1
        remaining = (entry.expire_at - now) // NANOSECONDS_PER_SECOND
        return remaining if remaining > 0 else 0

    def config_set_maxmemory(self, maxmemory: int) -> None:
        self._purge_expired(self._clock())
        if maxmemory < 0:
            raise ValueError("maxmemory cannot be negative")
        self._maxmemory = maxmemory

    def info_memory(self) -> MemoryInfo:
        self._purge_expired(self._clock())
        return MemoryInfo(
            self._used_memory,
            self._maxmemory,
            self._evicted_keys,
        )

    def _purge_expired(self, now: int) -> None:
        record = self._expiry_heap.peek()
        while record is not None and record.expire_at <= now:
            record = self._expiry_heap.pop()
            entry = self._data.get(record.key)
            if (
                entry is not None
                and entry.expire_at == record.expire_at
                and entry.ttl_version == record.ttl_version
            ):
                self._delete_entry(entry)
            record = self._expiry_heap.peek()

    def _evict_to_limit(self) -> None:
        while self._maxmemory > 0 and self._used_memory > self._maxmemory:
            node = self._lru.back_node
            if node is None:
                raise RuntimeError("memory is in use but the LRU list is empty")
            self._delete_entry(node.data)
            self._evicted_keys += 1

    def _delete_entry(self, entry: CacheEntry) -> None:
        removed = self._data.remove(entry.key)
        if removed is None:
            raise RuntimeError("cannot delete an entry missing from the hash map")
        if entry.lru_node is None:
            raise RuntimeError("cache entry is missing its LRU node")

        self._lru.remove_node(entry.lru_node)
        self._used_memory -= self._entry_size(entry.key, entry.value)
        entry.lru_node = None
        entry.expire_at = None
        entry.ttl_version += 1

    @staticmethod
    def _entry_size(key: str, value: str) -> int:
        return len(key.encode("utf-8")) + len(value.encode("utf-8"))

    @staticmethod
    def _validate_expire_seconds(seconds: int) -> None:
        if not isinstance(seconds, int):
            raise TypeError("expiration seconds must be an integer")
        if seconds < MIN_EXPIRE_SECONDS or seconds > MAX_EXPIRE_SECONDS:
            raise ExpiryOutOfRangeError("expiration time is out of range")

    @staticmethod
    def _validate_string(value: str, name: str) -> None:
        if not isinstance(value, str):
            raise TypeError("{} must be a string".format(name))
