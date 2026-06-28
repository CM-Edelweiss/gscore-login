from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException
from starlette.responses import JSONResponse

from ..schemas import LoginPayload, LoginResultModel, SendSmsPayload, StartPayload, StartResponse
from ..service import perform_login, send_sms
from login_env import settings
from ..state import create_session
from ._helpers import require_session, verify_start

router = APIRouter()

_MOBILE_RE = re.compile(r"^1\d{10}$")
_CODE_RE = re.compile(r"^\d{4,8}$")


def _result(model: LoginResultModel) -> JSONResponse:
    return JSONResponse(model.model_dump(), status_code=200 if model.ok else 400)


@router.post("/start", response_model=StartResponse)
async def nte_start(payload: StartPayload) -> StartResponse:
    verify_start(payload)
    create_session(payload.auth, payload.user_id, payload.bot_id, payload.group_id)
    return StartResponse(auth=payload.auth, expires_in_s=settings.session_ttl_s)


@router.post("/sendSmsCode")
async def nte_send_sms(payload: SendSmsPayload) -> JSONResponse:
    if not _MOBILE_RE.match(payload.mobile):
        return _result(LoginResultModel(ok=False, msg="手机号格式错误"))
    session = require_session(payload.auth)
    return _result(await send_sms(session, payload.mobile))


@router.post("/login")
async def nte_login(payload: LoginPayload) -> JSONResponse:
    if not _MOBILE_RE.match(payload.mobile):
        return _result(LoginResultModel(ok=False, msg="手机号格式错误"))
    if not _CODE_RE.match(payload.code):
        return _result(LoginResultModel(ok=False, msg="验证码格式错误"))
    session = require_session(payload.auth)
    if session.status == "success":
        # 已登录的会话不重复跑老虎接口；NTEUID 端拿过结果再来访问就让它走 done 页
        raise HTTPException(status_code=409, detail="already_finished")
    return _result(await perform_login(session, payload.mobile, payload.code))
