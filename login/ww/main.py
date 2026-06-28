# Standard library imports
import random
import string

# Third-party imports
from pathlib import Path
from fastapi import APIRouter
from jinja2 import Environment, FileSystemLoader
from starlette.responses import HTMLResponse

# Local imports
from . import lcache
from .kuro_api import kuro_login
from .models import AuthModel, LoginModel, TokenModel

cache = lcache.TimedCache(600, 1000)


_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
waves_router = APIRouter(prefix="/waves", tags=["waves"])
templates = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)))


@waves_router.post("/token", response_model=TokenModel, status_code=200)
async def generate_token(auth: AuthModel):
    _token = "".join(
        random.choice(string.ascii_letters + string.digits) for _ in range(8)
    )
    cache.set(_token, LoginModel(**auth.dict()))
    return {"token": _token}


@waves_router.get("/i/{token}", response_class=HTMLResponse)
async def verify_html(token: str):
    m = cache.get(token)
    template_name = "index.html" if m else "404.html"
    template = templates.get_template(template_name)
    return HTMLResponse(
        template.render(auth=token, userId=m.user_id) if m else template.render()
    )


@waves_router.post("/login")
async def waves_login(data: LoginModel):
    temp = cache.get(data.auth)
    if temp is None:
        return {"success": False, "msg": "登录超时"}
    ck, did = await kuro_login(data.mobile, data.code)
    if not ck:
        return {"success": False, "msg": "验证码无效"}
    data.ck = ck
    data.did = did
    cache.set(data.auth, data)
    return {"success": True}


@waves_router.post("/get", response_model=LoginModel, status_code=200)
async def waves_get_login(_token: TokenModel):
    temp = cache.get(_token.token, LoginModel())

    if temp and temp.ck:
        cache.delete(_token.token)

    return temp

@waves_router.get("/done", response_class=HTMLResponse)
async def login_done() -> HTMLResponse:
    return HTMLResponse(templates.get_template("done.html").render())
