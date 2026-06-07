"""Aggregates all v1 API routers into a single APIRouter."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.servers import router as servers_router

router = APIRouter(prefix="/api/v1")

router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(health_router, prefix="/servers", tags=["servers"])
router.include_router(servers_router, prefix="/servers", tags=["servers"])
