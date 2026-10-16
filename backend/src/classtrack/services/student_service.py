"""Students: their routine, what changes in it, and the rooms free to use.

Students have no accounts. A student names the groups they sit in and reads
the classes and notices of those groups; their phone follows the groups' push
topics. A group is a *token*, in four shapes (``models/student.py``):

* ``*`` everyone, ``63`` an intake, ``63_A`` a section or ``63_A1`` its lab
  group, and ``CSE447:RE_A`` a retake group, which names its course because
  every course numbers its retake groups from A.

A lab group is a part of its section, so a student of ``63_A1`` sits in the
section's ``63_A`` classes too: :func:`expand` adds the section.

**What a student sees of a class** is what the timetable on the wall would say,
and nothing monitoring learned about the teacher: it is on, it is cancelled, it
moved to another time, or it is a makeup or an extra class. Whether the teacher
came, came late, or was reported absent never leaves this module, and neither
does any check record.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date as Date
from datetime import timedelta
from math import ceil

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from classtrack.core.errors import ForbiddenError, NotFoundError, ValidationError
from classtrack.models import (
    ClassInstance,
    ClassSession,
    ClassStatus,
    Holiday,
    MakeupClass,
    NoticeKind,
    Routine,
    Semester,
    StudentNotice,
    StudentNoticeTarget,
    Teacher,
    User,
)
from classtrack.routine.audience import bare_course, is_retake
from classtrack.routine.cell_parser import split_section
from classtrack.routine.lattice import SLOTS
from classtrack.services import (
    audit_service,
    conflict_service,
    push_service,
    reschedule_links,
    status_engine,
)

EVERYONE = "*"

#: The most groups one student can name, and the most dates one request reads.
MAX_GROUPS = 16
MAX_DAYS = 42

_SECTION = re.compile(r"^\d+_[A-Z]\d*$")
_INTAKE = re.compile(r"^\d{1,3}$")
_RETAKE = re.compile(r"^([A-Z0-9]{2,12}):(RE_[A-Z]\d*)$")
#: What Firebase accepts in a topic name.
_TOPIC_SAFE = re.compile(r"[^A-Za-z0-9\-_.~%]")

#: A makeup students are told of: in a room, or online and approved. One still
#: waiting for the HoD may not happen, so it is not news yet.
_HAPPENING = {"SCHEDULED", "APPROVED", "COMPLETED"}


# --- groups ---------------------------------------------------------------------


def parse_groups(raw: str | Iterable[str] | None, *, allow_wide: bool = False) -> list[str]:
    """The tokens of a request, upper-cased and in order. A malformed one is refused.

    ``allow_wide`` admits everyone and whole intakes, which only an admin
    writes to; a student names the groups they sit in.
    """
    parts = raw.split(",") if isinstance(raw, str) else list(raw or [])
    tokens: list[str] = []
    for part in parts:
        token = part.strip().upper()
        if not token or token in tokens:
            continue
        if token == EVERYONE or _INTAKE.match(token):
            if not allow_wide:
                raise ValidationError(f"{token!r} is not a section.")
        elif token.startswith("RE_"):
            raise ValidationError(
                f"A retake group belongs to its course: write it as COURSE:{token}, "
                f"e.g. CSE447:{token}."
            )
        elif not (_SECTION.match(token) or _RETAKE.match(token)):
            raise ValidationError(f"{token!r} is not a section, lab group or retake group.")
        tokens.append(token)
    if len(tokens) > MAX_GROUPS:
        raise ValidationError(f"At most {MAX_GROUPS} groups at once.")
    return tokens


def class_token(course_code: str, section: str) -> str:
    """The group a class is held for: its section, or its course's retake group."""
    if is_retake(section):
        return f"{bare_course(course_code)}:{section.upper()}"
    return section.upper()


def _parent(token: str) -> str | None:
    """A lab group's section: ``63_A1`` -> ``63_A``, ``CSE447:RE_A1`` -> ``CSE447:RE_A``."""
    course, _, section = token.rpartition(":")
    if not section or token == EVERYONE or _INTAKE.match(token):
        return None
    batch, lab = split_section(section)
    if lab is None:
        return None
    return f"{course}:{batch}" if course else batch


def expand(groups: Iterable[str]) -> list[str]:
    """The groups whose classes a student sits in: each named one, and the
    section of each lab group named."""
    out: list[str] = []
    for token in groups:
        for t in (token, _parent(token)):
            if t and t not in out:
                out.append(t)
    return out


