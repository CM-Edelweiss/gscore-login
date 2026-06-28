from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from ..schemas import StatusResponse
from ..state import drop_session, get_session
from ...utils.logger import logger
from ._helpers import verify_listen

router = APIRouter()

_PING_S = 20.0
_TERMINAL = {"success", "failed", "expired"}


@router.websocket("/ws/{auth_token}")
async def login_ws(websocket: WebSocket, auth_token: str, ts: int, sig: str) -> None:
    try:
        verify_listen(auth_token, ts, sig)
    except Exception:
        # 没握手就关：1008 表示协议层鉴权失败，靠近 HTTP 401 语义
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    session = get_session(auth_token)
    if session is None:
        await websocket.send_json(StatusResponse(status="expired").model_dump())
        await websocket.close()
        return

    queue = session.add_listener()
    try:
        while True:
            try:
                snap = await asyncio.wait_for(queue.get(), timeout=_PING_S)
            except asyncio.TimeoutError:
                # WebSocket 协议自带 ping，但很多反代不透传：手动塞个轻量 JSON 当 keepalive
                await websocket.send_json({"status": "heartbeat"})
                continue

            await websocket.send_json(snap.model_dump())
            if snap.status in _TERMINAL:
                await websocket.close()
                return
    except WebSocketDisconnect:
        return
    finally:
        session.remove_listener(queue)
        if session.status in _TERMINAL:
            drop_session(auth_token)
            logger.debug(f"[DNA-LOGIN] WS 终态后丢弃会话 auth={auth_token}")
