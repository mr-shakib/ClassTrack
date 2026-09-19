"""Who may do what. The route guards are the security boundary, so they are
exercised directly rather than trusted to the frontend's navigation."""

from __future__ import annotations

import pytest
from tests.conftest import at

from classtrack.api.deps import require_role, scope_report_teacher
from classtrack.core.errors import ForbiddenError
from classtrack.models import (
    ADMIN_ROLES,
    CHECKING_ROLES,
    MANAGEMENT_ROLES,
    CheckOutcome,
    ClassStatus,
)
from classtrack.services import check_service


async def _admits(roles, user) -> bool:
    try:
        await require_role(*roles)(user)
    except ForbiddenError:
        return False
    return True


async def test_head_and_associate_head_hold_full_admin(hod, associate_head):
    for user in (hod, associate_head):
        assert await _admits(ADMIN_ROLES, user)
        assert await _admits(MANAGEMENT_ROLES, user)


async def test_coordination_officer_manages_but_is_not_an_admin(coordinator):
    assert await _admits(MANAGEMENT_ROLES, coordinator)
    assert await _admits(CHECKING_ROLES, coordinator)
    # Reports and the approval queue are both admin-only.
    assert not await _admits(ADMIN_ROLES, coordinator)
    with pytest.raises(ForbiddenError):
        scope_report_teacher(coordinator, "TCA")


async def test_coordination_officer_can_correct_a_past_class(session, instance, coordinator):
    checked = await check_service.submit(
        session,
        instance_id=instance.id,
        user=coordinator,
        outcome=CheckOutcome.RUNNING,
        now=at(9, 0, day=instance.date.replace(day=15)),
    )
    assert checked.status is ClassStatus.RUNNING


async def test_committee_and_staff_see_no_reports(committee, staff):
    for user in (committee, staff):
        assert not await _admits(MANAGEMENT_ROLES, user)
        with pytest.raises(ForbiddenError):
            scope_report_teacher(user, "TCA")


async def test_a_teacher_reads_only_their_own_report(teacher_user):
    assert scope_report_teacher(teacher_user, None) == "TCA"
    with pytest.raises(ForbiddenError):
        scope_report_teacher(teacher_user, "OTH")
