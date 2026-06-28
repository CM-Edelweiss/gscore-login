from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any


def _now() -> float:
    return time.monotonic()


class TimedCache:
    def __init__(self, timeout_s: float = 300.0, maxsize: int = 1024) -> None:
        if timeout_s < 0:
            raise ValueError("TimedCache timeout_s must be >= 0")
        if maxsize <= 0:
            raise ValueError("TimedCache maxsize must be > 0")

        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._timeout_s = timeout_s
        self._maxsize = maxsize

    def set(self, key: str, value: Any) -> None:
        self._sweep()

        if key in self._store:
            self._store.move_to_end(key)
        else:
            while len(self._store) >= self._maxsize:
                self._store.popitem(last=False)

        self._store[key] = (value, _now() + self._timeout_s)

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expire_at = entry
        if expire_at <= _now():
            self._store.pop(key, None)
            return None
        self._store.move_to_end(key)
        return value

    def pop(self, key: str) -> Any | None:
        entry = self._store.pop(key, None)
        if entry is None:
            return None
        value, expire_at = entry
        if expire_at <= _now():
            return None
        return value

    def _sweep(self) -> None:
        now = _now()
        expired = [key for key, (_, expire_at) in self._store.items() if expire_at <= now]
        for key in expired:
            self._store.pop(key, None)