def intake_of(token: str) -> str | None:
    """``63_A1`` -> ``63``. A retake group is drawn from several intakes: None."""
    match = re.match(r"^(\d+)_", token)
    return match.group(1) if match else None


def feed_tokens(groups: Iterable[str]) -> list[str]:
    """Every group whose notices reach a student of ``groups``."""
    classes = expand(groups)
    intakes = [i for i in dict.fromkeys(intake_of(t) for t in classes) if i]
    return [EVERYONE, *intakes, *classes]


def collapse(targets: Iterable[str]) -> list[str]:
    """Drop a target another one already covers: a lab group beside its section,
    a section beside its intake, anything beside everyone."""
    wanted = list(dict.fromkeys(targets))
    if EVERYONE in wanted:
        return [EVERYONE]

    def covered(t: str) -> bool:
        parent = _parent(t)
        intake = intake_of(t)
        return (parent is not None and parent in wanted) or (
            intake is not None and intake != t and intake in wanted
        )

    return [t for t in wanted if not covered(t)]


async def department(session: AsyncSession) -> str:
    """The department whose students these are: the current semester's."""
    dept = await session.scalar(select(Semester.department).where(Semester.is_active))
    return (dept or "cse").lower()


def topic(dept: str, token: str, *, reminder: bool = False) -> str:
    """The push topic a group's phones follow: ``cse.63_A``, ``cse.rem.63_A``."""
    name = "all" if token == EVERYONE else token.replace(":", "-")
    return _TOPIC_SAFE.sub("", f"{dept}.{'rem.' if reminder else ''}{name}")


def topics_for(dept: str, groups: Iterable[str]) -> dict[str, list[str]]:
    """What a student's phone follows: notices to any of their groups, and the
    reminders before each of their classes."""
    groups = list(groups)
    return {
        "alerts": [topic(dept, t) for t in feed_tokens(groups)],
        "reminders": [topic(dept, t, reminder=True) for t in expand(groups)],
    }


# --- the directory -------------------------------------------------------------


async def _routine(session: AsyncSession) -> Routine | None:
    return await session.scalar(select(Routine).where(Routine.is_active))


async def directory(session: AsyncSession) -> dict[str, object]:
    """Every group of the routine in force, to pick one's own from."""
    semester = await session.scalar(select(Semester).where(Semester.is_active))
    routine = await _routine(session)
    sections: dict[str, set[str]] = {}
    retakes: dict[str, dict[str, object]] = {}
    if routine is not None:
        rows = (
            await session.execute(
                select(ClassSession.course_code, ClassSession.course_title, ClassSession.section)
                .where(ClassSession.routine_id == routine.id)
                .distinct()
            )
        ).all()
        for course_code, title, section in rows:
            section = section.upper()
            batch, lab = split_section(section)
            if is_retake(section):
                course = bare_course(course_code)
                entry = retakes.setdefault(course, {"title": title, "groups": {}})
                if title and not entry["title"]:
                    entry["title"] = title
                labs = entry["groups"].setdefault(batch, set())  # type: ignore[union-attr]
                if lab is not None:
                    labs.add(section)
            elif _SECTION.match(section):
                labs = sections.setdefault(batch, set())
                if lab is not None:
                    labs.add(section)

    def order(section: str) -> tuple[int, str]:
        intake = intake_of(section)
        return (int(intake) if intake else 0, section)

    return {
        "department": (semester.department if semester else "cse").upper(),
        "semester": semester.name if semester else None,
        "sections": [
            {"section": s, "intake": intake_of(s) or "", "lab_groups": sorted(sections[s])}
            for s in sorted(sections, key=order)
        ],
        "retakes": [
            {
                "course_code": course,
                "course_title": entry["title"],
                "groups": [
                    {
                        "token": f"{course}:{batch}",
                        "section": batch,
                        "lab_groups": [
                            {"token": f"{course}:{lab}", "section": lab} for lab in sorted(labs)
                        ],
                    }
                    for batch, labs in sorted(entry["groups"].items())  # type: ignore[union-attr]
                ],
            }
            for course, entry in sorted(retakes.items())
        ],
    }


async def known_tokens(session: AsyncSession) -> set[str]:
    """Every group a notice may be written to."""
    found = await directory(session)
    known = {EVERYONE}
    for s in found["sections"]:  # type: ignore[union-attr]
        known.add(s["section"])
        known.update(s["lab_groups"])
        if s["intake"]:
            known.add(s["intake"])
    for r in found["retakes"]:  # type: ignore[union-attr]
        for g in r["groups"]:
            known.add(g["token"])
            known.update(lab["token"] for lab in g["lab_groups"])
    return known


