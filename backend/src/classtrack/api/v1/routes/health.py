from __future__ import annotations

from fastapi import APIRouter

from classtrack.core.config import get_settings

router = APIRouter(tags=["meta"])


@router.get("/health", summary="Liveness probe")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": get_settings().project_name}
