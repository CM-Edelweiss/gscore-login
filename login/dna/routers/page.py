from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from jinja2 import Environment, FileSystemLoader
from starlette.responses import HTMLResponse

from login_env import settings
from ..state import get_session

router = APIRouter()

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
_env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=True)


def _ttl_label(ttl_s: int) -> str:
    if ttl_s >= 60 and ttl_s % 60 == 0:
        return f"{ttl_s // 60} 分钟内有效"
    return f"{ttl_s} 秒内有效"


@router.get("/i/{auth_token}", response_class=HTMLResponse)
async def login_page(auth_token: str) -> HTMLResponse:
    session = get_session(auth_token)
    if session is None:
        return HTMLResponse(_env.get_template("404.html").render(), status_code=404)
    if session.status == "success":
        return HTMLResponse(_env.get_template("done.html").render())
    return HTMLResponse(
        _env.get_template("login.html").render(
            auth=auth_token,
            user_id=session.user_id,
            ttl_label=_ttl_label(settings.session_ttl_s),
        )
    )


@router.get("/done", response_class=HTMLResponse)
async def login_done() -> HTMLResponse:
    return HTMLResponse(_env.get_template("done.html").render())
