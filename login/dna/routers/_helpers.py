from __future__ import annotations

from fastapi import HTTPException

from ..schemas import StartPayload
from login_env import settings
from ..state import LoginSession, get_session
from ...utils.signature import verify


def require_session(auth: str) -> LoginSession:
    session = get_session(auth)
    if session is None:
        raise HTTPException(status_code=404, detail="session_expired")
    return session


def _verify(parts: list[str], sig: str, ts: int) -> None:
    if not verify(settings.shared_secret, parts, sig, ts=ts, ttl_s=settings.sig_ttl_s):
        raise HTTPException(status_code=401, detail="bad_signature")


def verify_start(payload: StartPayload) -> None:
    """`POST /dna/start` 的签名校验：sig = HMAC(secret, "start|auth|user_id|ts")。"""
    _verify(["start", payload.auth, payload.user_id, str(payload.ts)], payload.sig, payload.ts)


def verify_listen(auth: str, ts: int, sig: str) -> None:
    """transport 订阅类接口的签名校验：sig = HMAC(secret, "listen|auth|ts")。"""
    _verify(["listen", auth, str(ts)], sig, ts)
