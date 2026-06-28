from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, ClassVar

import httpx

from .logger import logger

_proxy_provider: Callable[[], str] | None = None


def set_proxy_provider(fn: Callable[[], str] | None) -> None:
    """注入函数返回代理 URL；返回空字符串等同直连。"""
    global _proxy_provider
    _proxy_provider = fn


class SdkError(RuntimeError):
    def __init__(self, message: str, raw: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.raw = raw


class BaseSdkClient:
    BASE_URL: ClassVar[str] = ""
    USER_AGENT: ClassVar[str] = ""
    error_cls: ClassVar[type[SdkError]] = SdkError
    timeout_s: float = 20.0

    def _default_headers(self) -> dict[str, str]:
        return {"User-Agent": self.USER_AGENT}

    def _finalize_headers(
        self,
        path: str,
        *,
        method: str,
        body: dict[str, Any] | None,
        query: dict[str, Any] | None,
        headers: dict[str, str],
    ) -> dict[str, str]:
        return headers

    def _extract_data(self, payload: dict[str, Any], path: str) -> Any:
        if payload.get("code") not in (0, "0"):
            raise self.error_cls(f"[{path}] {payload.get('msg', '')}", payload)
        return payload["data"] if "data" in payload and payload["data"] is not None else {}

    async def _request(
        self,
        path: str,
        *,
        method: str = "GET",
        body: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        merged = dict(self._default_headers())
        if headers is not None:
            merged.update(headers)
        if body is not None:
            merged.setdefault("Content-Type", "application/x-www-form-urlencoded")
        merged = self._finalize_headers(
            path,
            method=method,
            body=body,
            query=query,
            headers=merged,
        )

        tag = self.__class__.__name__
        logger.debug(f"[NTE-SDK] → {tag} {method} {self.BASE_URL}{path} query={query} body={body}")

        proxy: str | None = None
        if _proxy_provider:
            candidate = _proxy_provider()
            if candidate:
                proxy = candidate
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s, proxy=proxy, trust_env=False) as client:
                resp = await client.request(
                    method,
                    f"{self.BASE_URL}{path}",
                    headers=merged,
                    params=query,
                    data=body,
                )
        except httpx.HTTPError as err:
            logger.debug(f"[NTE-SDK] ✗ {tag} {method} {path} 网络错误: {err!r}")
            raise self.error_cls(f"[{path}] 网络请求失败") from err

        logger.debug(f"[NTE-SDK] ← {tag} {method} {path} HTTP={resp.status_code} body={resp.text}")

        if resp.status_code >= 400:
            raise self.error_cls(
                f"[{path}] HTTP {resp.status_code}",
                {"status_code": resp.status_code, "text": resp.text},
            )
        if not resp.content:
            raise self.error_cls(f"[{path}] 响应为空", {"status_code": resp.status_code})

        try:
            payload = resp.json()
        except json.JSONDecodeError:
            return resp.text
        return self._extract_data(payload, path) if isinstance(payload, dict) else payload
