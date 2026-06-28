from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field

from .schemas import DnaCredential, LoginStatus, StatusResponse
from login_env import settings
from ..utils.cache import TimedCache
from ..utils.logger import logger


def make_dev_code() -> str:
    return str(uuid.uuid4()).upper()


@dataclass
class LoginSession:
    auth: str
    user_id: str
    bot_id: str
    group_id: str | None
    dev_code: str
    status: LoginStatus = "pending"
    msg: str = ""
    credential: DnaCredential | None = None
    listeners: list[asyncio.Queue[StatusResponse]] = field(default_factory=list)

    def snapshot(self) -> StatusResponse:
        return StatusResponse(status=self.status, msg=self.msg, credential=self.credential)

    def add_listener(self) -> asyncio.Queue[StatusResponse]:
        """SSE / WS 订阅者注册一条队列；当前快照立刻塞进去，避免错过已 push 的终态。"""
        queue: asyncio.Queue[StatusResponse] = asyncio.Queue(maxsize=8)
        queue.put_nowait(self.snapshot())
        self.listeners.append(queue)
        return queue

    def remove_listener(self, queue: asyncio.Queue[StatusResponse]) -> None:
        try:
            self.listeners.remove(queue)
        except ValueError:
            pass


_SESSIONS: TimedCache = TimedCache(timeout_s=settings.session_ttl_s, maxsize=4096)


def create_session(auth: str, user_id: str, bot_id: str, group_id: str | None) -> LoginSession:
    existing: LoginSession | None = _SESSIONS.get(auth)
    if existing and existing.status == "pending":
        # 重发同一 auth 的 start：保留旧 session 和 listener，避免断开浏览器/transport 端
        return existing

    session = LoginSession(
        auth=auth,
        user_id=user_id,
        bot_id=bot_id,
        group_id=group_id,
        dev_code=make_dev_code(),
    )
    _SESSIONS.set(auth, session)
    logger.info(f"[DNA-LOGIN] 新会话 auth={auth} user_id={user_id} bot_id={bot_id}")
    return session


def get_session(auth: str) -> LoginSession | None:
    return _SESSIONS.get(auth)


def drop_session(auth: str) -> None:
    _SESSIONS.pop(auth)


def publish(
    session: LoginSession,
    status: LoginStatus,
    msg: str = "",
    credential: DnaCredential | None = None,
) -> None:
    """更新会话状态并广播给所有 listener。终态（success/failed/expired）触发后 listener 应自行退出循环。"""
    session.status = status
    session.msg = msg
    session.credential = credential
    snap = session.snapshot()
    for queue in list(session.listeners):
        try:
            queue.put_nowait(snap)
        except asyncio.QueueFull:
            logger.warning(f"[DNA-LOGIN] listener 队列已满 auth={session.auth}，丢弃事件")
