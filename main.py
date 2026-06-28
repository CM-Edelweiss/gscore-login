from __future__ import annotations

import os
import uvicorn
from fastapi import FastAPI
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from fastapi.responses import FileResponse, HTMLResponse

from login.ww.main import waves_router
from login.dna.main import dna_router
from login.nte.main import nte_router
from login_env import settings
from login.utils.logger import logger, setup_logging

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
templates = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)))


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    logger.success(f"gscore-login 启动，监听 http://{settings.host}:{settings.port}")
    if not settings.shared_secret:
        logger.warning("SHARED_SECRET 未设置，跨服务调用不会校验签名")
    yield
    logger.success("gscore-login 关闭")


setup_logging(settings.log_level)
app = FastAPI(lifespan=lifespan)


@app.get("/")
async def index():
    login_list = ''
    if "ww" in settings.login_list:
        login_list = "XutheringWavesUID"
    if "dna" in settings.login_list:
        login_list += "、DNAUID"
    if "nte" in settings.login_list:
        login_list += "、NTEUID"
    if settings.shared_secret:
        shared_secret = settings.shared_secret
    else:
        shared_secret = "未设置"
    return HTMLResponse(templates.get_template("index.html").render(login_list=login_list, shared_secret=shared_secret))


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(str(_TEMPLATE_DIR / "favicon.ico"))


if "ww" in settings.login_list:
    app.include_router(waves_router)
    logger.info("ww 登录服务已启用")
if "dna" in settings.login_list:
    app.include_router(dna_router)
    logger.info("dna 登录服务已启用")
if "nte" in settings.login_list:
    app.include_router(nte_router)
    logger.info("nte 登录服务未已启用")


def main():
    port = int(os.getenv("PORT", settings.port))
    uvicorn.run(app, host=settings.host, port=port, log_config=None)


if __name__ == "__main__":
    main()
