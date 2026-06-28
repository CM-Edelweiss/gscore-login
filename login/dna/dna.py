from __future__ import annotations

import base64
import hashlib
import secrets
import time
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from ..utils.cache import TimedCache
from ..utils.logger import logger
from ..utils.base import BaseSdkClient, SdkError

DNA_BASE_URL = "https://dnabbs-api.yingxiong.com"
DNA_GAME_ID = 268
DNA_APP_VERSION = "1.3.2"
DNA_USER_AGENT = "okhttp/3.10.0"

# 服务端 /config/getRsaPublicKey 拿不到时的内置公钥（与 DNAUID 插件内置值一致，长期未变）
DNA_FALLBACK_RSA_PUBLIC_KEY = (
    "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDGpdbezK+eknQZQzPOjp8mr/dP+"
    "QHwk8CRkQh6C6qFnfLH3tiyl0pnt3dePuFDnM1PUXGhCkQ157ePJCQgkDU2+mimDmXh0oLFn9zuWSp+"
    "U8uLSLX3t3PpJ8TmNCROfUDWvzdbnShqg7JfDmnrOJz49qd234W84nrfTHbzdqeigQIDAQAB"
)

_RAND_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
# 1.3.0+ 版本的随机串：仅数字，字符集与 Java 端 p63.b() 一致
_RAND_DIGIT_CHARS = "01234567890123456789012345678901234567890123456789010123456789"


class DnaError(SdkError):
    pass


class DnaAccount(BaseModel):
    """`/user/sdkLogin` 返回 data 的子集（字段与 DNAUID 插件 DNALoginRes 对齐）。"""

    model_config = ConfigDict(extra="ignore")

    userId: str
    token: str
    refreshToken: str
    # schema 上就是可空字段（服务端可能回 null），插件侧同样按 Optional 处理
    dNum: str | None = ""
    isComplete: int | None = 0


def rand_str(length: int) -> str:
    return "".join(secrets.choice(_RAND_CHARS) for _ in range(length))


def rand_digit_str(length: int) -> str:
    return "".join(secrets.choice(_RAND_DIGIT_CHARS) for _ in range(length))


def rsa_encrypt(data: str, public_key_base64: str) -> str:
    """RSA/ECB/PKCS1Padding 加密，支持分段（每段最多 117 字节）。"""
    from Crypto.Cipher import PKCS1_v1_5
    from Crypto.PublicKey import RSA

    key = RSA.importKey(base64.b64decode(public_key_base64))
    cipher = PKCS1_v1_5.new(key)
    raw = data.encode("utf-8")
    max_block = 117
    result = b""
    offset = 0
    while offset < len(raw):
        result += cipher.encrypt(raw[offset : offset + max_block])
        offset += max_block
    return base64.b64encode(result).decode("utf-8")


def xor_encode(text: str, key: str) -> str:
    """自定义 XOR 编码（字节值相加，非异或）。"""
    tb = text.encode("utf-8")
    kb = key.encode("utf-8")
    return "".join(f"@{(tb[i] & 255) + (kb[i % len(kb)] & 255)}" for i in range(len(tb)))


def shuffle_md5(md5_hex: str) -> str:
    """MD5 结果位置混淆: 1↔13, 5↔17, 7↔23。"""
    if len(md5_hex) <= 23:
        return md5_hex
    chars = list(md5_hex)
    for i, j in [(1, 13), (5, 17), (7, 23)]:
        chars[i], chars[j] = chars[j], chars[i]
    return "".join(chars)


def sign_shuffled(params: dict[str, Any], app_key: str) -> str:
    """按 key 排序拼接参数 → MD5 → shuffle。"""
    pairs = [f"{k}={params[k]}" for k in sorted(params) if params[k] is not None and str(params[k]) != ""]
    pairs.append(app_key)
    md5_hash = hashlib.md5("&".join(pairs).encode("utf-8")).hexdigest().upper()
    return shuffle_md5(md5_hash)


def _swap(text: str, i: int, j: int) -> str:
    if i < 0 or j < 0 or i >= len(text) or j >= len(text):
        return text
    chars = list(text)
    chars[i], chars[j] = chars[j], chars[i]
    return "".join(chars)


