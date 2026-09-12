"""Parse one routine cell into its parts.

A populated cell fuses the course and its audience into one token, with the
teacher's initial alongside::

    CSE322(66_B1)   AAM

The grammar is wider than it first looks. Every shape below appears in the
published Summer-2026 routine:

===========================  ==========================================
``CSE315(66_E)``             theory class for section 66_E
``CSE322(66_B1)``            lab subsection 1 of section 66_B
``CSE213(RE_A(3C))``         retake section A, 3 credits
``CSE124(RE_A1(1.5C))``      retake section A, lab subsection 1, 1.5 credits
``CSE311(RE_B)``             retake section B, no credit annotation
``CSE323(RE_A(3C.))``        stray full stop in the credit
``CSE324(RE_A1(2C)``         unbalanced -- a typo in the source document
===========================  ==========================================

``course_code`` is kept fused. ``batch`` and ``section`` are derived *alongside*
it, never by destroying the original token.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: A course token: 2-5 letters, then 3 digits, optionally spaced.
COURSE_RE = re.compile(r"^([A-Z]{2,5})\s?(\d{3}[A-Z]?)")

#: A section, with optional lab subsection. Retakes use ``RE_`` in place of a
#: batch number, so both forms are accepted.
SECTION_RE = re.compile(r"^(\d+_[A-Z]|RE_[A-Z])(\d+)?$", re.IGNORECASE)

#: A teacher initial. Mostly plain letters, but the source also carries
#: disambiguating suffixes such as ``NT_2``, ``MNT_2`` and ``NT-1``.
INITIAL_RE = re.compile(r"^[A-Z]{1,6}(?:[_-]\d{1,2})?$")

#: Cells that deliberately hold something other than a class. A room marked
#: "Reserved" is held for something outside the routine; that is information,
#: not a parse failure, so it is reported separately.
NON_CLASS = {"reserved", "-", "--", "n/a", "x", ""}

#: A course cell whose opening bracket is missing: "CSE47164_P)" should read
#: "CSE471(64_P)". One such typo exists in the Summer-2026 document. Course
#: codes are always three digits, so the split is unambiguous.
MISSING_BRACKET_RE = re.compile(r"^([A-Z]{2,5}\d{3})(\d+_[A-Z]\d?)\)?$")

#: Elective courses carried a "T" prefix in earlier routines (TCSE412). The
#: Summer-2026 routine has none, but the convention is cheap to keep.
OPTIONAL_PREFIX = "TCSE"

#: Reserved sentinel for an unassigned teacher.
TBA = "TBA"


@dataclass(frozen=True, slots=True)
class ParsedCell:
    """The structured content of one populated routine cell."""

    course_code: str  #: fused source token, e.g. "CSE322(66_B1)"
    batch: str  #: "66_B", or "RE_A" for a retake
    section: str  #: "66_B1"
    teacher: str  #: "AAM", or "TBA"
    is_lab: bool  #: the section carries a subsection suffix
    is_optional: bool  #: elective course
    is_retake: bool  #: a repeat section rather than a numbered batch
    credit: str | None = None  #: "3C", "1.5C" -- present on retakes only


def split_section(section: str) -> tuple[str, str | None]:
    """Split a section into ``(batch, subsection)``.

    ``"66_B1" -> ("66_B", "1")``, ``"RE_A1" -> ("RE_A", "1")``, and a section
    with no subsection returns ``(section, None)``. An unrecognised shape is
    returned unchanged rather than raising, so an unfamiliar naming scheme
    degrades instead of losing the class.
    """
    cleaned = section.strip()
    match = SECTION_RE.match(cleaned)
    if not match:
        return cleaned.upper(), None
    return match.group(1).upper(), match.group(2)


def is_non_class(text: str) -> bool:
    """Whether a cell deliberately holds no class (blank, "Reserved", a dash)."""
    flat = " ".join((text or "").replace("\xa0", " ").split()).lower()
    return flat in NON_CLASS or flat.startswith("reserved")


def split_course_token(text: str) -> tuple[str, str, str | None] | None:
    """Split a course cell into ``(code, section, credit)``.

    Takes everything between the *first* ``(`` and the *last* ``)``, so nested
    annotations like ``RE_A(3C)`` survive. A missing closing bracket -- which
    occurs in the published document -- is tolerated.
    """
    flat = " ".join(text.replace("\xa0", " ").split())

    if recovered := MISSING_BRACKET_RE.match(flat):
        return recovered.group(1).upper(), recovered.group(2).upper(), None

    course = COURSE_RE.match(flat)
    if not course:
        return None
    code = f"{course.group(1)}{course.group(2)}".upper()

    open_at = flat.find("(")
    if open_at == -1:
        return code, "", None

    close_at = flat.rfind(")")
    inner = flat[open_at + 1 : close_at] if close_at > open_at else flat[open_at + 1 :]
    inner = inner.strip().rstrip(")")

    # A nested bracket separates the section from its credit annotation.
    nested = inner.find("(")
    if nested != -1:
        return (
            code,
            inner[:nested].strip().upper(),
            inner[nested + 1 :].replace(" ", "").strip(" )").upper(),
        )
    return code, inner.upper(), None


def parse_cell(course_text: str, teacher_text: str = "") -> ParsedCell | None:
    """Parse a course cell and its teacher cell, or ``None`` if it holds no class."""
    if not course_text:
        return None
    if is_non_class(course_text):
        return None
    flat = " ".join(course_text.replace("\xa0", " ").split())

    split = split_course_token(flat)
    if split is None:
        return None
    code, section, credit = split

    batch, subsection = split_section(section) if section else ("", None)
    if not batch:
        # A course with no section cannot be attributed to anyone, so it is not
        # a usable class record.
        return None

    return ParsedCell(
        course_code=f"{code}({section})" if section else code,
        batch=batch,
        section=section.upper() or batch,
        teacher=normalise_teacher(teacher_text),
        is_lab=subsection is not None,
        is_optional=code.startswith(OPTIONAL_PREFIX),
        is_retake=batch.upper().startswith("RE_"),
        credit=credit,
    )


def normalise_teacher(text: str) -> str:
    """Clean a teacher cell down to an initial, or ``TBA``."""
    flat = " ".join((text or "").replace("\xa0", " ").split()).strip(".:,-").upper()
    if not flat or flat == "RESERVED":
        return TBA
    # Occasionally two initials share a cell; the first is the class teacher.
    first = flat.split()[0].strip(".:,")
    return first if INITIAL_RE.match(first) else (flat if len(flat) <= 12 else TBA)
