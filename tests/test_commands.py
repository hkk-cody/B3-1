import unittest

from mini_redis.commands import CommandProcessor, quote_string
from mini_redis.store import MiniRedis
from tests.test_store import FakeClock


class CommandProcessorTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.store = MiniRedis(clock=self.clock)
        self.commands = CommandProcessor(self.store)

    def execute(self, line):
        output, should_exit = self.commands.execute(line)
        self.assertFalse(should_exit)
        return output

    def test_set_get_exists_delete_dbsize_and_keys(self):
        self.assertEqual("OK", self.execute('SET user:1 "Alice Smith"'))
        self.assertEqual('"Alice Smith"', self.execute("get user:1"))
        self.assertEqual("(integer) 1", self.execute("EXISTS user:1"))
        self.assertEqual("(integer) 1", self.execute("DBSIZE"))
        self.assertEqual('1. "user:1"', self.execute("KEYS"))
        self.assertEqual("(integer) 1", self.execute("DEL user:1"))
        self.assertEqual("(nil)", self.execute("GET user:1"))
        self.assertEqual("(empty array)", self.execute("KEYS"))

    def test_string_output_escapes_quotes_and_backslashes(self):
        self.store.set("key", 'a"b\\c')

        self.assertEqual('"a\\"b\\\\c"', self.execute("GET key"))
        self.assertEqual('"a\\"b\\\\c"', quote_string('a"b\\c'))

    def test_memory_commands_and_oom(self):
        self.assertEqual("OK", self.execute("config set MAXMEMORY 3"))
        self.assertEqual("OK", self.execute("SET a 1"))
        self.assertEqual(
            "used_memory:2\nmaxmemory:3\nevicted_keys:0",
            self.execute("INFO memory"),
        )
        self.assertEqual(
            "(error) OOM command not allowed when used_memory > 'maxmemory'",
            self.execute("SET long value"),
        )

    def test_expire_and_ttl(self):
        self.execute("SET session token")
        self.assertEqual("(integer) -1", self.execute("TTL session"))
        self.assertEqual("(integer) 1", self.execute("EXPIRE session 3"))
        self.assertEqual("(integer) 3", self.execute("TTL session"))
        self.clock.advance(3)
        self.assertEqual("(integer) -2", self.execute("TTL session"))

    def test_commands_are_case_insensitive_but_data_is_preserved(self):
        self.assertEqual("OK", self.execute("sEt Mixed Value"))

        self.assertEqual('"Value"', self.execute("gEt Mixed"))
        self.assertEqual("(nil)", self.execute("GET mixed"))

    def test_unknown_wrong_arity_integer_and_syntax_errors(self):
        self.assertEqual(
            "(error) ERR unknown command 'HELLO'", self.execute("HELLO")
        )
        self.assertEqual(
            "(error) ERR wrong number of arguments for 'GET' command",
            self.execute("GET"),
        )
        self.assertEqual(
            "(error) ERR value is not an integer or out of range",
            self.execute("CONFIG SET maxmemory abc"),
        )
        self.assertEqual(
            "(error) ERR value is not an integer or out of range",
            self.execute("CONFIG SET maxmemory -1"),
        )
        self.assertEqual(
            "(error) ERR value is not an integer or out of range",
            self.execute("EXPIRE key nope"),
        )
        self.assertEqual(
            "(error) ERR syntax error", self.execute('SET key "unfinished')
        )
        self.assertEqual(
            "(error) ERR syntax error", self.execute("CONFIG GET maxmemory 1")
        )
        self.assertEqual("(error) ERR syntax error", self.execute("INFO server"))

    def test_out_of_range_expire_is_atomic(self):
        self.assertEqual("OK", self.execute("SET key value"))
        self.assertEqual("(integer) 1", self.execute("EXPIRE key 5"))

        out_of_range_values = (
            -(10**400),
            -(1 << 63) - 1,
            1 << 63,
            10**400,
        )
        for seconds in out_of_range_values:
            with self.subTest(seconds=seconds):
                output = self.execute("EXPIRE key {}".format(seconds))
                self.assertEqual(
                    "(error) ERR value is not an integer or out of range", output
                )
                self.assertEqual("(integer) 5", self.execute("TTL key"))

        self.assertEqual(
            "(error) ERR value is not an integer or out of range",
            self.execute("CONFIG SET maxmemory {}".format(1 << 63)),
        )

        large_seconds = (1 << 63) - 1
        self.assertEqual(
            "(integer) 1",
            self.execute("EXPIRE key {}".format(large_seconds)),
        )
        self.assertEqual(
            "(integer) {}".format(large_seconds), self.execute("TTL key")
        )

    def test_all_commands_validate_argument_count(self):
        commands = (
            "SET key",
            "GET key extra",
            "DEL",
            "EXISTS",
            "DBSIZE extra",
            "KEYS extra",
            "CONFIG SET maxmemory",
            "INFO",
            "EXPIRE key",
            "TTL key extra",
            "exit extra",
            "quit extra",
        )
        for line in commands:
            with self.subTest(line=line):
                output = self.execute(line)
                self.assertIn("wrong number of arguments", output)

    def test_empty_input_and_exit_commands(self):
        self.assertEqual((None, False), self.commands.execute("   "))
        self.assertEqual((None, True), self.commands.execute("exit"))
        self.assertEqual((None, True), self.commands.execute("QUIT"))


if __name__ == "__main__":
    unittest.main()
