"""Where to get the mobile app."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AndroidAppOut(BaseModel):
    available: bool
    #: True when ``url`` is the Play Store page rather than a download.
    store: bool = False
    url: str | None = None
    version: str | None = None
    size_bytes: int | None = None
    updated_at: datetime | None = None
