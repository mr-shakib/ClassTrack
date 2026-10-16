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
    mobile_app,
    notifications,
    reports,
    students,
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
    mobile_app,
    students,
):
    api_router.include_router(module.router)
