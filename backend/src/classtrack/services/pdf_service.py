"""Printable reports: one teacher's classes, and a department summary.

Both render from the same dictionaries the JSON endpoints return, so a PDF can
never disagree with the screen it was downloaded from.
"""

from __future__ import annotations

from datetime import date as Date
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from classtrack.services import report_service, status_engine

# The web palette, so a printed report reads like the screen.
INK = colors.HexColor("#0f172a")
INK_SOFT = colors.HexColor("#475569")
LINE = colors.HexColor("#e2e8f0")
CANVAS = colors.HexColor("#f6f8fb")
BAD = colors.HexColor("#b91c1c")
BAD_SOFT = colors.HexColor("#fef2f2")

#: Text colour and row tint per outcome. Missed and Not checked stay different
#: hues: one is the teacher's absence, the other a staff gap.
OUTCOME_STYLE = {
    report_service.CONDUCTED: (colors.HexColor("#047857"), None),
    report_service.LATE: (colors.HexColor("#b45309"), colors.HexColor("#fffbeb")),
    report_service.MISSED: (BAD, BAD_SOFT),
    report_service.NOT_CHECKED: (colors.HexColor("#6d28d9"), colors.HexColor("#f5f3ff")),
    report_service.RESCHEDULED: (colors.HexColor("#0e7490"), colors.HexColor("#ecfeff")),
    report_service.CANCELLED: (INK_SOFT, None),
    report_service.PENDING: (INK_SOFT, None),
}

_styles = getSampleStyleSheet()
TITLE = ParagraphStyle("Title", parent=_styles["Title"], fontSize=17, leading=21,
                       alignment=0, textColor=INK, spaceAfter=2)
SUB = ParagraphStyle("Sub", parent=_styles["Normal"], fontSize=9.5, leading=12,
                     textColor=INK_SOFT)
H2 = ParagraphStyle("H2", parent=_styles["Heading2"], fontSize=12, leading=15,
                    textColor=INK, spaceBefore=10, spaceAfter=5)
CELL = ParagraphStyle("Cell", parent=_styles["Normal"], fontSize=8, leading=10, textColor=INK)
CELL_SMALL = ParagraphStyle("CellSmall", parent=CELL, fontSize=7.2, leading=9,
                            textColor=INK_SOFT)
NOTE = ParagraphStyle("Note", parent=SUB, fontSize=8.5, leading=11)
RIGHT = ParagraphStyle("Right", parent=SUB, alignment=TA_RIGHT)


def _d(value: Date | str) -> str:
    if isinstance(value, str):
        value = Date.fromisoformat(value)
    return value.strftime("%d %b %Y")


def _short(value: Date | str) -> str:
    if isinstance(value, str):
        value = Date.fromisoformat(value)
    return value.strftime("%d %b")


def _header_block(title: str, subtitle: str, range_: dict) -> list:
    generated = status_engine.now_local().strftime("%d %b %Y, %H:%M")
    head = Table(
        [
            [
                Paragraph(
                    "<b>Daffodil International University</b> · Department of CSE", SUB
                ),
                Paragraph(f"Generated {generated}", RIGHT),
            ]
        ],
        colWidths=["65%", "35%"],
    )
    head.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    return [
        head,
        Spacer(1, 4),
        Paragraph(title, TITLE),
        Paragraph(f"{subtitle} · {_d(range_['from'])} to {_d(range_['to'])}", SUB),
        Spacer(1, 8),
    ]


def _kpis(items: list[tuple[str, object, colors.Color | None]]) -> Table:
    """A strip of labelled figures."""
    labels = [Paragraph(label.upper(), CELL_SMALL) for label, _v, _c in items]
    values = [
        Paragraph(
            f'<font size="14" color="{(c or INK).hexval()}"><b>{v}</b></font>', CELL
        )
        for _label, v, c in items
    ]
    table = Table([labels, values], colWidths=[None] * len(items))
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), CANVAS),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.white),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def _grid(data: list[list], widths: list, *, extra: list | None = None) -> Table:
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("TEXTCOLOR", (0, 0), (-1, 0), INK_SOFT),
                ("BACKGROUND", (0, 0), (-1, 0), CANVAS),
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK_SOFT),
                ("LINEBELOW", (0, 1), (-1, -1), 0.3, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                *(extra or []),
            ]
        )
    )
    return table


