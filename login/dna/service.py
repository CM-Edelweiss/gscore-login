from __future__ import annotations

from .schemas import DnaCredential, LoginResultModel
from .dna import DnaClient, DnaError
from .state import LoginSession, publish
from ..utils.logger import logger

SMS_SENT = "验证码已发送"
NOT_BOUND = "皎皎角未绑定二重螺旋账号"
SUCCESS = "登录成功"


async def send_sms(session: LoginSession, mobile: str, v_json: str) -> LoginResultModel:
    client = DnaClient(session.dev_code)
    try:
        await client.send_sms_code(mobile, v_json)
    except DnaError as err:
        logger.warning(f"[DNA-LOGIN] sms 下发失败 auth={session.auth}: {err.message}")
        return LoginResultModel(ok=False, msg=err.message)
    return LoginResultModel(ok=True, msg=SMS_SENT)


async def perform_login(session: LoginSession, mobile: str, code: str) -> LoginResultModel:
    client = DnaClient(session.dev_code)
    try:
        account = await client.sdk_login(mobile, code)
    except DnaError as err:
        logger.warning(f"[DNA-LOGIN] 皎皎角短信登录失败 auth={session.auth}: {err.message}")
        publish(session, "failed", msg=err.message)
        return LoginResultModel(ok=False, msg=err.message)

    if not account.isComplete:
        logger.warning(f"[DNA-LOGIN] 皎皎角未绑定二重螺旋 auth={session.auth} userId={account.userId}")
        publish(session, "failed", msg=NOT_BOUND)
        return LoginResultModel(ok=False, msg=NOT_BOUND)

    cred = DnaCredential(
        token=account.token,
        dev_code=session.dev_code,
        d_num=account.dNum or "",  # schema 上 dNum 可空，落协议时统一成空串
        refresh_token=account.refreshToken,
    )
    publish(session, "success", msg=SUCCESS, credential=cred)
    logger.info(f"[DNA-LOGIN] 登录成功 auth={session.auth} userId={account.userId}")
    return LoginResultModel(ok=True, msg=SUCCESS)
