"""Roles an admin makes and edits: what they grant, who may hand them out, and
the rules that keep anyone from escalating or locking the department out."""

from __future__ import annotations

import pytest

from classtrack.api.deps import ExtraClassUser, require, scope_report_teacher, scope_teacher
from classtrack.core.errors import ForbiddenError, ValidationError
from classtrack.core.security import hash_password
from classtrack.models import BuiltinRole, Permission, RoleKind, User
from classtrack.services import role_service

P = Permission


async def _office_user(session, email: str, *roles) -> User:
    user = User(
        email=email,
        full_name=email.split("@")[0],
        password_hash=hash_password("x"),
        roles=list(roles),
    )
    session.add(user)
    await session.flush()
    return user


async def _admits(user, *permissions) -> bool:
    try:
        await require(*permissions)(user)
    except ForbiddenError:
        return False
    return True


async def test_an_admin_makes_a_role_from_the_permissions_they_pick(session, hod):
    exam = await role_service.create_role(
        session,
        actor=hod,
        name="Exam controller",
        description="Watches the exam weeks.",
        kind=RoleKind.OFFICE,
        permissions=[P.DEPARTMENT_REPORTS.value, P.MANAGE_CALENDAR.value],
    )
    clerk = await _office_user(session, "exam@test.edu")
    await role_service.set_roles(session, actor=hod, target=clerk, roles=[exam])

    assert exam.key == f"CUSTOM_{exam.id}" and not exam.is_builtin
    assert clerk.permissions == {P.DEPARTMENT_REPORTS, P.MANAGE_CALENDAR}
    assert await _admits(clerk, P.DEPARTMENT_REPORTS)
    assert not await _admits(clerk, P.VIEW_DASHBOARD)
    assert scope_report_teacher(clerk, "TCA") == "TCA"


async def test_several_roles_add_up(session, hod, teacher_user):
    committee = await role_service.builtin(session, BuiltinRole.COMMITTEE)
    teacher = await role_service.builtin(session, BuiltinRole.TEACHER)
    await role_service.set_roles(
        session, actor=hod, target=teacher_user, roles=[teacher, committee]
    )

    assert teacher_user.is_teacher
    assert teacher_user.can(P.CORRECT_CHECKS) and teacher_user.can(P.BOOK_EXTRA_CLASSES)
    # A teacher whose other role corrects checks may look at others' classes.
    assert scope_teacher(teacher_user, "OTH") == "OTH"


async def test_a_teacher_alone_sees_only_their_own_classes(teacher_user):
    assert scope_teacher(teacher_user, None) == "TCA"
    with pytest.raises(ForbiddenError):
        scope_teacher(teacher_user, "OTH")


async def test_teacher_roles_belong_to_teacher_accounts_only(session, hod, staff, teacher_user):
    lab = await role_service.create_role(
        session,
        actor=hod,
        name="Lab teacher",
        description="",
        kind=RoleKind.TEACHER,
        permissions=[P.REQUEST_RESCHEDULES.value],
    )
    with pytest.raises(ValidationError, match="teacher role"):
        await role_service.set_roles(session, actor=hod, target=staff, roles=[lab])

    committee = await role_service.builtin(session, BuiltinRole.COMMITTEE)
    with pytest.raises(ValidationError, match="keeps at least one teacher role"):
        await role_service.set_roles(session, actor=hod, target=teacher_user, roles=[committee])

    await role_service.set_roles(session, actor=hod, target=teacher_user, roles=[lab])
    assert teacher_user.is_teacher and not teacher_user.can(P.BOOK_EXTRA_CLASSES)


async def test_an_account_keeps_at_least_one_role(session, hod, staff):
    with pytest.raises(ValidationError, match="at least one role"):
        await role_service.set_roles(session, actor=hod, target=staff, roles=[])


async def test_nobody_hands_out_more_than_they_hold(session, hod, coordinator):
    clerks = await role_service.create_role(
        session,
        actor=hod,
        name="Account clerk",
        description="",
        kind=RoleKind.OFFICE,
        permissions=[P.MANAGE_ACCOUNTS.value, P.MANAGE_ROLES.value],
    )
    clerk = await _office_user(session, "clerk@test.edu", clerks)

    with pytest.raises(ForbiddenError, match="do not have"):
        await role_service.create_role(
            session,
            actor=clerk,
            name="Reports",
            description="",
            kind=RoleKind.OFFICE,
            permissions=[P.DEPARTMENT_REPORTS.value],
        )
    head = await role_service.builtin(session, BuiltinRole.HOD)
    with pytest.raises(ForbiddenError):
        await role_service.set_roles(session, actor=clerk, target=coordinator, roles=[head])
    with pytest.raises(ForbiddenError):
        await role_service.update_role(
            session,
            actor=clerk,
            role_id=clerks.id,
            permissions=[P.MANAGE_ROLES.value, P.VIEW_AUDIT.value],
        )

    # Within what they hold, they may.
    helpers = await role_service.create_role(
        session,
        actor=clerk,
        name="Account helper",
        description="",
        kind=RoleKind.OFFICE,
        permissions=[P.MANAGE_ACCOUNTS.value],
    )
    assert helpers.granted == {P.MANAGE_ACCOUNTS}


