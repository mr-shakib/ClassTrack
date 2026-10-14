"""The Android app, for the website's /app page: where to get it.

Until the app is on the Play Store, the API hands out the newest APK in the
downloads directory, so publishing a version is copying a file there. Setting
``CLASSTRACK_ANDROID_PLAY_URL`` sends everyone to the store instead, with no
change here or on the website. Both are public: the page is for people who
have not signed in yet.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from classtrack.core.config import get_settings
from classtrack.core.errors import NotFoundError
from classtrack.schemas.mobile import AndroidAppOut

router = APIRouter(prefix="/app", tags=["app"])

_APK = re.compile(r"^classtrack-(?P<version>[0-9][0-9A-Za-z.+_-]*)\.apk$")


def _newest_apk() -> tuple[Path, str] | None:
    """The most recently placed ``classtrack-<version>.apk``, and its version."""
    folder = Path(get_settings().downloads_dir)
    try:
        found = [
            (path, match["version"])
            for path in folder.iterdir()
            if (match := _APK.match(path.name)) and path.is_file()
        ]
    except OSError:
        return None
    return max(found, key=lambda f: f[0].stat().st_mtime, default=None)


@router.get("/android", response_model=AndroidAppOut, summary="Where to get the Android app")
async def android() -> AndroidAppOut:
    settings = get_settings()
    if settings.android_play_url:
        return AndroidAppOut(available=True, store=True, url=settings.android_play_url)
    apk = _newest_apk()
    if apk is None:
        return AndroidAppOut(available=False)
    path, version = apk
    stat = path.stat()
    return AndroidAppOut(
        available=True,
        url=f"{settings.api_v1_prefix}/app/android/download",
        version=version,
        size_bytes=stat.st_size,
        updated_at=datetime.fromtimestamp(stat.st_mtime, UTC),
    )


@router.get("/android/download", summary="Download the Android app")
async def download() -> FileResponse:
    apk = _newest_apk()
    if apk is None:
        raise NotFoundError("The Android app is not available for download yet.")
    path, version = apk
    return FileResponse(
        path,
        media_type="application/vnd.android.package-archive",
        filename=f"ClassTrack-{version}.apk",
    )
