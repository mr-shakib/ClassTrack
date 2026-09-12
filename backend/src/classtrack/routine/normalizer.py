"""Clean values lifted straight out of the routine PDF's table cells.

Cell text arrives with the artifacts of its origin. The app we studied never
stripped them: its published room list contains keys like ``"KT-503\\n  (COM
LAB)"`` -- an embedded newline surviving into a dictionary key. We normalise at
ingestion so every downstream comparison is on clean data.
"""

from __future__ import annotations

import re

ROOM_TYPE_THEORY = "Theory"
ROOM_TYPE_COMPUTER_LAB = "Computer Lab"
ROOM_TYPE_PHYSICS_LAB = "Physics Lab"
ROOM_TYPE_ELECTRICAL_LAB = "Electrical Lab"
ROOM_TYPE_LAB = "Lab"

#: Annotations the published routine appends under a room name, longest first so
#: a specific match wins over the generic "LAB".
_ROOM_TYPE_MARKERS: tuple[tuple[str, str], ...] = (
    ("COMPUTER LAB", ROOM_TYPE_COMPUTER_LAB),
    ("COM LAB", ROOM_TYPE_COMPUTER_LAB),
    ("PHYSICS LAB", ROOM_TYPE_PHYSICS_LAB),
    ("ELECTRICAL", ROOM_TYPE_ELECTRICAL_LAB),
    ("LAB", ROOM_TYPE_LAB),
)


def normalise_whitespace(value: str) -> str:
    """Collapse newlines, non-breaking spaces and runs of whitespace."""
    if not value:
        return ""
    return " ".join(value.replace("\xa0", " ").split())


def normalise_room(raw: str) -> tuple[str, str]:
    """Split a room cell into ``(room, room_type)``.

    The published PDF puts a room's type on a second line inside the same cell,
    so ``"KT-503\\n(COM LAB)"`` arrives as one string. Splitting it here means
    every downstream comparison runs on a clean room name -- the app we studied
    never does this, and ships room keys with the newline still embedded.

    ``"G1-020\\n(Physics Lab)"`` becomes ``("G1-020", "Physics Lab")``.
    """
    if not raw:
        return "", ROOM_TYPE_THEORY

    # The name is the first line; anything below it annotates the room.
    lines = [ln.strip() for ln in str(raw).replace("\xa0", " ").splitlines() if ln.strip()]
    if not lines:
        return "", ROOM_TYPE_THEORY

    name = normalise_whitespace(lines[0]).upper()
    annotation = " ".join(lines[1:]).upper()

    # Some cells append the annotation inline rather than wrapping it, but a
    # room legitimately named "KT-517(A)" must not lose its suffix -- so only
    # split when the bracketed part actually names a room type.
    if not annotation and "(" in name:
        head, _, tail = name.partition("(")
        if any(marker in tail for marker, _type in _ROOM_TYPE_MARKERS):
            name, annotation = head.strip(), tail

    room_type = ROOM_TYPE_THEORY
    for marker, resolved in _ROOM_TYPE_MARKERS:
        if marker in annotation:
            room_type = resolved
            break

    return name.strip(" -"), room_type


def normalise_initial(raw: str) -> str:
    """Uppercase a teacher initial and strip surrounding punctuation."""
    return normalise_whitespace(raw).strip(".:-()").upper()


#: Faculty directory names embed the initial: "Dr. Sheak Rashed Haider Noori (SRH)".
_NAME_INITIAL_RE = re.compile(r"^(.*?)\s*\(([A-Z]{2,5})\)\s*$")


def split_name_initial(raw: str) -> tuple[str, str | None]:
    """Split ``"Full Name (INI)"`` into ``("Full Name", "INI")``.

    Returns ``(name, None)`` when no initial is present, so a malformed
    directory entry is kept rather than dropped.
    """
    flat = normalise_whitespace(raw)
    match = _NAME_INITIAL_RE.match(flat)
    if not match:
        return flat, None
    return match.group(1).strip(), match.group(2).upper()
