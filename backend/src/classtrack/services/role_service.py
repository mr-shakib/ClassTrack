"""Roles: creating them, changing what they permit, and giving them to people.

Three rules hold whatever the request:

* **No escalation.** You may only give a role, or add a permission to one, if
  you hold every permission involved yourself. Managing accounts or roles
  cannot be turned into more access than the manager has.
* **No lockout.** Super admin always holds every permission, cannot be
  deleted, and its last active holder keeps it and stays active.
* **Kind matches the account.** A teacher account (one with a faculty initial)
  always holds a teacher-kind role, and only teacher accounts hold them.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from classtrack.core.errors import ForbiddenError, NotFoundError, ValidationError
from classtrack.models import (
    BUILTIN_ROLES,
    BuiltinRole,
    Permission,
    Role,
    RoleKind,
    User,
    user_role,
)
from classtrack.services import audit_service


async def ensure_builtin_roles(session: AsyncSession) -> dict[str, Role]:
    """Create any built-in role that is missing, with its starting permissions.

    The migration makes them on an existing install; this covers a database
    built from the models, as the tests and a fresh ``create_all`` are.
    """
    have = {r.key: r for r in (await session.scalars(select(Role))).all()}
    for key, (name, kind, description, granted) in BUILTIN_ROLES.items():
        if key.value in have:
            continue
        role = Role(
            key=key.value,
            name=name,
            kind=kind,
            description=description,
            is_builtin=True,
            permission_values=sorted(p.value for p in granted),
        )
        session.add(role)
        have[key.value] = role
    await session.flush()
    return have


async def builtin(session: AsyncSession, key: BuiltinRole) -> Role:
    role = await session.scalar(select(Role).where(Role.key == key.value))
    if role is None:
        role = (await ensure_builtin_roles(session))[key.value]
    return role


async def all_roles(session: AsyncSession) -> list[Role]:
    return list((await session.scalars(select(Role).order_by(Role.id))).all())


async def holders(session: AsyncSession) -> dict[int, int]:
    """How many accounts hold each role, by role id."""
    rows = await session.execute(
        select(user_role.c.role_id, func.count()).group_by(user_role.c.role_id)
    )
    return dict(rows.all())


async def users_who_can(session: AsyncSession, permission: Permission) -> list[User]:
    """Active accounts holding a role that grants ``permission``."""
    role_ids = [r.id for r in await all_roles(session) if permission in r.granted]
    if not role_ids:
        return []
    query = (
        select(User)
        .join(user_role, user_role.c.user_id == User.id)
        .where(user_role.c.role_id.in_(role_ids), User.is_active.is_(True))
        .distinct()
    )
    return list((await session.scalars(query)).all())


def _permissions(values: Iterable[str]) -> list[Permission]:
    known = {p.value: p for p in Permission}
    out: list[Permission] = []
    for value in values:
        if value not in known:
            raise ValidationError(f"{value!r} is not a permission.")
        if known[value] not in out:
            out.append(known[value])
    return out


def _require_held(actor: User, permissions: Iterable[Permission], what: str) -> None:
    missing = sorted(p.value for p in permissions if p not in actor.permissions)
    if missing:
        raise ForbiddenError(
            f"You cannot {what}: it grants permissions you do not have yourself.",
            detail={"missing": missing},
        )


def require_held(actor: User, role: Role, what: str) -> None:
    """The no-escalation rule, for giving someone ``role``."""
    _require_held(actor, role.granted, what)


def _clean_name(name: str) -> str:
    name = re.sub(r"\s+", " ", name).strip()
    if not 2 <= len(name) <= 64:
        raise ValidationError("A role's name is 2 to 64 characters.")
    return name


async def _name_taken(session: AsyncSession, name: str, *, other_than: int | None = None) -> bool:
    query = select(Role.id).where(func.lower(Role.name) == name.lower())
    if other_than is not None:
        query = query.where(Role.id != other_than)
    return await session.scalar(query) is not None


async def create_role(
    session: AsyncSession,
    *,
    actor: User,
    name: str,
    description: str,
    kind: RoleKind,
    permissions: Iterable[str],
) -> Role:
    name = _clean_name(name)
    if await _name_taken(session, name):
        raise ValidationError(f"There is already a role called {name}.")
    granted = _permissions(permissions)
    _require_held(actor, granted, "create this role")

    role = Role(
        # Settled once the row has an id; the key only has to be unique.
        key=f"PENDING_{uuid4().hex}",
        name=name,
        description=description.strip(),
        kind=kind,
        is_builtin=False,
        permission_values=sorted(p.value for p in granted),
    )
    session.add(role)
    await session.flush()
    role.key = f"CUSTOM_{role.id}"
    audit_service.record(
        session,
        actor_id=actor.id,
        entity_type="role",
        entity_id=role.id,
        action="role_created",
        after={"name": name, "kind": kind.value, "permissions": role.permission_values},
    )
    return role


async def update_role(
    session: AsyncSession,
    *,
    actor: User,
    role_id: int,
    name: str | None = None,
    description: str | None = None,
    permissions: Iterable[str] | None = None,
) -> Role:
    role = await session.get(Role, role_id)
    if role is None:
        raise NotFoundError(f"No role with id {role_id}")

    before = {"name": role.name, "permissions": list(role.permission_values)}
    if name is not None:
        name = _clean_name(name)
        if await _name_taken(session, name, other_than=role.id):
            raise ValidationError(f"There is already a role called {name}.")
        role.name = name
    if description is not None:
        role.description = description.strip()
    if permissions is not None:
        if role.is_locked:
            raise ValidationError(f"{role.name} always has every permission.")
        new = set(_permissions(permissions))
        old = set(role.granted)
        # Adding or taking away, it is a change to what others may do.
        _require_held(actor, new ^ old, "change these permissions")
        if role in actor.roles and Permission.MANAGE_ROLES in old - new:
            raise ValidationError(
                "You would lose the right to manage roles. Ask another admin to change it."
            )
        role.permission_values = sorted(p.value for p in new)

    audit_service.record(
        session,
        actor_id=actor.id,
        entity_type="role",
        entity_id=role.id,
        action="role_updated",
        before=before,
        after={"name": role.name, "permissions": list(role.permission_values)},
    )
    return role


async def delete_role(session: AsyncSession, *, actor: User, role_id: int) -> None:
    role = await session.get(Role, role_id)
    if role is None:
        raise NotFoundError(f"No role with id {role_id}")
    if role.is_builtin:
        raise ValidationError(f"{role.name} is a built-in role and cannot be deleted.")
    held = (await holders(session)).get(role.id, 0)
    if held:
        raise ValidationError(
            f"{held} account{'s' if held != 1 else ''} still hold{'s' if held == 1 else ''} "
            f"{role.name}. Give them another role first."
        )
    _require_held(actor, role.granted, "delete this role")
    audit_service.record(
        session,
        actor_id=actor.id,
        entity_type="role",
        entity_id=role.id,
        action="role_deleted",
        before={"name": role.name, "permissions": list(role.permission_values)},
    )
    await session.delete(role)


async def _active_super_admins(session: AsyncSession) -> int:
    count = await session.scalar(
        select(func.count(User.id))
        .join(user_role, user_role.c.user_id == User.id)
        .join(Role, Role.id == user_role.c.role_id)
        .where(Role.key == BuiltinRole.SUPER_ADMIN.value, User.is_active.is_(True))
    )
    return count or 0


async def guard_deactivation(session: AsyncSession, target: User) -> None:
    """Refuse to deactivate the last active Super admin."""
    if any(r.is_locked for r in target.roles) and await _active_super_admins(session) <= 1:
        raise ValidationError(
            "This is the last active Super admin. Give the role to someone else first."
        )


def check_kinds(target: User, roles: list[Role]) -> None:
    """A teacher account holds a teacher-kind role; nobody else does."""
    if not roles:
        raise ValidationError("An account needs at least one role.")
    teacher_roles = [r for r in roles if r.kind is RoleKind.TEACHER]
    if target.teacher_initial and not teacher_roles:
        raise ValidationError("A teacher account keeps at least one teacher role.")
    if teacher_roles and not target.teacher_initial:
        names = ", ".join(r.name for r in teacher_roles)
        raise ValidationError(
            f"{names} is a teacher role. Teacher accounts are made from the Teachers tab."
        )


async def resolve(session: AsyncSession, role_ids: Iterable[int]) -> list[Role]:
    ids = list(dict.fromkeys(role_ids))
    found = {r.id: r for r in (await session.scalars(select(Role).where(Role.id.in_(ids)))).all()}
    missing = [i for i in ids if i not in found]
    if missing:
        raise NotFoundError(f"No role with id {missing[0]}")
    return [found[i] for i in ids]


async def set_roles(session: AsyncSession, *, actor: User, target: User, roles: list[Role]) -> None:
    """Replace the roles an account holds."""
    if target.id == actor.id:
        raise ValidationError("You cannot change your own roles. Ask another admin.")
    check_kinds(target, roles)

    old = {r.id: r for r in target.roles}
    new = {r.id: r for r in roles}
    changed = [r for rid, r in {**old, **new}.items() if (rid in old) != (rid in new)]
    for role in changed:
        _require_held(actor, role.granted, f"give or take {role.name}")

    losing_super = any(r.is_locked for r in old.values()) and not any(
        r.is_locked for r in new.values()
    )
    if losing_super and target.is_active and await _active_super_admins(session) <= 1:
        raise ValidationError(
            "This is the last active Super admin. Give the role to someone else first."
        )

    target.roles = roles
    audit_service.record(
        session,
        actor_id=actor.id,
        entity_type="user",
        entity_id=target.id,
        action="roles_changed",
        before={"roles": sorted(r.name for r in old.values())},
        after={"roles": sorted(r.name for r in roles)},
    )
