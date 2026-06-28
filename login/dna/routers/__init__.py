from __future__ import annotations

from fastapi import APIRouter

from . import auth, page, transport_http, transport_sse, transport_ws

router = APIRouter(prefix="/dna", tags=["dna"])
router.include_router(page.router)
router.include_router(auth.router)
router.include_router(transport_http.router)
router.include_router(transport_sse.router)
router.include_router(transport_ws.router)

__all__ = ["router"]
