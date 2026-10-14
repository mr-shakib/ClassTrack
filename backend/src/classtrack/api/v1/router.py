from __future__ import annotations

from fastapi import APIRouter

from classtrack.api.v1.routes import (
    admin,
    announcements,
    auth,
    checking,
    extra_classes,
    health,
    instances,
    makeup,
    notifications,
    reports,
)

api_router = APIRouter()
for module in (
    health,
    auth,
    checking,
    instances,
    makeup,
    extra_classes,
    reports,
    notifications,
    admin,
    announcements,
):
    api_router.include_router(module.router)