def _footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(INK_SOFT)
    canvas.drawString(doc.leftMargin, 8 * mm, "ClassTrack · class monitoring report")
    canvas.drawRightString(
        doc.pagesize[0] - doc.rightMargin, 8 * mm, f"Page {canvas.getPageNumber()}"
    )
    canvas.restoreState()


def _build(story: list, *, wide: bool = True) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4) if wide else A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=11 * mm,
        bottomMargin=14 * mm,
        title="ClassTrack report",
        author="ClassTrack",
    )
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()


def _course_table(courses: list[dict], *, with_teacher: bool) -> Table:
    head = ["Course", "Section", "Held", "Late", "Missed", "Not checked",
            "Rescheduled", "Makeups held", "Total"]
    if with_teacher:
        head = ["Teacher", *head]
    data: list[list] = [head]
    extra = []
    for i, c in enumerate(courses, start=1):
        row = [
            Paragraph(f"<b>{c['course_code']}</b>", CELL),
            c["section"],
            c["held"],
            c["late"],
            c["missed"],
            c["not_checked"],
            c["rescheduled"],
            c["makeup_held"],
            c["total"],
        ]
        if with_teacher:
            row = [c["teacher_initial"], *row]
        data.append(row)
        if c["below_minimum"]:
            held_col = 3 if with_teacher else 2
            extra += [
                ("BACKGROUND", (0, i), (-1, i), BAD_SOFT),
                ("TEXTCOLOR", (held_col, i), (held_col, i), BAD),
                ("FONTNAME", (held_col, i), (held_col, i), "Helvetica-Bold"),
            ]
    widths = [None] * len(head)
    return _grid(data, widths, extra=extra)


def _slot_ref(ref: dict | None) -> str:
    if not ref:
        return ""
    where = "Online" if ref.get("mode") == "ONLINE" else ref.get("room") or ""
    return f"{_short(ref['date'])} {ref['time_slot']} {where}".strip()


def _class_note(c: dict) -> str:
    notes = []
    if c.get("rescheduled_from"):
        notes.append(f"<b>Makeup</b> for the class of {_slot_ref(c['rescheduled_from'])}")
    if c.get("rescheduled_to"):
        progress = (c["rescheduled_to"].get("status") or "").lower()
        notes.append(f"Moved to {_slot_ref(c['rescheduled_to'])} ({progress})")
    if c.get("outcome") == report_service.LATE and c.get("late_minutes") is not None:
        notes.append(f"{c['late_minutes']} min late")
    if c.get("remark"):
        notes.append(escape(str(c["remark"])))
    return " · ".join(notes)


def teacher_pdf(report: dict) -> bytes:
    """Every class a teacher had in the range, and how each one went."""
    minimum = report["min_conducted"]
    name = report.get("teacher_name") or report["teacher_initial"]
    subtitle = "Teacher class report"
    if report.get("label"):
        subtitle += " · " + escape(report["label"])
    story = _header_block(
        escape(f"{name} ({report['teacher_initial']})"), subtitle, report["range"]
    )

    story.append(
        _kpis(
            [
                ("Scheduled", report["total_scheduled"], None),
                ("Held", report["conducted"], OUTCOME_STYLE["CONDUCTED"][0]),
                ("On time", report["on_time"], None),
                ("Late", report["late"], OUTCOME_STYLE["LATE"][0]),
                ("Missed", report["missed"], BAD),
                ("Not checked", report["not_checked"], OUTCOME_STYLE["NOT_CHECKED"][0]),
                ("Rescheduled", report["rescheduled"], OUTCOME_STYLE["RESCHEDULED"][0]),
                ("Conduct rate", f"{report['conduct_rate']}%", None),
            ]
        )
    )

    courses = report.get("courses") or []
    if courses:
        short = sum(1 for c in courses if c["below_minimum"])
        story += [
            Paragraph("Classes held per course", H2),
            _course_table(courses, with_teacher=False),
            Spacer(1, 3),
            Paragraph(
                f"Rows in red have fewer than <b>{minimum}</b> classes held so far "
                f"({short} of {len(courses)}). Held = on time + late, including makeups.",
                NOTE,
            ),
        ]

    classes = report.get("classes") or []
    story.append(Paragraph(f"All classes ({len(classes)})", H2))
    if not classes:
        story.append(Paragraph("No classes in this range.", NOTE))
        return _build(story)

    data: list[list] = [["#", "Date", "Day", "Time", "Room", "Course", "Section",
                         "Status", "Notes"]]
    extra = []
    for i, c in enumerate(classes, start=1):
        fg, bg = OUTCOME_STYLE.get(c["outcome"], (INK, None))
        label = report_service.OUTCOME_LABELS.get(c["outcome"], c["outcome"])
        if c.get("is_makeup"):
            label = f"{label} · makeup"
        data.append(
            [
                i,
                _d(c["date"]),
                c["day"][:3],
                c["time_slot"],
                c["room"],
                c["course_code"],
                c["section"],
                Paragraph(f'<font color="{fg.hexval()}"><b>{label}</b></font>', CELL),
                Paragraph(_class_note(c), CELL_SMALL),
            ]
        )
        if bg is not None:
            extra.append(("BACKGROUND", (0, i), (-1, i), bg))
        if c.get("is_makeup"):
            # A makeup is marked with a bar down its left edge, as on screen.
            extra.append(("LINEBEFORE", (0, i), (0, i), 3, OUTCOME_STYLE["RESCHEDULED"][0]))

    story.append(
        _grid(
            data,
            [9 * mm, 22 * mm, 11 * mm, 24 * mm, 22 * mm, 30 * mm, 18 * mm, 30 * mm, None],
            extra=extra,
        )
    )
    return _build(story)


