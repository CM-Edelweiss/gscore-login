from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from starlette.responses import StreamingResponse

from ..schemas import StatusResponse
from ..state import drop_session, get_session
from ...utils.logger import logger
from ._helpers import verify_listen

router = APIRouter()

_HEARTBEAT_S = 15.0
_TERMINAL = {"success", "failed", "expired"}


def _format_event(snap: StatusResponse) -> str:
    return f"event: status\ndata: {snap.model_dump_json()}\n\n"


@router.get("/events/{auth_token}")
async def login_events(auth_token: str, ts: int, sig: str, request: Request) -> StreamingResponse:
    verify_listen(auth_token, ts, sig)

    async def stream() -> AsyncIterator[str]:
        session = get_session(auth_token)
        if session is None:
            yield _format_event(StatusResponse(status="expired"))
            return

        queue = session.add_listener()
        try:
            while True:
                if await request.is_disconnected():
                    return
                try:
                    snap = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_S)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"  # SSE 注释行作心跳，浏览器/httpx 都会忽略但能保持连接
                    continue

                yield _format_event(snap)
                if snap.status in _TERMINAL:
                    return
        finally:
            session.remove_listener(queue)
            if session.status in _TERMINAL:
                drop_session(auth_token)
                logger.debug(f"[NTE-LOGIN] SSE 终态后丢弃会话 auth={auth_token}")

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 关掉 nginx 缓冲
        },
    )
