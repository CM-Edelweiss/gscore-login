from __future__ import annotations

from .constants import LAOHU_APP_ID, LAOHU_APP_KEY
from .schemas import LaohuCredential, LoginResultModel
from .laohu import LaohuClient, LaohuError
from .state import LoginSession, publish
from ..utils.logger import logger

SMS_SENT = "验证码已发送"
SMS_SEND_FAILED = "验证码发送失败，请稍后再试"
SMS_LOGIN_FAILED = "验证码错误或已过期，请重新获取"
SUCCESS = "登录成功"


async def send_sms(session: LoginSession, mobile: str) -> LoginResultModel:
    client = LaohuClient(LAOHU_APP_ID, LAOHU_APP_KEY, device=session.device)
    try:
        await client.send_sms_code(mobile)
    except LaohuError as err:
        logger.warning(f"[NTE-LOGIN] sms 下发失败 auth={session.auth}: {err.message}")
        return LoginResultModel(ok=False, msg=SMS_SEND_FAILED)
    return LoginResultModel(ok=True, msg=SMS_SENT)


async def perform_login(session: LoginSession, mobile: str, code: str) -> LoginResultModel:
    client = LaohuClient(LAOHU_APP_ID, LAOHU_APP_KEY, device=session.device)
    try:
        account = await client.login_by_sms(mobile, code)
    except LaohuError as err:
        logger.warning(f"[NTE-LOGIN] 老虎短信登录失败 auth={session.auth}: {err.message}")
        publish(session, "failed", msg=SMS_LOGIN_FAILED)
        return LoginResultModel(ok=False, msg=SMS_LOGIN_FAILED)

    cred = LaohuCredential(laohu_token=account.token, laohu_user_id=str(account.user_id))
    publish(session, "success", msg=SUCCESS, credential=cred)
    logger.info(f"[NTE-LOGIN] 登录成功 auth={session.auth} laohu_user_id={account.user_id}")
    return LoginResultModel(ok=True, msg=SUCCESS)
