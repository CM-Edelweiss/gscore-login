from __future__ import annotations

import hashlib
import hmac
import time
from collections.abc import Iterable


def sign(secret: str, parts: Iterable[str]) -> str:
    """`HMAC-SHA256(secret, "|".join(parts))` 取十六进制。`parts` 顺序敏感。"""
    msg = "|".join(parts).encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def verify(secret: str, parts: Iterable[str], expected: str, *, ts: int, ttl_s: int) -> bool:
    """空 `secret` 表示禁用签名校验（启动时已 warn）；不接受空 `expected`。"""
    if not secret:
        return True
    if not expected:
        return False
    now = int(time.time())
    if abs(now - ts) > ttl_s:
        return False
    return hmac.compare_digest(sign(secret, parts), expected)
