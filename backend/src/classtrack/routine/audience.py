"""Who sits in a class, as far as the routine can tell.

Two classes at the same time clash when some student would have to be in both.
The routine names its students by section, in three shapes:

* ``66_B`` -- section B of batch 66, the whole of it, as for a theory class.
* ``66_B1`` -- lab group 1 of that section, a part of ``66_B``. Groups 1 and 2
  are different students, so their labs may run side by side, but neither may
  run beside the section's own theory class.
* ``RE_A`` / ``RE_A1`` -- retake group A of one course, and its lab group.
  Every course with a retake numbers its groups from A, so ``CSE447(RE_A)``
  and ``CSE491(RE_A)`` are different students: a retake group is the course
  and the section together.

Retake students are drawn from several batches, and the routine does not say
which. Whether a retake shares students with any other class -- a regular
section, or another course's retake -- cannot be known, so
:func:`share_students` does not claim it, and a caller warns instead.
"""

from __future__ import annotations

from classtrack.routine.cell_parser import split_section


def bare_course(course_code: str) -> str:
    """``"CSE447(RE_A)"`` -> ``"CSE447"``. The stored code keeps its section."""
    return course_code.split("(", 1)[0].strip().upper()


def is_retake(section: str | None) -> bool:
    return bool(section) and section.strip().upper().startswith("RE_")


def _group(course_code: str, section: str) -> tuple[str, str, str | None]:
    """``(course, batch, lab group)``; the course matters only to a retake."""
    batch, lab_group = split_section(section)
    return (bare_course(course_code) if is_retake(section) else ""), batch, lab_group


def share_students(a_course: str, a_section: str, b_course: str, b_section: str) -> bool:
    """Whether the routine says some student sits in both classes."""
    if not a_section or not b_section:
        return False
    a_course_key, a_batch, a_lab = _group(a_course, a_section)
    b_course_key, b_batch, b_lab = _group(b_course, b_section)
    if (a_course_key, a_batch) != (b_course_key, b_batch):
        return False
    # The whole section includes every lab group; two lab groups are apart.
    return a_lab is None or b_lab is None or a_lab == b_lab
