"""Who may do what with the built-in roles as they start. The route guards are
the security boundary, so they are exercised directly rather than trusted to
the frontend's navigation."""

from __future__ import annotations

import pytest
from tests.conftest import at

from classtrack.api.deps import require, scope_report_teacher
from classtrack.core.errors import ForbiddenError
from classtrack.models import ALL_PERMISSIONS, CheckOutcome, ClassStatus, Permission
from classtrack.services import check_service


async def _admits(user, *permissions: Permission) -> bool:
    try:
        await require(*permissions)(user)
    except ForbiddenError:
        return False
    return True


async def test_head_and_associate_head_hold_every_permission(hod, associate_head):
    for user in (hod, associate_head):
        assert user.permissions == ALL_PERMISSIONS
        assert await _admits(user, Permission.DEPARTMENT_REPORTS)
        assert await _admits(user, Permission.MANAGE_ROLES)


async def test_coordination_officer_manages_but_is_not_an_admin(coordinator):
    for granted in (
        Permission.VIEW_DASHBOARD,
        Permission.CHECK_CLASSES,
        Permission.MANAGE_ROUTINE,
        Permission.MANAGE_CALENDAR,
        Permission.MANAGE_STAFF,
        Permission.VIEW_AUDIT,
    ):
        assert await _admits(coordinator, granted)
    # Reports, the approval queue, accounts and semesters stay with the admins.
    for withheld in (
        Permission.DEPARTMENT_REPORTS,
        Permission.DECIDE_RESCHEDULES,
        Permission.MANAGE_ACCOUNTS,
        Permission.MANAGE_SEMESTERS,
        Permission.MANAGE_ROLES,
    ):
        assert not await _admits(coordinator, withheld)
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
        assert not await _admits(user, Permission.VIEW_DASHBOARD)
        with pytest.raises(ForbiddenError):
            scope_report_teacher(user, "TCA")
    assert await _admits(committee, Permission.CORRECT_CHECKS)
    assert not await _admits(staff, Permission.CORRECT_CHECKS)


async def test_a_teacher_reads_only_their_own_report(teacher_user):
    assert teacher_user.is_teacher
    assert scope_report_teacher(teacher_user, None) == "TCA"
    with pytest.raises(ForbiddenError):
        scope_report_teacher(teacher_user, "OTH")
