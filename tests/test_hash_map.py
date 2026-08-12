import unittest

from mini_redis.hash_map import HashMap


class CollisionHashMap(HashMap):
    def _hash(self, key):
        return 1


class HashMapTests(unittest.TestCase):
    def test_crud_and_update(self):
        mapping = HashMap()

        self.assertIsNone(mapping.put("name", "Alice"))
        self.assertEqual("Alice", mapping.get("name"))
        self.assertTrue(mapping.contains("name"))
        self.assertEqual("Alice", mapping.put("name", "Bob"))
        self.assertEqual(1, mapping.size())
        self.assertEqual("Bob", mapping.remove("name"))
        self.assertIsNone(mapping.remove("name"))
        self.assertFalse(mapping.contains("name"))

    def test_chaining_handles_collisions(self):
        mapping = CollisionHashMap()
        mapping.put("one", 1)
        mapping.put("two", 2)
        mapping.put("three", 3)

        self.assertEqual(1, mapping.get("one"))
        self.assertEqual(2, mapping.remove("two"))
        self.assertEqual(3, mapping.get("three"))
        self.assertEqual(["one", "three"], list(mapping.keys()))

    def test_collision_chain_survives_resize(self):
        mapping = CollisionHashMap()
        for index in range(7):
            mapping.put("key:{}".format(index), index)

        self.assertEqual(16, mapping.capacity)
        self.assertEqual(7, mapping.size())
        for index in range(7):
            self.assertEqual(index, mapping.get("key:{}".format(index)))

    def test_resizes_only_after_load_factor_exceeds_point_seven_five(self):
        mapping = HashMap()
        for index in range(6):
            mapping.put("key:{}".format(index), index)
        self.assertEqual(8, mapping.capacity)

        mapping.put("key:6", 6)

        self.assertEqual(16, mapping.capacity)
        self.assertEqual(7, mapping.size())
        for index in range(7):
            self.assertEqual(index, mapping.get("key:{}".format(index)))

    def test_fnv_one_a_is_stable_for_ascii_and_utf8(self):
        mapping = HashMap()

        self.assertEqual(0xA430D84680AABD0B, mapping._hash("hello"))
        self.assertEqual(mapping._hash("한글"), mapping._hash("한글"))
        self.assertNotEqual(mapping._hash("한글"), mapping._hash("한국"))

    def test_keys_iterates_all_entries(self):
        mapping = HashMap()
        mapping.put("a", 1)
        mapping.put("b", 2)
        mapping.put("c", 3)

        self.assertEqual(["a", "b", "c"], sorted(mapping.keys()))

    def test_rejects_invalid_keys_and_none_values(self):
        mapping = HashMap()
        with self.assertRaises(TypeError):
            mapping.put(1, "value")
        with self.assertRaises(ValueError):
            mapping.put("key", None)


if __name__ == "__main__":
    unittest.main()
