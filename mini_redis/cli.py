"""Interactive command-line interface for Mini Redis."""

import sys
from typing import Optional, TextIO

from mini_redis.commands import CommandProcessor


PROMPT = "mini-redis> "


def run_cli(
    processor: Optional[CommandProcessor] = None,
    input_stream: Optional[TextIO] = None,
    output_stream: Optional[TextIO] = None,
) -> None:
    """Run the REPL until EOF, interruption, exit, or quit."""

    command_processor = processor if processor is not None else CommandProcessor()
    source = input_stream if input_stream is not None else sys.stdin
    destination = output_stream if output_stream is not None else sys.stdout

    while True:
        try:
            destination.write(PROMPT)
            destination.flush()
            line = source.readline()
        except KeyboardInterrupt:
            destination.write("\n")
            destination.flush()
            break

        if line == "":
            break

        output, should_exit = command_processor.execute(line)
        if output is not None:
            destination.write(output)
            destination.write("\n")
            destination.flush()
        if should_exit:
            break
