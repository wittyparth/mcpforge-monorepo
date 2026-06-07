"""Aggregates all v1 API routers into a single APIRouter.

Wave 0 Skeleton contract: this file is the single source of truth for
which routers are mounted. Feature agents (F1, F2, F4, F5, F6, F7) do
NOT add to this file — they only fill in the bodies of the route stubs
that already exist here.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints.analytics import router as analytics_router
from app.api.v1.endpoints.api_keys import router as api_keys_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.billing import router as billing_router
from app.api.v1.endpoints.build import router as build_router
from app.api.v1.endpoints.credentials import router as credentials_router
from app.api.v1.endpoints.gateway_admin import router as gateway_admin_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.security import router as security_router
from app.api.v1.endpoints.servers import router as servers_router
from app.api.v1.endpoints.specs import router as specs_router
from app.api.v1.endpoints.team import router as team_router
from app.api.v1.endpoints.tools import router as tools_router

router = APIRouter(prefix="/api/v1")

# Phase 1 — ships today
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(servers_router, prefix="/servers", tags=["servers"])
router.include_router(health_router, prefix="/servers", tags=["servers"])

# Wave 0 Skeleton — F1, F2, F4, F5, F6, F7 stubs (return 501 until implemented)
router.include_router(specs_router, tags=["specs"])
router.include_router(tools_router, tags=["tools"])
router.include_router(credentials_router, tags=["credentials"])
router.include_router(build_router, tags=["build"])
router.include_router(security_router, tags=["security"])
router.include_router(analytics_router, tags=["analytics"])
router.include_router(team_router, tags=["team"])
router.include_router(api_keys_router, tags=["api-keys"])
router.include_router(billing_router, tags=["billing"])
router.include_router(gateway_admin_router, tags=["gateway"])
