import unittest

from mini_redis.store import ExpiryOutOfRangeError, MiniRedis, OutOfMemoryError


class FakeClock:
    def __init__(self, initial=100.0):
        self.now = initial

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class MiniRedisStoreTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.store = MiniRedis(clock=self.clock)

    def test_basic_string_operations(self):
        self.assertIsNone(self.store.get("missing"))
        self.store.set("name", "Alice")

        self.assertEqual("Alice", self.store.get("name"))
        self.assertEqual(1, self.store.exists("name"))
        self.assertEqual(1, self.store.dbsize())
        self.assertEqual(["name"], list(self.store.keys()))
        self.assertEqual(1, self.store.delete("name"))
        self.assertEqual(0, self.store.delete("name"))
        self.assertEqual(0, self.store.exists("name"))

    def test_memory_uses_utf8_bytes_and_overwrite_delta(self):
        self.store.set("한", "값")
        self.assertEqual(6, self.store.info_memory().used_memory)

        self.store.set("한", "value")
        self.assertEqual(8, self.store.info_memory().used_memory)

    def test_get_updates_lru_but_exists_does_not(self):
        self.store.config_set_maxmemory(4)
        self.store.set("a", "1")
        self.store.set("b", "2")
        self.assertEqual(1, self.store.exists("a"))

        self.store.set("c", "3")
        self.assertIsNone(self.store.get("a"))
        self.assertEqual("2", self.store.get("b"))

        second = MiniRedis(clock=self.clock)
        second.config_set_maxmemory(4)
        second.set("a", "1")
        second.set("b", "2")
        self.assertEqual("1", second.get("a"))
        second.set("c", "3")
        self.assertIsNone(second.get("b"))
        self.assertEqual("1", second.get("a"))

    def test_set_existing_key_updates_lru(self):
        self.store.config_set_maxmemory(4)
        self.store.set("a", "1")
        self.store.set("b", "2")

        self.store.set("a", "x")
        self.store.set("c", "3")

        self.assertIsNone(self.store.get("b"))
        self.assertEqual("x", self.store.get("a"))

    def test_set_can_evict_multiple_lru_entries(self):
        self.store.config_set_maxmemory(6)
        self.store.set("a", "1")
        self.store.set("b", "2")
        self.store.set("c", "3")

        self.store.set("zz", "99")

        self.assertIsNone(self.store.get("a"))
        self.assertIsNone(self.store.get("b"))
        self.assertEqual("3", self.store.get("c"))
        self.assertEqual("99", self.store.get("zz"))
        info = self.store.info_memory()
        self.assertEqual(6, info.used_memory)
        self.assertEqual(2, info.evicted_keys)

    def test_oversized_new_entry_is_atomic(self):
        self.store.config_set_maxmemory(3)
        self.store.set("a", "1")
        self.store.expire("a", 10)

        with self.assertRaises(OutOfMemoryError):
            self.store.set("long", "value")

        self.assertEqual("1", self.store.get("a"))
        self.assertEqual(10, self.store.ttl("a"))
        self.assertEqual(2, self.store.used_memory)
        self.assertEqual(0, self.store.evicted_keys)

    def test_oversized_overwrite_preserves_value_ttl_and_memory(self):
        self.store.config_set_maxmemory(3)
        self.store.set("a", "1")
        self.store.expire("a", 5)

        with self.assertRaises(OutOfMemoryError):
            self.store.set("a", "large")

        self.assertEqual("1", self.store.get("a"))
        self.assertEqual(5, self.store.ttl("a"))
        self.assertEqual(2, self.store.used_memory)

    def test_oversized_overwrite_preserves_lru_order(self):
        self.store.config_set_maxmemory(4)
        self.store.set("a", "1")
        self.store.set("b", "2")

        with self.assertRaises(OutOfMemoryError):
            self.store.set("a", "oversized")
        self.store.set("c", "3")

        self.assertIsNone(self.store.get("a"))
        self.assertEqual("2", self.store.get("b"))
        self.assertEqual("3", self.store.get("c"))
        self.assertEqual(1, self.store.evicted_keys)

    def test_lowering_maxmemory_waits_until_next_set(self):
        self.store.set("large", "value")
        self.store.config_set_maxmemory(2)
        self.assertEqual(10, self.store.info_memory().used_memory)

        self.store.set("a", "b")

        self.assertIsNone(self.store.get("large"))
        self.assertEqual("b", self.store.get("a"))
        self.assertEqual(1, self.store.evicted_keys)

    def test_zero_maxmemory_is_unlimited(self):
        self.store.config_set_maxmemory(0)
        self.store.set("large", "x" * 1000)

        self.assertEqual(1005, self.store.used_memory)
        self.assertEqual(0, self.store.evicted_keys)

    def test_ttl_contract_and_flooring(self):
        self.store.set("session", "token")
        self.assertEqual(-1, self.store.ttl("session"))
        self.assertEqual(-2, self.store.ttl("missing"))
        self.assertEqual(1, self.store.expire("session", 10))
        self.assertEqual(10, self.store.ttl("session"))

        self.clock.advance(9.2)
        self.assertEqual(0, self.store.ttl("session"))
        self.clock.advance(0.8)
        self.assertEqual(-2, self.store.ttl("session"))
        self.assertIsNone(self.store.get("session"))

    def test_expire_missing_and_non_positive_expiry(self):
        self.assertEqual(0, self.store.expire("missing", 5))
        self.store.set("zero", "value")
        self.assertEqual(1, self.store.expire("zero", 0))
        self.assertEqual(0, self.store.exists("zero"))
        self.store.set("negative", "value")
        self.assertEqual(1, self.store.expire("negative", -1))
        self.assertEqual(0, self.store.dbsize())

    def test_reexpire_ignores_stale_heap_record(self):
        self.store.set("key", "value")
        self.store.expire("key", 5)
        self.clock.advance(2)
        self.store.expire("key", 10)

        self.clock.advance(3)
        self.assertEqual(1, self.store.dbsize())
        self.assertEqual(7, self.store.ttl("key"))
        self.clock.advance(7)
        self.assertEqual(0, self.store.dbsize())

    def test_out_of_range_expire_preserves_existing_ttl(self):
        fractional_clock = FakeClock(0.022059208)
        fractional_store = MiniRedis(clock=fractional_clock)
        fractional_store.set("short", "value")
        self.assertEqual(1, fractional_store.expire("short", 1))
        self.assertEqual(1, fractional_store.ttl("short"))

        fractional_store.set("large", "value")
        large_seconds = (1 << 63) - 1
        self.assertEqual(1, fractional_store.expire("large", large_seconds))
        self.assertEqual(large_seconds, fractional_store.ttl("large"))

        self.store.set("key", "value")
        self.store.expire("key", 5)

        out_of_range_values = (
            -(10**400),
            -(1 << 63) - 1,
            1 << 63,
            10**400,
        )
        for seconds in out_of_range_values:
            with self.subTest(seconds=seconds):
                with self.assertRaises(ExpiryOutOfRangeError):
                    self.store.expire("key", seconds)
                self.assertEqual(5, self.store.ttl("key"))

        self.clock.advance(5)
        self.assertIsNone(self.store.get("key"))

    def test_set_overwrite_clears_ttl(self):
        self.store.set("key", "old")
        self.store.expire("key", 3)

        self.store.set("key", "new")
        self.clock.advance(3)

        self.assertEqual("new", self.store.get("key"))
        self.assertEqual(-1, self.store.ttl("key"))

    def test_delete_then_reinsert_is_not_removed_by_stale_record(self):
        self.store.set("key", "old")
        self.store.expire("key", 3)
        self.store.delete("key")
        self.store.set("key", "new")

        self.clock.advance(3)

        self.assertEqual("new", self.store.get("key"))

    def test_lru_eviction_then_reinsert_ignores_old_expiry_record(self):
        self.store.config_set_maxmemory(4)
        self.store.set("a", "1")
        self.store.expire("a", 5)
        self.store.set("b", "2")
        self.store.set("c", "3")
        self.assertIsNone(self.store.get("a"))

        self.store.delete("b")
        self.store.set("a", "new")
        self.clock.advance(5)

        self.assertEqual("new", self.store.get("a"))

    def test_all_observation_commands_purge_expired_keys(self):
        self.store.set("key", "value")
        self.store.expire("key", 1)
        self.clock.advance(1)

        self.assertEqual([], list(self.store.keys()))
        self.assertEqual(0, self.store.dbsize())
        info = self.store.info_memory()
        self.assertEqual(0, info.used_memory)
        self.assertEqual(0, info.evicted_keys)

    def test_delete_and_expiry_do_not_increment_eviction_count(self):
        self.store.set("delete", "value")
        self.store.delete("delete")
        self.store.set("expire", "value")
        self.store.expire("expire", 1)
        self.clock.advance(1)
        self.store.dbsize()

        self.assertEqual(0, self.store.evicted_keys)


if __name__ == "__main__":
    unittest.main()
