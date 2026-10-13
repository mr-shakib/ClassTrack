"""A teacher's classes between two dates, for the app's coming week."""

from __future__ import annotations

from datetime import timedelta

import httpx

from classtrack.api.deps import get_current_user
from classtrack.db.session import get_session
from classtrack.main import app
from classtrack.models import ClassInstance


async def _dates(session, user, query: str) -> list[str]:
    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/instances{query}")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200, response.text
    return [row["date"] for row in response.json()]


async def test_from_and_to_bound_the_dates_inclusively(session, instance, teacher_user):
    # The fixture's class is on 13 Sep; add the same class each week after it.
    for weeks in (1, 2, 3):
        session.add(
            ClassInstance(
                session_id=instance.session_id,
                semester_id=instance.semester_id,
                date=instance.date + timedelta(weeks=weeks),
                day=instance.day,
                time_slot=instance.time_slot,
                start_min=instance.start_min,
                end_min=instance.end_min,
                room=instance.room,
                course_code=instance.course_code,
                section=instance.section,
                batch=instance.batch,
                teacher_initial=instance.teacher_initial,
            )
        )
    await session.flush()

    assert await _dates(session, teacher_user, "?from=2026-09-20&to=2026-09-27") == [
        "2026-09-20",
        "2026-09-27",
    ]
    assert await _dates(session, teacher_user, "?from=2026-09-21") == ["2026-09-27", "2026-10-04"]
    assert len(await _dates(session, teacher_user, "")) == 4
