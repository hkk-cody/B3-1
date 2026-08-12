import io
import os
import subprocess
import sys
import unittest

from mini_redis.cli import run_cli
from mini_redis.commands import CommandProcessor


class CliTests(unittest.TestCase):
    def test_injected_stream_repl(self):
        source = io.StringIO('SET name "Alice Smith"\nGET name\nquit\n')
        destination = io.StringIO()

        run_cli(CommandProcessor(), source, destination)

        self.assertEqual(
            'mini-redis> OK\nmini-redis> "Alice Smith"\nmini-redis> ',
            destination.getvalue(),
        )

    def test_main_runs_as_a_subprocess(self):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        result = subprocess.run(
            [sys.executable, "main.py"],
            cwd=project_root,
            input="SET key value\nDBSIZE\nexit\n",
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(0, result.returncode)
        self.assertEqual("", result.stderr)
        self.assertEqual(
            "mini-redis> OK\nmini-redis> (integer) 1\nmini-redis> ",
            result.stdout,
        )


if __name__ == "__main__":
    unittest.main()
