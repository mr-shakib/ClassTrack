"""The website's /app page offers the newest APK, or the Play Store once it is there.

Both endpoints are public: the page is for people who have not signed in yet.
"""

from __future__ import annotations

import os

import httpx
import pytest

from classtrack.core.config import get_settings
from classtrack.main import app


@pytest.fixture
def downloads(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "downloads_dir", str(tmp_path))
    monkeypatch.setattr(get_settings(), "android_play_url", None)
    return tmp_path


async def _get(path: str) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.get(f"/api/v1/app{path}")


def _place(folder, name: str, content: bytes, mtime: int):
    path = folder / name
    path.write_bytes(content)
    os.utime(path, (mtime, mtime))
    return path


async def test_nothing_to_offer_yet(downloads):
    response = await _get("/android")

    assert response.status_code == 200
    assert response.json()["available"] is False
    assert (await _get("/android/download")).status_code == 404


async def test_a_missing_folder_offers_nothing(downloads, monkeypatch):
    monkeypatch.setattr(get_settings(), "downloads_dir", str(downloads / "absent"))

    assert (await _get("/android")).json()["available"] is False


async def test_the_newest_apk_is_offered_with_its_version_and_size(downloads):
    _place(downloads, "classtrack-1.0.0.apk", b"old", 1_700_000_000)
    _place(downloads, "classtrack-1.1.0.apk", b"newer!", 1_800_000_000)
    _place(downloads, "notes.txt", b"ignored", 1_900_000_000)

    info = (await _get("/android")).json()

    assert info["available"] is True
    assert info["store"] is False
    assert info["url"] == "/api/v1/app/android/download"
    assert (info["version"], info["size_bytes"]) == ("1.1.0", 6)
    assert info["updated_at"].startswith("2027-01-15")


async def test_the_download_is_the_apk_named_for_its_version(downloads):
    _place(downloads, "classtrack-1.1.0.apk", b"PK-apk-bytes", 1_800_000_000)

    response = await _get("/android/download")

    assert response.status_code == 200
    assert response.content == b"PK-apk-bytes"
    assert response.headers["content-type"] == "application/vnd.android.package-archive"
    assert 'filename="ClassTrack-1.1.0.apk"' in response.headers["content-disposition"]


async def test_the_play_store_link_takes_over_once_set(downloads, monkeypatch):
    _place(downloads, "classtrack-1.1.0.apk", b"apk", 1_800_000_000)
    store = "https://play.google.com/store/apps/details?id=com.bitstreamhq.classtrack"
    monkeypatch.setattr(get_settings(), "android_play_url", store)

    info = (await _get("/android")).json()

    assert (info["available"], info["store"], info["url"]) == (True, True, store)
    assert info["version"] is None
