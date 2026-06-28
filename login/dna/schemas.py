from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LoginStatus = Literal["pending", "success", "failed", "expired"]


class _ProtocolModel(BaseModel):
    """dna-login ↔ DNAUID 协议层模型基类。允许 snake_case / camelCase 兼容入参。"""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class StartPayload(_ProtocolModel):
    auth: str = Field(min_length=4, max_length=64, description="登录会话 token，由 DNAUID 端算 sha256(user_id)[:8]")
    user_id: str = Field(min_length=1, max_length=64, description="发起登录的用户 ID")
    bot_id: str = Field(default="", max_length=64, description="发起登录的 bot 平台 ID")
    group_id: str | None = Field(default=None, max_length=64, description="群聊场景的 group ID，私聊场景为 None")
    ts: int = Field(description="UNIX 秒级时间戳，用于防重放")
    sig: str = Field(default="", description='HMAC-SHA256("start|auth|user_id|ts")，空表示未启用签名')


class StartResponse(_ProtocolModel):
    auth: str = Field(description="原样回写的会话 token")
    expires_in_s: int = Field(description="会话存活秒数")


class SendSmsPayload(_ProtocolModel):
    auth: str = Field(min_length=4, max_length=64, description="会话 token")
    mobile: str = Field(min_length=11, max_length=11, description="11 位中国大陆手机号")
    v_json: str = Field(alias="vJson", min_length=2, description="浏览器侧 Alicom4 验证码回执 JSON 字符串")


class LoginPayload(_ProtocolModel):
    auth: str = Field(min_length=4, max_length=64, description="会话 token")
    mobile: str = Field(min_length=11, max_length=11, description="11 位中国大陆手机号")
    code: str = Field(min_length=4, max_length=8, description="短信验证码")


class LoginResultModel(_ProtocolModel):
    """浏览器表单回执，不带敏感凭据。"""

    ok: bool = Field(description="本次操作是否成功")
    msg: str = Field(default="", description="给用户看的展示文案")


class DnaCredential(_ProtocolModel):
    """登录成功后回传给 DNAUID 的凭据；DNAUID 拿到后走 dna_login_by_token。"""

    token: str = Field(description="皎皎角 token（DNAUID 侧落库为 cookie）")
    dev_code: str = Field(description="本次登录使用的设备码，后续请求需复用")
    d_num: str = Field(default="", description="皎皎角 dNum")
    refresh_token: str = Field(default="", description="皎皎角 refreshToken")


class StatusResponse(_ProtocolModel):
    """transport 通用事件结构（HTTP 轮询、SSE、WS 共用）。"""

    status: LoginStatus = Field(description="会话当前状态")
    msg: str = Field(default="", description="给用户看的展示文案")
    credential: DnaCredential | None = Field(default=None, description="终态为 success 时的凭据，否则为 None")
