import unittest

from mini_redis.min_heap import MinHeap


class MinHeapTests(unittest.TestCase):
    def test_empty_heap(self):
        heap = MinHeap()

        self.assertEqual(0, heap.size())
        self.assertIsNone(heap.peek())
        self.assertIsNone(heap.pop())

    def test_push_peek_and_pop_in_order(self):
        heap = MinHeap()
        for value in (5, 1, 4, 2, 3):
            heap.push(value)

        self.assertEqual(1, heap.peek())
        self.assertEqual(5, heap.size())
        self.assertEqual([1, 2, 3, 4, 5], [heap.pop() for _ in range(5)])
        self.assertEqual(0, heap.size())

    def test_duplicate_priorities_are_preserved(self):
        heap = MinHeap()
        for value in (2, 1, 2, 1):
            heap.push(value)

        self.assertEqual([1, 1, 2, 2], [heap.pop() for _ in range(4)])


if __name__ == "__main__":
    unittest.main()