# --- classes ----------------------------------------------------------------------


def _online(inst: ClassInstance) -> bool:
    return inst.room == "ONLINE"


def _state(inst: ClassInstance, moved_to: dict | None) -> str:
    if inst.status is ClassStatus.CANCELLED:
        return "CANCELLED"
    if not inst.is_makeup and moved_to is not None and moved_to.get("status") in _HAPPENING:
        return "MOVED"
    return "SCHEDULED"


async def _teachers(session: AsyncSession, initials: set[str]) -> dict[str, Teacher]:
    if not initials:
        return {}
    rows = await session.scalars(select(Teacher).where(Teacher.initial.in_(initials)))
    return {t.initial: t for t in rows}


def teacher_card(initial: str, teacher: Teacher | None) -> dict[str, str | None]:
    """Who teaches it, from the faculty directory: never their contact address."""
    return {
        "initial": initial,
        "name": teacher.name if teacher else None,
        "designation": teacher.designation if teacher else None,
        "office_room": teacher.office_room if teacher else None,
        "photo_url": teacher.image_url if teacher else None,
    }


async def classes(
    session: AsyncSession, groups: list[str], *, date_from: Date, date_to: Date
) -> list[dict[str, object]]:
    """The classes of ``groups`` between two dates, both inclusive, as students see them."""
    if date_to < date_from:
        raise ValidationError("The end date is before the start date.")
    if (date_to - date_from).days >= MAX_DAYS:
        raise ValidationError(f"At most {MAX_DAYS} days at once.")
    tokens = expand(groups)
    plain = [t for t in tokens if ":" not in t]
    retakes = {tuple(t.split(":", 1)) for t in tokens if ":" in t}
    sections = plain + sorted({s for _course, s in retakes})
    if not sections:
        return []

    rows = (
        await session.scalars(
            select(ClassInstance)
            .where(
                ClassInstance.date >= date_from,
                ClassInstance.date <= date_to,
                ClassInstance.section.in_(sections),
            )
            .order_by(ClassInstance.date, ClassInstance.start_min, ClassInstance.course_code)
        )
    ).all()
    # A retake section is only a group within its course.
    instances = [
        i
        for i in rows
        if not is_retake(i.section) or (bare_course(i.course_code), i.section.upper()) in retakes
    ]
    return await _describe(session, instances)


async def _describe(
    session: AsyncSession, instances: list[ClassInstance]
) -> list[dict[str, object]]:
    moved_from, moved_to = await reschedule_links.links_for(session, instances)
    makeup_ids = {i.makeup_id for i in instances if i.is_makeup and i.makeup_id}
    links = (
        {
            m.id: m.meeting_link
            for m in await session.scalars(
                select(MakeupClass).where(MakeupClass.id.in_(makeup_ids))
            )
        }
        if makeup_ids
        else {}
    )
    teachers = await _teachers(session, {i.teacher_initial for i in instances})
    notes = await _notes_on(session, [i.id for i in instances])

    out = []
    for inst in instances:
        to = moved_to.get(inst.id)
        state = _state(inst, to)
        source = moved_from.get(inst.id)
        note = notes.get(inst.id)
        out.append(
            {
                "id": inst.id,
                "date": inst.date,
                "day": inst.day,
                "time_slot": inst.time_slot,
                "start_min": inst.start_min,
                "end_min": inst.end_min,
                "room": None if _online(inst) else inst.room,
                "room_type": inst.room_type,
                "online": _online(inst),
                "course_code": bare_course(inst.course_code),
                "course_title": inst.course_title,
                "section": inst.section,
                "kind": "MAKEUP" if inst.is_makeup else "EXTRA" if inst.is_extra else "CLASS",
                "state": state,
                "moved_to": (
                    {
                        "date": to["date"],
                        "time_slot": to["time_slot"],
                        "room": to["room"],
                        "online": to.get("mode") == "ONLINE",
                    }
                    if state == "MOVED" and to is not None
                    else None
                ),
                "makeup_for": (
                    {"date": source["date"], "time_slot": source["time_slot"]}
                    if inst.is_makeup and source is not None
                    else None
                ),
                "join_link": links.get(inst.makeup_id) if inst.is_makeup else None,
                "teacher": teacher_card(inst.teacher_initial, teachers.get(inst.teacher_initial)),
                "note": (
                    {"body": note.body, "author": note.author, "created_at": note.created_at}
                    if note is not None
                    else None
                ),
            }
        )
    return out


