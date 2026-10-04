import OutcomeBadge from "@/components/OutcomeBadge";
import {
  ExtraTag,
  MovedToTag,
  RescheduledTag,
  rescheduledRowClass,
  shortDay,
} from "@/components/Rescheduled";
import type { ClassRow } from "@/lib/types";

/** Every class in a report, one row each, with its outcome and where it moved. */
export default function ClassTable({
  rows,
  showTeacher = false,
}: {
  rows: ClassRow[];
  showTeacher?: boolean;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-faint">
            <th className="px-4 py-2 font-medium">Date</th>
            <th className="px-4 py-2 font-medium">Time</th>
            <th className="px-4 py-2 font-medium">Room</th>
            <th className="px-4 py-2 font-medium">Course</th>
            <th className="px-4 py-2 font-medium">Section</th>
            {showTeacher ? <th className="px-4 py-2 font-medium">Teacher</th> : null}
            <th className="px-4 py-2 font-medium">Status</th>
            <th className="px-4 py-2 font-medium">Notes</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((c) => (
            <tr key={c.instance_id} className={c.is_makeup ? rescheduledRowClass : undefined}>
              <td className="whitespace-nowrap px-4 py-2 font-medium">{shortDay(c.date)}</td>
              <td className="whitespace-nowrap px-4 py-2 tabular-nums text-ink-soft">
                {c.time_slot}
              </td>
              <td className="px-4 py-2 text-ink-soft">{c.room}</td>
              <td className="px-4 py-2">{c.course_code}</td>
              <td className="px-4 py-2 text-ink-soft">{c.section}</td>
              {showTeacher ? (
                <td className="px-4 py-2 text-ink-soft" title={c.teacher_name ?? undefined}>
                  {c.teacher_initial}
                </td>
              ) : null}
              <td className="px-4 py-2">
                <OutcomeBadge outcome={c.outcome} lateMinutes={c.late_minutes} />
              </td>
              <td className="px-4 py-2">
                <div className="flex flex-wrap items-center gap-1.5">
                  {c.is_makeup ? <RescheduledTag from={c.rescheduled_from} /> : null}
                  {c.is_extra ? <ExtraTag /> : null}
                  {c.rescheduled_to ? <MovedToTag to={c.rescheduled_to} /> : null}
                  {c.remark ? <span className="text-xs text-ink-faint">{c.remark}</span> : null}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