async def test_super_admin_always_holds_everything(session, hod):
    sa = await role_service.builtin(session, BuiltinRole.SUPER_ADMIN)
    with pytest.raises(ValidationError, match="every permission"):
        await role_service.update_role(session, actor=hod, role_id=sa.id, permissions=[])
    with pytest.raises(ValidationError, match="built-in"):
        await role_service.delete_role(session, actor=hod, role_id=sa.id)
    sa.permission_values = []  # even tampered with in the database
    assert sa.granted == set(P)


async def test_the_last_super_admin_stays(session, hod):
    sa = await role_service.builtin(session, BuiltinRole.SUPER_ADMIN)
    head = await role_service.builtin(session, BuiltinRole.HOD)
    first = await _office_user(session, "sa1@test.edu", sa)

    with pytest.raises(ValidationError, match="last active Super admin"):
        await role_service.set_roles(session, actor=hod, target=first, roles=[head])
    with pytest.raises(ValidationError, match="last active Super admin"):
        await role_service.guard_deactivation(session, first)

    await _office_user(session, "sa2@test.edu", sa)
    await role_service.set_roles(session, actor=hod, target=first, roles=[head])
    assert not any(r.is_locked for r in first.roles)


async def test_nobody_changes_their_own_roles(session, hod):
    committee = await role_service.builtin(session, BuiltinRole.COMMITTEE)
    with pytest.raises(ValidationError, match="your own roles"):
        await role_service.set_roles(session, actor=hod, target=hod, roles=[committee])


async def test_nobody_takes_away_their_own_right_to_manage_roles(session, hod):
    head = await role_service.builtin(session, BuiltinRole.HOD)
    without = [p.value for p in head.granted if p is not P.MANAGE_ROLES]
    with pytest.raises(ValidationError, match="lose the right to manage roles"):
        await role_service.update_role(session, actor=hod, role_id=head.id, permissions=without)


async def test_editing_a_built_in_role_applies_at_once(session, hod, coordinator):
    officer = await role_service.builtin(session, BuiltinRole.COORDINATION_OFFICER)
    with pytest.raises(ForbiddenError):
        scope_report_teacher(coordinator, "TCA")

    granted = [p.value for p in officer.granted] + [P.DEPARTMENT_REPORTS.value]
    await role_service.update_role(session, actor=hod, role_id=officer.id, permissions=granted)
    assert scope_report_teacher(coordinator, "TCA") == "TCA"


async def test_a_role_is_deleted_only_once_nobody_holds_it(session, hod):
    temp = await role_service.create_role(
        session, actor=hod, name="Temporary", description="", kind=RoleKind.OFFICE, permissions=[]
    )
    holder = await _office_user(session, "temp@test.edu", temp)
    with pytest.raises(ValidationError, match="still hold"):
        await role_service.delete_role(session, actor=hod, role_id=temp.id)

    committee = await role_service.builtin(session, BuiltinRole.COMMITTEE)
    await role_service.set_roles(session, actor=hod, target=holder, roles=[committee])
    await session.flush()
    await role_service.delete_role(session, actor=hod, role_id=temp.id)
    await session.flush()
    assert temp.id not in {r.id for r in await role_service.all_roles(session)}


async def test_role_names_are_unique(session, hod):
    with pytest.raises(ValidationError, match="already a role called"):
        await role_service.create_role(
            session,
            actor=hod,
            name="head of department",
            description="",
            kind=RoleKind.OFFICE,
            permissions=[],
        )


async def test_alerts_follow_the_permission(session, hod, coordinator):
    alerted = {u.id for u in await role_service.users_who_can(session, P.RECEIVE_ALERTS)}
    assert hod.id in alerted and coordinator.id not in alerted

    watch = await role_service.create_role(
        session,
        actor=hod,
        name="Watch",
        description="",
        kind=RoleKind.OFFICE,
        permissions=[P.RECEIVE_ALERTS.value],
    )
    officer = await role_service.builtin(session, BuiltinRole.COORDINATION_OFFICER)
    await role_service.set_roles(session, actor=hod, target=coordinator, roles=[officer, watch])
    await session.flush()
    alerted = {u.id for u in await role_service.users_who_can(session, P.RECEIVE_ALERTS)}
    assert coordinator.id in alerted


async def test_switching_a_teacher_feature_off_closes_it(session, hod, teacher_user):
    guard = ExtraClassUser.__metadata__[0].dependency
    assert await guard(teacher_user) is teacher_user

    teacher = await role_service.builtin(session, BuiltinRole.TEACHER)
    await role_service.update_role(
        session, actor=hod, role_id=teacher.id, permissions=[P.REQUEST_RESCHEDULES.value]
    )
    with pytest.raises(ForbiddenError):
        await guard(teacher_user)


async def test_an_unknown_permission_is_refused(session, hod):
    with pytest.raises(ValidationError, match="not a permission"):
        await role_service.create_role(
            session,
            actor=hod,
            name="Typo",
            description="",
            kind=RoleKind.OFFICE,
            permissions=["reports.al"],
        )
