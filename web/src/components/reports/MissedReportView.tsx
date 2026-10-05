"use client";

import { useEffect, useMemo, useState } from "react";
import { Button, Card, EmptyState, ErrorNote, Spinner, SummaryCard, inputClass } from "@/components/ui";
import { api } from "@/lib/api";
import { downloadCsv } from "@/lib/csv";
import { teacherMatcher } from "@/lib/search";
import type { CourseTally, Overview, TeacherTally } from "@/lib/types";
import PeriodPicker, { type Period, currentMonthPeriod, periodQuery } from "./PeriodPicker";

type Ranked = TeacherTally & { rank: number; missedIn: CourseTally[] };

/**
 * Every teacher who missed a class in the period, most missed first. Only
 * confirmed absences count: a class nobody checked is a staff gap, and a missed
 * class already moved to a makeup is counted as rescheduled.
 */
export default function MissedReportView({
  onOpenTeacher,
}: {
  onOpenTeacher: (initial: string, period: Period) => void;
}) {
  const [period, setPeriod] = useState<Period>(currentMonthPeriod);
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    let alive = true;
    setError(null);
    api
      .overview(periodQuery(period))
      .then((d) => alive && setData(d))
      .catch((err) => alive && setError(err instanceof Error ? err.message : "Could not load."));
    return () => {
      alive = false;
    };
  }, [period]);

  const ranked = useMemo(() => (data ? rank(data) : []), [data]);
  const rows = useMemo(() => {
    const matches = teacherMatcher(query, ranked.map((r) => r.teacher_initial));
    return ranked.filter((r) => matches(r.teacher_initial, r.teacher_name));
  }, [ranked, query]);

  const top = ranked[0]?.missed ?? 0;
  const leaders = ranked.filter((r) => r.missed === top).map((r) => r.teacher_initial);

  return (
    <div className="space-y-4">
      <Card className="p-3">
        <PeriodPicker value={period} onChange={setPeriod} />
      </Card>
      {error ? <ErrorNote message={error} /> : null}
      {!data ? (
        <Spinner label="Building the report…" />
      ) : (
        <>
          <p className="text-sm text-ink-soft">
            <span className="font-semibold text-ink">{period.label}</span> · {data.range.from} to{" "}
            {data.range.to}
          </p>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <SummaryCard
              label="Teachers who missed"
              value={ranked.length}
              tone={ranked.length ? "bad" : "ok"}
              hint={`of ${data.by_teacher.length} teaching`}
            />
            <SummaryCard label="Classes missed" value={data.totals.missed} tone="bad" hint="confirmed absences" />
            <SummaryCard
              label="Most by one teacher"
              value={top}
              tone={top ? "bad" : "ok"}
              hint={leaders.length ? leaders.slice(0, 3).join(", ") + (leaders.length > 3 ? "…" : "") : undefined}
            />
            <SummaryCard
              label="Rescheduled"
              value={data.totals.rescheduled}
              tone="info"
              hint="missed, then moved"
            />
          </div>

          <Card>
            <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
              <h2 className="text-sm font-semibold">
                Teachers with missed classes ({ranked.length})
                <span className="ml-2 font-normal text-ink-faint">most missed first</span>
              </h2>
              {ranked.length ? (
                <div className="ml-auto flex items-center gap-2">
                  <div className="w-44">
                    <input
                      className={inputClass}
                      placeholder="Search initial or name"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                    />
                  </div>
                  <Button type="button" variant="secondary" onClick={() => exportMissed(data, ranked)}>
                    CSV
                  </Button>
                </div>
              ) : null}
            </div>
            {ranked.length === 0 ? (
              <EmptyState title="No missed classes" body={`No teacher missed a class in ${period.label}.`} />
            ) : (
              <div className="max-h-[40rem] overflow-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-surface">
                    <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-faint">
                      <th className="px-3 py-2 font-medium">#</th>
                      <th className="px-3 py-2 font-medium">Teacher</th>
                      <th className="px-3 py-2 font-medium">Name</th>
                      <th className="px-3 py-2 font-medium">Missed</th>
                      <th className="px-3 py-2 font-medium">Held</th>
                      <th className="px-3 py-2 font-medium">Resch.</th>
                      <th className="px-3 py-2 font-medium">Rate</th>
                      <th className="px-3 py-2 font-medium">Missed in</th>
                      <th className="px-3 py-2" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {rows.map((r) => (
                      <tr key={r.teacher_initial}>
                        <td className="px-3 py-2 tabular-nums text-ink-faint">{r.rank}</td>
                        <td className="px-3 py-2 font-semibold">{r.teacher_initial}</td>
                        <td className="max-w-56 truncate px-3 py-2 text-ink-soft">{r.teacher_name ?? "—"}</td>
                        <td className="px-3 py-2">
                          <div className="flex items-center gap-2">
                            <span className="w-6 text-right font-bold tabular-nums text-bad">{r.missed}</span>
                            <div className="h-1.5 w-20 rounded-full bg-canvas">
                              <div
                                className="h-1.5 rounded-full bg-bad"
                                style={{ width: `${(r.missed / top) * 100}%` }}
                              />
                            </div>
                          </div>
                        </td>
                        <td className="px-3 py-2 tabular-nums">{r.held}</td>
                        <td className="px-3 py-2 tabular-nums text-ink-soft">{r.rescheduled}</td>
                        <td className="px-3 py-2 tabular-nums">{r.conduct_rate}%</td>
                        <td className="px-3 py-2">
                          <div className="flex min-w-48 flex-wrap gap-1">
                            {r.missedIn.map((c) => (
                              <span
                                key={`${c.course_code}-${c.section}`}
                                title={c.course_title ?? undefined}
                                className="whitespace-nowrap rounded-md bg-bad-soft px-1.5 py-0.5 text-xs text-bad"
                              >
                                {courseLabel(c)}
                                {c.missed > 1 ? <span className="font-semibold"> ×{c.missed}</span> : null}
                              </span>
                            ))}
                          </div>
                        </td>
                        <td className="px-3 py-2 text-right">
                          <button
                            type="button"
                            className="whitespace-nowrap rounded-md px-2 py-1 text-sm font-semibold text-brand hover:bg-brand-soft"
                            onClick={() => onOpenTeacher(r.teacher_initial, period)}
                          >
                            Report ›
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {rows.length === 0 ? <EmptyState title="No teacher matches" /> : null}
              </div>
            )}
          </Card>
          <p className="text-xs text-ink-faint">
            Missed counts confirmed absences only. A class nobody checked is a staff gap and is
            not counted; a missed class moved to a makeup is counted under rescheduled.
          </p>
        </>
      )}
    </div>
  );
}

/** Teachers with a missed class, most first; ties share a rank. */
function rank(data: Overview): Ranked[] {
  const courses = new Map<string, CourseTally[]>();
  for (const c of data.by_course) {
    if (c.missed > 0) courses.set(c.teacher_initial, [...(courses.get(c.teacher_initial) ?? []), c]);
  }
  const list = data.by_teacher
    .filter((r) => r.missed > 0)
    .sort((a, b) => b.missed - a.missed || a.teacher_initial.localeCompare(b.teacher_initial));
  const out: Ranked[] = [];
  list.forEach((r, i) => {
    const prev = out[i - 1];
    out.push({
      ...r,
      rank: prev && prev.missed === r.missed ? prev.rank : i + 1,
      missedIn: (courses.get(r.teacher_initial) ?? []).sort((a, b) => b.missed - a.missed),
    });
  });
  return out;
}

/** Routine course codes carry their section already, as in "CSE322(67_D1)". */
const courseLabel = (c: CourseTally) =>
  c.course_code.includes(c.section) ? c.course_code : `${c.course_code} · ${c.section}`;

function exportMissed(data: Overview, ranked: Ranked[]) {
  downloadCsv(`classtrack-missed-${data.range.from}-${data.range.to}.csv`, [
    ["Rank", "Initial", "Name", "Missed", "Held", "Rescheduled", "Conduct rate %", "Missed in"],
    ...ranked.map((r) => [
      r.rank, r.teacher_initial, r.teacher_name, r.missed, r.held, r.rescheduled, r.conduct_rate,
      r.missedIn.map((c) => `${courseLabel(c)} (${c.missed})`).join("; "),
    ]),
  ]);
}
