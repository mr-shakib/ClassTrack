"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { OUTCOME, OUTCOME_ORDER } from "@/components/OutcomeBadge";
import { Button, Card, EmptyState, ErrorNote, Field, Spinner, SummaryCard, inputClass } from "@/components/ui";
import { api, pdfUrl } from "@/lib/api";
import { downloadCsv } from "@/lib/csv";
import type { Outcome, TeacherAccount, TeacherReport } from "@/lib/types";
import ClassTable from "./ClassTable";
import PeriodPicker, { type Period, minimumNote, periodQuery } from "./PeriodPicker";

/**
 * One teacher: headline figures, every course against the minimum, and every
 * class in the period. The PDF lists the same classes.
 */
export default function TeacherReportView({
  isAdmin,
  initial: initialProp,
  period: periodProp,
}: {
  isAdmin: boolean;
  initial: string;
  period: Period;
}) {
  const [period, setPeriod] = useState<Period>(periodProp);
  const [draft, setDraft] = useState(initialProp);
  const [initial, setInitial] = useState(initialProp);
  const [directory, setDirectory] = useState<TeacherAccount[]>([]);
  const [data, setData] = useState<TeacherReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [only, setOnly] = useState<Outcome | "MAKEUP" | null>(null);

  // A new selection from the overview replaces what is shown here.
  useEffect(() => {
    setInitial(initialProp);
    setDraft(initialProp);
  }, [initialProp]);
  useEffect(() => setPeriod(periodProp), [periodProp]);

  useEffect(() => {
    if (isAdmin) api.teachers().then(setDirectory).catch(() => setDirectory([]));
  }, [isAdmin]);

  const load = useCallback(async () => {
    if (!initial) return;
    setLoading(true);
    setError(null);
    try {
      setData(await api.teacherReport(initial, periodQuery(period)));
    } catch (err) {
      setData(null);
      setError(err instanceof Error ? err.message : "Could not build the report.");
    } finally {
      setLoading(false);
    }
  }, [initial, period]);

  useEffect(() => {
    void load();
  }, [load]);

  const classes = useMemo(() => {
    const all = data?.classes ?? [];
    if (only === "MAKEUP") return all.filter((c) => c.is_makeup);
    return only ? all.filter((c) => c.outcome === only) : all;
  }, [data, only]);

  const counts = useMemo(() => {
    const out: Partial<Record<Outcome, number>> = {};
    for (const c of data?.classes ?? []) out[c.outcome] = (out[c.outcome] ?? 0) + 1;
    return out;
  }, [data]);

  return (
    <div className="space-y-4">
      <Card className="space-y-3 p-3">
        <PeriodPicker value={period} onChange={setPeriod} />
        {isAdmin ? (
          <form
            className="flex flex-wrap items-end gap-3 border-t border-line pt-3"
            onSubmit={(e) => {
              e.preventDefault();
              setInitial(draft.trim().toUpperCase());
            }}
          >
            <Field label="Teacher initial">
              <input
                className={`${inputClass} w-36 uppercase`}
                placeholder="e.g. SRH"
                list="teacher-directory"
                value={draft}
                onChange={(e) => setDraft(e.target.value.toUpperCase())}
              />
              <datalist id="teacher-directory">
                {directory.map((t) => (
                  <option key={t.initial} value={t.initial}>
                    {t.name}
                  </option>
                ))}
              </datalist>
            </Field>
            <Button type="submit" disabled={loading || !draft.trim()}>
              {loading ? "Building…" : "Show report"}
            </Button>
          </form>
        ) : null}
      </Card>

      {error ? <ErrorNote message={error} /> : null}
      {!initial ? (
        <Card>
          <EmptyState title="Enter a teacher's initial" body="Or open one from the overview's teacher table." />
        </Card>
      ) : loading && !data ? (
        <Spinner label="Building the report…" />
      ) : data ? (
        <>
          <Card className={`flex flex-wrap items-center gap-3 p-4 ${data.flagged ? "border-bad/40 bg-bad-soft/40" : ""}`}>
            <div className="min-w-0">
              <p className="text-lg font-semibold">
                {data.teacher_name ?? data.teacher_initial}{" "}
                <span className="font-normal text-ink-faint">({data.teacher_initial})</span>
              </p>
              <p className="text-sm text-ink-faint">
                {period.label} · {data.range.from} to {data.range.to}
              </p>
            </div>
            {data.flagged ? (
              <span className="rounded-full bg-bad px-3 py-1 text-sm font-semibold text-white">
                {data.courses.filter((c) => c.below_minimum).length} course
                {data.courses.filter((c) => c.below_minimum).length === 1 ? "" : "s"} below{" "}
                {data.min_conducted} classes
              </span>
            ) : null}
            <div className="ml-auto flex gap-2">
              <a
                href={pdfUrl.teacher(data.teacher_initial, periodQuery(period))}
                className="inline-flex items-center rounded-lg bg-brand px-3 py-2 text-sm font-medium text-white hover:bg-brand/90"
              >
                Download PDF
              </a>
              <Button variant="secondary" onClick={() => exportClasses(data)}>
                CSV
              </Button>
            </div>
          </Card>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-8">
            <SummaryCard label="Scheduled" value={data.total_scheduled} />
            <SummaryCard label="Held" value={data.conducted} tone="ok" hint="incl. makeups" />
            <SummaryCard label="On time" value={data.on_time} tone="ok" />
            <SummaryCard label="Late" value={data.late} tone="warn" hint={data.late ? `avg ${data.avg_late_minutes} min` : undefined} />
            <SummaryCard label="Missed" value={data.missed} tone="bad" />
            <SummaryCard label="Not checked" value={data.not_checked} tone="gap" hint="staff gap" />
            <SummaryCard label="Rescheduled" value={data.rescheduled} tone="info" hint={`${data.makeup_completed} makeups done`} />
            <SummaryCard label="Conduct rate" value={`${data.conduct_rate}%`} />
          </div>

          <Card>
            <div className="border-b border-line px-4 py-3">
              <h2 className="text-sm font-semibold">Classes held per course</h2>
              <p className="text-xs text-ink-faint">
                Red: fewer than {data.min_conducted} held so far, {minimumNote(data.term)}. Held = on
                time + late, including makeups.
              </p>
            </div>
            {data.courses.length === 0 ? (
              <EmptyState title="No classes in this period" />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-faint">
                      <th className="px-4 py-2 font-medium">Course</th>
                      <th className="px-4 py-2 font-medium">Section</th>
                      <th className="px-4 py-2 font-medium">Held</th>
                      <th className="w-1/4 px-4 py-2 font-medium">Toward {data.min_conducted}</th>
                      <th className="px-4 py-2 font-medium">Late</th>
                      <th className="px-4 py-2 font-medium">Missed</th>
                      <th className="px-4 py-2 font-medium">Not checked</th>
                      <th className="px-4 py-2 font-medium">Rescheduled</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {data.courses.map((c) => (
                      <tr key={`${c.course_code}-${c.section}`} className={c.below_minimum ? "bg-bad-soft/60" : undefined}>
                        <td className="px-4 py-2 font-medium">{c.course_code}</td>
                        <td className="px-4 py-2 text-ink-soft">{c.section}</td>
                        <td className={`px-4 py-2 font-bold tabular-nums ${c.below_minimum ? "text-bad" : "text-ok"}`}>
                          {c.held}
                        </td>
                        <td className="px-4 py-2">
                          <div className="h-2 overflow-hidden rounded-full bg-line" title={`${c.held} of ${data.min_conducted}`}>
                            <div
                              className={`h-full rounded-full ${c.below_minimum ? "bg-bad" : "bg-ok"}`}
                              style={{ width: `${Math.min(100, (c.held / data.min_conducted) * 100)}%` }}
                            />
                          </div>
                        </td>
                        <td className="px-4 py-2 tabular-nums text-ink-soft">{c.late}</td>
                        <td className="px-4 py-2 tabular-nums">{c.missed}</td>
                        <td className="px-4 py-2 tabular-nums text-ink-soft">{c.not_checked}</td>
                        <td className="px-4 py-2 tabular-nums text-ink-soft">{c.rescheduled}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <Card>
            <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-3">
              <h2 className="mr-2 text-sm font-semibold">All classes ({data.classes.length})</h2>
              <Chip active={only == null} onClick={() => setOnly(null)}>All</Chip>
              {OUTCOME_ORDER.filter((o) => counts[o]).map((o) => (
                <Chip key={o} active={only === o} onClick={() => setOnly(only === o ? null : o)}>
                  {OUTCOME[o].label} · {counts[o]}
                </Chip>
              ))}
              {data.classes.some((c) => c.is_makeup) ? (
                <Chip active={only === "MAKEUP"} onClick={() => setOnly(only === "MAKEUP" ? null : "MAKEUP")}>
                  Makeups · {data.classes.filter((c) => c.is_makeup).length}
                </Chip>
              ) : null}
            </div>
            {classes.length === 0 ? <EmptyState title="No classes" /> : <ClassTable rows={classes} />}
          </Card>
        </>
      ) : null}
    </div>
  );
}

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full px-3 py-1 text-xs font-semibold ring-1 ring-inset ${
        active ? "bg-brand text-white ring-brand" : "bg-surface text-ink-soft ring-line hover:bg-canvas"
      }`}
    >
      {children}
    </button>
  );
}

function exportClasses(r: TeacherReport) {
  downloadCsv(`classtrack-${r.teacher_initial}-${r.range.from}-${r.range.to}.csv`, [
    ["Date", "Day", "Time", "Room", "Course", "Section", "Status", "Late minutes",
      "Makeup for", "Moved to", "Remark"],
    ...r.classes.map((c) => [
      c.date, c.day, c.time_slot, c.room, c.course_code, c.section, OUTCOME[c.outcome].label,
      c.late_minutes,
      c.rescheduled_from ? `${c.rescheduled_from.date} ${c.rescheduled_from.time_slot}` : "",
      c.rescheduled_to ? `${c.rescheduled_to.date} ${c.rescheduled_to.time_slot}` : "",
      c.remark,
    ]),
  ]);
}
