from __future__ import annotations

from fastapi import APIRouter

from classtrack.api.v1.routes import (
    admin,
    auth,
    checking,
    health,
    instances,
    makeup,
    notifications,
    reports,
)

api_router = APIRouter()
for module in (health, auth, checking, instances, makeup, reports, notifications, admin):
    api_router.include_router(module.router)