def summary_pdf(overview: dict) -> bytes:
    """A department-wide period: totals, every teacher, and the courses running short."""
    minimum = overview["min_conducted"]
    totals = overview["totals"]
    active = {k: v for k, v in (overview.get("filters") or {}).items() if v}
    subtitle = "Department summary"
    if overview.get("label"):
        subtitle += " · " + escape(overview["label"])
    if active:
        subtitle += " · " + escape(", ".join(f"{k} {v}" for k, v in active.items()))
    story = _header_block("Class monitoring summary", subtitle, overview["range"])

    story.append(
        _kpis(
            [
                ("Classes", totals["total"], None),
                ("Held", totals["held"], OUTCOME_STYLE["CONDUCTED"][0]),
                ("Late", totals["late"], OUTCOME_STYLE["LATE"][0]),
                ("Missed", totals["missed"], BAD),
                ("Not checked", totals["not_checked"], OUTCOME_STYLE["NOT_CHECKED"][0]),
                ("Rescheduled", totals["rescheduled"], OUTCOME_STYLE["RESCHEDULED"][0]),
                ("Makeups held", totals["makeup_held"], None),
                ("Conduct rate", f"{totals['conduct_rate']}%", None),
            ]
        )
    )

    floors = overview.get("by_floor") or []
    if floors:
        data = [["Floor", "Classes", "Held", "Late", "Missed", "Not checked",
                 "Rescheduled", "Conduct rate"]]
        for f in floors:
            data.append([f["label"], f["total"], f["held"], f["late"], f["missed"],
                         f["not_checked"], f["rescheduled"], f"{f['conduct_rate']}%"])
        story += [Paragraph("By floor", H2), _grid(data, [None] * 8)]

    teachers = overview.get("by_teacher") or []
    if teachers:
        data = [["Teacher", "Name", "Held", "Late", "Missed", "Not checked", "Rescheduled",
                 "Conduct rate", f"Courses < {minimum}"]]
        extra = []
        for i, t in enumerate(teachers, start=1):
            data.append(
                [
                    Paragraph(f"<b>{t['teacher_initial']}</b>", CELL),
                    Paragraph(escape(t.get("teacher_name") or "—"), CELL),
                    t["held"], t["late"], t["missed"], t["not_checked"], t["rescheduled"],
                    f"{t['conduct_rate']}%",
                    f"{t['courses_below_minimum']} of {t['courses']}",
                ]
            )
            if t["flagged"]:
                extra += [
                    ("BACKGROUND", (0, i), (-1, i), BAD_SOFT),
                    ("TEXTCOLOR", (-1, i), (-1, i), BAD),
                    ("FONTNAME", (-1, i), (-1, i), "Helvetica-Bold"),
                ]
        story += [
            Paragraph("By teacher", H2),
            _grid(data, [20 * mm, 70 * mm, *([None] * 7)], extra=extra),
            Spacer(1, 3),
            Paragraph(
                f"Teachers in red have at least one course with fewer than "
                f"<b>{minimum}</b> classes held so far.",
                NOTE,
            ),
        ]

    short = [c for c in overview.get("by_course") or [] if c["below_minimum"]]
    if short:
        story += [
            Paragraph(f"Courses below {minimum} classes held ({len(short)})", H2),
            _course_table(short, with_teacher=True),
        ]

    return _build(story)