async def _notes_on(session: AsyncSession, instance_ids: list[int]) -> dict[int, StudentNotice]:
    """The latest note a teacher wrote about each of these classes."""
    if not instance_ids:
        return {}
    rows = await session.scalars(
        select(StudentNotice)
        .where(
            StudentNotice.instance_id.in_(instance_ids),
            StudentNotice.kind == NoticeKind.TEACHER,
        )
        .order_by(StudentNotice.id)
    )
    # Ordered by id, so a later note on the same class wins.
    return {n.instance_id: n for n in rows if n.instance_id is not None}


# --- notices --------------------------------------------------------------------


async def notices(
    session: AsyncSession, groups: list[str], *, limit: int = 50
) -> list[StudentNotice]:
    """What was written to any of a student's groups, newest first."""
    ids = (
        select(StudentNoticeTarget.notice_id)
        .where(StudentNoticeTarget.token.in_(feed_tokens(groups)))
        .distinct()
    )
    rows = await session.scalars(
        select(StudentNotice)
        .where(StudentNotice.id.in_(ids))
        .order_by(StudentNotice.id.desc())
        .limit(limit)
    )
    return list(rows)


async def describe_notices(
    session: AsyncSession, rows: list[StudentNotice]
) -> list[dict[str, object]]:
    """Each notice, with the class it is about as students see it."""
    about = {
        i.id: i
        for i in (
            await session.scalars(
                select(ClassInstance).where(
                    ClassInstance.id.in_({n.instance_id for n in rows if n.instance_id})
                )
            )
        ).all()
    }
    classes_by_id = {c["id"]: c for c in await _describe(session, list(about.values()))}
    return [
        {
            "id": n.id,
            "kind": n.kind.value,
            "title": n.title,
            "body": n.body,
            "author": n.author,
            "created_at": n.created_at,
            "targets": n.tokens,
            "about": classes_by_id.get(n.instance_id) if n.instance_id else None,
        }
        for n in rows
    ]


async def post(
    session: AsyncSession,
    *,
    kind: NoticeKind,
    title: str,
    body: str,
    author: str,
    targets: Iterable[str],
    author_id: int | None = None,
    instance: ClassInstance | None = None,
) -> StudentNotice:
    """Keep a notice for its groups and push it to their phones once committed."""
    wanted = collapse(targets)
    if not wanted:
        raise ValidationError("Choose who it is for.")
    notice = StudentNotice(
        kind=kind,
        title=title[:160],
        body=body,
        author=author,
        author_id=author_id,
        instance_id=instance.id if instance is not None else None,
        targets=[StudentNoticeTarget(token=t) for t in wanted],
    )
    session.add(notice)
    await session.flush()

    dept = await department(session)
    link = "/students"
    if instance is not None:
        link = f"/students?date={instance.date.isoformat()}"
    # Up to five topics share one message, so a phone that follows two of them
    # (a section, and one of its lab groups) is told once.
    names = [topic(dept, t) for t in wanted]
    for start in range(0, len(names), 5):
        push_service.queue(
            session,
            push_service.TopicPush(
                topics=tuple(names[start : start + 5]),
                title=title,
                body=body,
                kind=push_service.STUDENT_NOTICE,
                link=link,
            ),
        )
    return notice


# --- what changed, told to the section --------------------------------------------


def _clock(minutes: int) -> str:
    return f"{minutes // 60 % 24:02d}:{minutes % 60:02d}"


def _period(start_min: int, end_min: int) -> str:
    """ "13:00-14:30" with an en dash: the 24-hour clock, as nobody misreads it."""
    return f"{_clock(start_min)}\u2013{_clock(end_min)}"


def _when(on: Date, start_min: int, end_min: int) -> str:
    """ "Sunday 13 Oct, 13:00-14:30"."""
    return f"{on:%A} {on.day} {on:%b}, {_period(start_min, end_min)}"


def _where(inst: ClassInstance) -> str:
    return "online" if _online(inst) else f"in room {inst.room}"


async def _change(session: AsyncSession, inst: ClassInstance, *, title: str, body: str) -> None:
    await post(
        session,
        kind=NoticeKind.CHANGE,
        title=title,
        body=body,
        author="ClassTrack",
        targets=[class_token(inst.course_code, inst.section)],
        instance=inst,
    )


