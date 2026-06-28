from __future__ import annotations

from fastapi import APIRouter

from ..schemas import StatusResponse
from ..state import drop_session, get_session
from ._helpers import verify_listen

router = APIRouter()


@router.get("/status/{auth_token}", response_model=StatusResponse)
async def login_status(auth_token: str, ts: int, sig: str) -> StatusResponse:
    verify_listen(auth_token, ts, sig)
    session = get_session(auth_token)
    if session is None:
        return StatusResponse(status="expired")
    snap = session.snapshot()
    if snap.status in {"success", "failed"}:
        # 终态被拿走后立刻丢弃，避免再被消费一次（凭据是一次性的）。
        drop_session(auth_token)
    return snap
