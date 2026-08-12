import unittest

from mini_redis.linked_list import DoublyLinkedList, Node


class DoublyLinkedListTests(unittest.TestCase):
    def test_empty_list(self):
        linked = DoublyLinkedList()

        self.assertEqual(0, linked.size())
        self.assertIsNone(linked.front_node)
        self.assertIsNone(linked.back_node)
        self.assertIsNone(linked.remove_front())
        self.assertIsNone(linked.remove_back())

    def test_insert_at_both_ends_and_remove(self):
        linked = DoublyLinkedList()
        middle = linked.insert_front("middle")
        front = linked.insert_front("front")
        back = linked.insert_back("back")

        self.assertEqual(["front", "middle", "back"], list(linked))
        self.assertIs(front, linked.front_node)
        self.assertIs(back, linked.back_node)
        self.assertEqual("front", linked.remove_front())
        self.assertEqual("back", linked.remove_back())
        self.assertEqual("middle", linked.remove_node(middle))
        self.assertEqual(0, linked.size())

    def test_remove_middle_node(self):
        linked = DoublyLinkedList()
        linked.insert_back(1)
        middle = linked.insert_back(2)
        linked.insert_back(3)

        self.assertEqual(2, linked.remove_node(middle))
        self.assertEqual([1, 3], list(linked))

    def test_move_to_front_keeps_identity_and_size(self):
        linked = DoublyLinkedList()
        first = linked.insert_back("a")
        last = linked.insert_back("b")

        self.assertIs(last, linked.move_to_front(last))
        self.assertEqual(["b", "a"], list(linked))
        self.assertEqual(2, linked.size())
        self.assertIs(last, linked.move_to_front(last))
        self.assertEqual(["b", "a"], list(linked))
        self.assertIs(first, linked.back_node)

    def test_rejects_foreign_and_removed_nodes(self):
        linked = DoublyLinkedList()
        other = DoublyLinkedList()
        node = linked.insert_front("value")

        with self.assertRaises(ValueError):
            other.remove_node(node)
        linked.remove_node(node)
        with self.assertRaises(ValueError):
            linked.move_to_front(node)
        with self.assertRaises(ValueError):
            linked.remove_node(Node("detached"))


if __name__ == "__main__":
    unittest.main()