async def announce_makeup(
    session: AsyncSession, makeup: MakeupClass, original: ClassInstance, instance: ClassInstance
) -> None:
    """A makeup is on: booked in a room, or online and approved."""
    course = bare_course(instance.course_code)
    online = _online(instance)
    body = (
        f"{_when(instance.date, instance.start_min, instance.end_min)}, {_where(instance)}. "
        f"It makes up the class of {original.date:%A} {original.date.day} {original.date:%b}."
    )
    if online:
        body += (
            " The join link is in ClassTrack."
            if makeup.meeting_link
            else " Your teacher will share how to join."
        )
    await _change(
        session,
        instance,
        title=f"{course} · {'Online makeup' if online else 'Makeup class'}",
        body=body,
    )


async def announce_extra(session: AsyncSession, instance: ClassInstance) -> None:
    course = bare_course(instance.course_code)
    await _change(
        session,
        instance,
        title=f"{course} · Extra class",
        body=f"{_when(instance.date, instance.start_min, instance.end_min)}, {_where(instance)}.",
    )


async def announce_cancelled(session: AsyncSession, instance: ClassInstance) -> None:
    """A class is off. Only one still to come is news: a past one is history."""
    if instance.date < status_engine.now_local().date():
        return
    course = bare_course(instance.course_code)
    kind = "Extra class" if instance.is_extra else "Makeup class" if instance.is_makeup else "Class"
    await _change(
        session,
        instance,
        title=f"{course} · {kind} cancelled",
        body=f"{_when(instance.date, instance.start_min, instance.end_min)} will not be held.",
    )


async def announce_meeting_link(session: AsyncSession, instance: ClassInstance) -> None:
    course = bare_course(instance.course_code)
    await _change(
        session,
        instance,
        title=f"{course} · Join link for the online class",
        body=(
            f"{_when(instance.date, instance.start_min, instance.end_min)}. "
            "Open the class in ClassTrack to join."
        ),
    )


def remind(dept: str, instance: ClassInstance, *, starts_in: timedelta) -> push_service.TopicPush:
    """The push to a class's students shortly before it starts."""
    minutes = max(1, ceil(starts_in.total_seconds() / 60))
    course = bare_course(instance.course_code)
    kind = "Extra class" if instance.is_extra else "Makeup class" if instance.is_makeup else None
    where = "Online · open ClassTrack to join" if _online(instance) else f"Room {instance.room}"
    return push_service.TopicPush(
        topics=(topic(dept, class_token(instance.course_code, instance.section), reminder=True),),
        title=f"{course} starts in {minutes} minute{'s' if minutes != 1 else ''}",
        body=" · ".join(
            p for p in (kind, where, _period(instance.start_min, instance.end_min)) if p
        ),
        kind=push_service.STUDENT_REMINDER,
        link=f"/students?date={instance.date.isoformat()}",
        ttl_seconds=int(starts_in.total_seconds()),
    )


# --- written by people ---------------------------------------------------------------


async def teacher_groups(session: AsyncSession, initial: str) -> list[dict[str, str]]:
    """The groups a teacher may write to: each course-section they teach."""
    routine = await _routine(session)
    if routine is None:
        return []
    rows = (
        await session.execute(
            select(ClassSession.course_code, ClassSession.course_title, ClassSession.section)
            .where(ClassSession.routine_id == routine.id, ClassSession.teacher == initial)
            .distinct()
        )
    ).all()
    seen: dict[str, dict[str, str]] = {}
    for course_code, title, section in rows:
        token = class_token(course_code, section)
        seen.setdefault(
            token,
            {
                "token": token,
                "course_code": bare_course(course_code),
                "course_title": title or "",
                "section": section.upper(),
            },
        )
    return sorted(seen.values(), key=lambda g: (g["course_code"], g["section"]))


