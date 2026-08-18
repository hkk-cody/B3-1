"""Mini Redis 대화형 명령줄 인터페이스(CLI)."""

import sys
from typing import Optional, TextIO

from mini_redis.commands import CommandProcessor


PROMPT = "mini-redis> "


def run_cli(
    processor: Optional[CommandProcessor] = None,
    input_stream: Optional[TextIO] = None,
    output_stream: Optional[TextIO] = None,
) -> None:
    """EOF, 인터럽트(키보드 중단), exit 또는 quit 입력 시까지 REPL을 실행합니다."""

    command_processor = processor if processor is not None else CommandProcessor()
    source = input_stream if input_stream is not None else sys.stdin
    destination = output_stream if output_stream is not None else sys.stdout

    while True:
        try:
            destination.write(PROMPT)
            destination.flush()
            line = source.readline()

            if line == "":
                break

            output, should_exit = command_processor.execute(line)
            if output is not None:
                destination.write(output)
                destination.write("\n")
                destination.flush()
            if should_exit:
                break
        except KeyboardInterrupt:
            destination.write("\n")
            destination.flush()
            break