def build_sa_header(raw_sa: str, timestamp: int | None = None) -> str:
    """1.3.x sa header 构建（libalgorithmlib.so cppCoreAlgorithm 的 Python 等价）:

    1. 对 raw_sa(30 位纯数字随机串) 做 4 次位置交换: (1,17)(9,20)(15,16)(22,27)
    2. 在位置 8、16 各插入 5 位时间戳，在位置 22 插入 3 位时间戳
    最终长度 30 + 5 + 5 + 3 = 43
    """
    if timestamp is None:
        timestamp = int(time.time() * 1000)

    sa = raw_sa
    for i, j in [(1, 17), (9, 20), (15, 16), (22, 27)]:
        sa = _swap(sa, i, j)

    ts = str(timestamp)
    if len(sa) != 30 or len(ts) < 13:
        return sa

    time_idx = 0
    out = []
    for i in range(len(sa)):
        if i == 8 or i == 16:
            out.append(ts[time_idx : time_idx + 5])
            time_idx += 5
        elif i == 22:
            out.append(ts[time_idx : time_idx + 3])
            time_idx += 3
        out.append(sa[i])

    return "".join(out)


def generate_headers_130(
    headers: dict[str, str],
    payload: dict[str, Any],
    rsa_public_key: str,
) -> tuple[dict[str, str], dict[str, Any]]:
    """为 1.3.x 版本生成签名 headers（tn + sa）。"""
    rk = rand_str(16)
    raw_sa = rand_digit_str(30)
    sa = build_sa_header(raw_sa)

    sign_params = {key: str(value) for key, value in payload.items()}
    if headers.get("token"):
        sign_params["token"] = headers["token"]
    sign_params["sa"] = raw_sa

    sign_encoded = xor_encode(sign_shuffled(sign_params, rk), rk)
    tn = f"{rsa_encrypt(rk, rsa_public_key)},{sign_encoded}"

    headers.update({"sa": sa, "tn": tn})
    return headers, payload


class _RsaKeyData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    key: str


_rsa_key_cache: TimedCache = TimedCache(timeout_s=86400, maxsize=1)


class DnaClient(BaseSdkClient):
    BASE_URL = DNA_BASE_URL
    USER_AGENT = DNA_USER_AGENT
    error_cls = DnaError

    def __init__(self, dev_code: str, *, timeout_s: float = BaseSdkClient.timeout_s):
        self.dev_code = dev_code
        self.timeout_s = timeout_s

    def _default_headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.USER_AGENT,
            "version": DNA_APP_VERSION,
            "source": "android",
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            "devCode": self.dev_code,
        }

    def _extract_data(self, payload: dict[str, Any], path: str) -> Any:
        code = payload.get("code")
        if not (payload.get("success") and code in (0, 200, "0", "200")):
            msg = payload.get("msg")
            raise self.error_cls(msg if isinstance(msg, str) and msg else f"[{path}] 请求失败", payload)
        return payload.get("data")

    async def _rsa_public_key(self) -> str:
        cached = _rsa_key_cache.get("rsa_pub")
        if isinstance(cached, str):
            return cached
        # 拿不到 / 返回结构异常时退回内置公钥：登录可用性优先，服务端公钥长期未变
        try:
            data = await self._request("/config/getRsaPublicKey", method="POST")
            key = _RsaKeyData.model_validate(data).key
        except (DnaError, ValidationError) as err:
            logger.warning(f"[DNA-SDK] getRsaPublicKey 失败，使用内置公钥: {err!r}")
            return DNA_FALLBACK_RSA_PUBLIC_KEY
        _rsa_key_cache.set("rsa_pub", key)
        return key

    async def _submit_signed(self, path: str, payload: dict[str, Any]) -> Any:
        rsa_pub = await self._rsa_public_key()
        headers, signed = generate_headers_130(self._default_headers(), payload, rsa_pub)
        return await self._request(path, method="POST", body=signed, headers=headers)

    async def send_sms_code(self, mobile: str, v_json: str) -> None:
        await self._submit_signed(
            "/user/getSmsCode",
            {"isCaptcha": 1, "mobile": mobile, "vJson": v_json},
        )

    async def sdk_login(self, mobile: str, code: str) -> DnaAccount:
        data = await self._submit_signed(
            "/user/sdkLogin",
            {
                "code": code,
                "devCode": self.dev_code,
                "gameList": DNA_GAME_ID,
                "loginType": 1,
                "mobile": mobile,
            },
        )
        try:
            return DnaAccount.model_validate(data)
        except ValidationError as err:
            raise self.error_cls("登录返回缺少必要字段", data if isinstance(data, dict) else None) from err
