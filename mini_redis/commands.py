"""Redis 스타일의 명령어 파싱 및 응답 포맷팅."""

import shlex
from typing import Optional, Tuple

from mini_redis.store import ExpiryOutOfRangeError, MiniRedis, OutOfMemoryError


INTEGER_ERROR = "(error) ERR value is not an integer or out of range"
SYNTAX_ERROR = "(error) ERR syntax error"
OOM_ERROR = "(error) OOM command not allowed when used_memory > 'maxmemory'"
MIN_INTEGER = -(1 << 63)
MAX_INTEGER = (1 << 63) - 1


def quote_string(value: str) -> str:
    """문자열을 Redis 스타일의 따옴표로 감싼 형태로 반환합니다."""

    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return '"{}"'.format(escaped)


class CommandProcessor:
    """입력된 한 줄을 파싱하여 MiniRedis 저장소에서 실행합니다."""

    __slots__ = ("_store",)

    def __init__(self, store: Optional[MiniRedis] = None) -> None:
        self._store = store if store is not None else MiniRedis()

    @property
    def store(self) -> MiniRedis:
        return self._store

    def execute(self, line: str) -> Tuple[Optional[str], bool]:
        try:
            tokens = shlex.split(line, posix=True)
        except ValueError:
            return SYNTAX_ERROR, False

        if not tokens:
            return None, False

        original_command = tokens[0]
        command = original_command.upper()

        if command == "EXIT" or command == "QUIT":
            if len(tokens) != 1:
                return self._wrong_arguments(original_command), False
            return None, True
        if command == "SET":
            return self._set(tokens, original_command)
        if command == "GET":
            return self._get(tokens, original_command)
        if command == "DEL":
            return self._delete(tokens, original_command)
        if command == "EXISTS":
            return self._exists(tokens, original_command)
        if command == "DBSIZE":
            return self._dbsize(tokens, original_command)
        if command == "KEYS":
            return self._keys(tokens, original_command)
        if command == "CONFIG":
            return self._config(tokens, original_command)
        if command == "INFO":
            return self._info(tokens, original_command)
        if command == "EXPIRE":
            return self._expire(tokens, original_command)
        if command == "TTL":
            return self._ttl(tokens, original_command)

        return "(error) ERR unknown command '{}'".format(original_command), False

    def _set(self, tokens, command: str) -> Tuple[str, bool]:
        if len(tokens) != 3:
            return self._wrong_arguments(command), False
        try:
            self._store.set(tokens[1], tokens[2])
        except OutOfMemoryError:
            return OOM_ERROR, False
        return "OK", False

    def _get(self, tokens, command: str) -> Tuple[str, bool]:
        if len(tokens) != 2:
            return self._wrong_arguments(command), False
        value = self._store.get(tokens[1])
        if value is None:
            return "(nil)", False
        return quote_string(value), False

    def _delete(self, tokens, command: str) -> Tuple[str, bool]:
        if len(tokens) != 2:
            return self._wrong_arguments(command), False
        return self._integer(self._store.delete(tokens[1])), False

    def _exists(self, tokens, command: str) -> Tuple[str, bool]:
        if len(tokens) != 2:
            return self._wrong_arguments(command), False
        return self._integer(self._store.exists(tokens[1])), False

    def _dbsize(self, tokens, command: str) -> Tuple[str, bool]:
        if len(tokens) != 1:
            return self._wrong_arguments(command), False
        return self._integer(self._store.dbsize()), False

    def _keys(self, tokens, command: str) -> Tuple[str, bool]:
        if len(tokens) != 1:
            return self._wrong_arguments(command), False

        output = ""
        index = 0
        for key in self._store.keys():
            index += 1
            if output:
                output += "\n"
            output += "{}. {}".format(index, quote_string(key))
        if index == 0:
            return "(empty array)", False
        return output, False

    def _config(self, tokens, command: str) -> Tuple[str, bool]:
        if len(tokens) != 4:
            return self._wrong_arguments(command), False
        if tokens[1].upper() != "SET" or tokens[2].lower() != "maxmemory":
            return SYNTAX_ERROR, False

        maxmemory = self._parse_integer(tokens[3])
        if maxmemory is None or maxmemory < 0:
            return INTEGER_ERROR, False
        self._store.config_set_maxmemory(maxmemory)
        return "OK", False

    def _info(self, tokens, command: str) -> Tuple[str, bool]:
        if len(tokens) != 2:
            return self._wrong_arguments(command), False
        if tokens[1].lower() != "memory":
            return SYNTAX_ERROR, False

        info = self._store.info_memory()
        return (
            "used_memory:{}\nmaxmemory:{}\nevicted_keys:{}".format(
                info.used_memory,
                info.maxmemory,
                info.evicted_keys,
            ),
            False,
        )

    def _expire(self, tokens, command: str) -> Tuple[str, bool]:
        if len(tokens) != 3:
            return self._wrong_arguments(command), False
        seconds = self._parse_integer(tokens[2])
        if seconds is None:
            return INTEGER_ERROR, False
        try:
            result = self._store.expire(tokens[1], seconds)
        except ExpiryOutOfRangeError:
            return INTEGER_ERROR, False
        return self._integer(result), False

    def _ttl(self, tokens, command: str) -> Tuple[str, bool]:
        if len(tokens) != 2:
            return self._wrong_arguments(command), False
        return self._integer(self._store.ttl(tokens[1])), False

    @staticmethod
    def _parse_integer(value: str) -> Optional[int]:
        try:
            parsed = int(value)
        except ValueError:
            return None
        if parsed < MIN_INTEGER or parsed > MAX_INTEGER:
            return None
        return parsed

    @staticmethod
    def _integer(value: int) -> str:
        return "(integer) {}".format(value)

    @staticmethod
    def _wrong_arguments(command: str) -> str:
        return "(error) ERR wrong number of arguments for '{}' command".format(
            command
        )