async def write_as_teacher(
    session: AsyncSession,
    *,
    user: User,
    body: str,
    targets: list[str] | None = None,
    instance_id: int | None = None,
) -> StudentNotice:
    """A teacher writes to their own students: about one class (a heads-up), or
    to whichever of their sections they choose."""
    initial = user.teacher_initial
    if not initial:
        raise ForbiddenError("Only a teacher may write to their students.")
    teacher = await session.scalar(select(Teacher).where(Teacher.initial == initial))
    author = f"{teacher.name if teacher else user.full_name} ({initial})"
    instance = None

    if instance_id is not None:
        instance = await session.get(ClassInstance, instance_id)
        if instance is None:
            raise NotFoundError(f"No class with id {instance_id}")
        if instance.teacher_initial != initial:
            raise ForbiddenError("You may only write about your own classes.")
        ends = status_engine.slot_end_at(instance.date, instance.end_min)
        if status_engine.now_local() >= ends:
            raise ValidationError("That class is over.")
        wanted = [class_token(instance.course_code, instance.section)]
        title = (
            f"{bare_course(instance.course_code)} · "
            f"{_when(instance.date, instance.start_min, instance.end_min)}"
        )
    else:
        mine = {g["token"]: g for g in await teacher_groups(session, initial)}
        wanted = parse_groups(targets or [])
        if not wanted:
            raise ValidationError("Choose which of your sections it is for.")
        others = [t for t in wanted if t not in mine]
        if others:
            raise ForbiddenError(
                f"You do not teach {', '.join(others)} this semester.",
                detail={"not_yours": others},
            )
        courses = sorted({mine[t]["course_code"] for t in wanted})
        title = f"{courses[0] if len(courses) == 1 else 'Your classes'} · Note from {initial}"

    notice = await post(
        session,
        kind=NoticeKind.TEACHER,
        title=title,
        body=body,
        author=author,
        author_id=user.id,
        targets=wanted,
        instance=instance,
    )
    audit_service.record(
        session,
        actor_id=user.id,
        entity_type="student_notice",
        entity_id=notice.id,
        action="student_notice_sent",
        after={"targets": notice.tokens, "body": body, "instance_id": instance_id},
    )
    return notice


async def write_as_admin(
    session: AsyncSession, *, user: User, title: str, body: str, targets: list[str]
) -> StudentNotice:
    """The department writes to students: everyone, intakes, or chosen groups."""
    wanted = parse_groups(targets, allow_wide=True)
    if not wanted:
        raise ValidationError("Choose who it is for.")
    unknown = [t for t in wanted if t not in await known_tokens(session)]
    if unknown:
        raise ValidationError(
            f"No such group in the routine: {', '.join(unknown)}.", detail={"unknown": unknown}
        )
    dept = await department(session)
    notice = await post(
        session,
        kind=NoticeKind.ANNOUNCEMENT,
        title=title,
        body=body,
        author=f"Department of {dept.upper()}",
        author_id=user.id,
        targets=wanted,
    )
    audit_service.record(
        session,
        actor_id=user.id,
        entity_type="student_notice",
        entity_id=notice.id,
        action="student_notice_sent",
        after={"targets": notice.tokens, "title": title, "body": body},
    )
    return notice


async def written_by(
    session: AsyncSession, *, kind: NoticeKind, author_id: int | None = None, limit: int = 20
) -> list[StudentNotice]:
    """What was sent, newest first: a teacher's own, or every admin's."""
    query = select(StudentNotice).where(StudentNotice.kind == kind)
    if author_id is not None:
        query = query.where(StudentNotice.author_id == author_id)
    return list(await session.scalars(query.order_by(StudentNotice.id.desc()).limit(limit)))


# --- rooms and the calendar -----------------------------------------------------------


async def free_rooms(session: AsyncSession, *, on: Date) -> list[dict[str, object]]:
    """Each slot of a day and the rooms with nothing in them then.

    A day with no classes at all -- the weekend, a holiday -- says nothing about
    which rooms are open, so it has no slots.
    """
    held = await session.scalar(select(ClassInstance.id).where(ClassInstance.date == on).limit(1))
    if held is None:
        return []
    return [
        {
            "time_slot": slot,
            "rooms": await conflict_service.free_rooms(session, on=on, time_slot=slot),
        }
        for slot in SLOTS
    ]


async def calendar(session: AsyncSession) -> dict[str, object] | None:
    """The semester: its dates, its exams, and the days with no classes."""
    semester = await session.scalar(select(Semester).where(Semester.is_active))
    if semester is None:
        return None
    holidays = (
        await session.scalars(
            select(Holiday).where(Holiday.semester_id == semester.id).order_by(Holiday.date)
        )
    ).all()
    exams = []
    if semester.mid_exam_start and semester.mid_exam_end:
        exams.append(
            {
                "name": "Mid-term exams",
                "start": semester.mid_exam_start,
                "end": semester.mid_exam_end,
            }
        )
    if semester.final_exam_start:
        exams.append(
            {"name": "Final exams", "start": semester.final_exam_start, "end": semester.end_date}
        )
    return {
        "name": semester.name,
        "start_date": semester.start_date,
        "end_date": semester.end_date,
        "exams": exams,
        "holidays": [{"date": h.date, "title": h.title, "kind": h.kind.value} for h in holidays],
    }
