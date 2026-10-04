"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  HeldDistribution,
  OutcomeBars,
  OutcomeShare,
  TeacherBars,
} from "@/components/charts";
import { Button, Card, EmptyState, ErrorNote, Field, Spinner, SummaryCard, inputClass } from "@/components/ui";
import { SLOTS, api, pdfUrl } from "@/lib/api";
import { downloadCsv } from "@/lib/csv";
import { teacherMatcher } from "@/lib/search";
import type { Overview, ReportFilters, TeacherTally, Zone } from "@/lib/types";
import PeriodPicker, {
  type Period,
  currentMonthPeriod,
  minimumNote,
  periodQuery,
} from "./PeriodPicker";

const EMPTY: ReportFilters = { teacher: "", floor: "", course: "", section: "", slot: "" };

const bucketLabel = (iso: string, granularity: Overview["granularity"]) => {
  const d = new Date(`${iso}T00:00:00`);
  if (granularity === "month") return d.toLocaleDateString([], { month: "short", year: "2-digit" });
  const day = d.toLocaleDateString([], { day: "numeric", month: "short" });
  return granularity === "week" ? `Wk ${day}` : day;
};

/**
 * The monthly and semester report: every breakdown for one period, with
 * filters. Opening a teacher hands off to the teacher-wise report.
 */
export default function OverviewReport({
  onOpenTeacher,
}: {
  onOpenTeacher: (initial: string, period: Period) => void;
}) {
  const [period, setPeriod] = useState<Period>(currentMonthPeriod);
  const [draft, setDraft] = useState<ReportFilters>(EMPTY);
  const [filters, setFilters] = useState<ReportFilters>(EMPTY);
  const [zones, setZones] = useState<Zone[]>([]);
  const [data, setData] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.zones().then(setZones).catch(() => setZones([]));
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await api.overview(periodQuery(period), filters));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not build the report.");
    } finally {
      setLoading(false);
    }
  }, [period, filters]);

  useEffect(() => {
    void load();
  }, [load]);

  const active = Object.values(filters).some(Boolean);

  return (
    <div className="space-y-4">
      <Card className="space-y-3 p-3">
        <PeriodPicker value={period} onChange={setPeriod} />
        <form
          className="flex flex-wrap items-end gap-3 border-t border-line pt-3"
          onSubmit={(e) => {
            e.preventDefault();
            setFilters({ ...draft, teacher: draft.teacher?.trim().toUpperCase() });
          }}
        >
          <Field label="Teacher initial">
            <input
              className={`${inputClass} w-28 uppercase`}
              placeholder="e.g. SRH"
              value={draft.teacher}
              onChange={(e) => setDraft({ ...draft, teacher: e.target.value.toUpperCase() })}
            />
          </Field>
          <Field label="Floor">
            <select
              className={inputClass}
              value={draft.floor}
              onChange={(e) => setDraft({ ...draft, floor: e.target.value })}
            >
              <option value="">All floors</option>
              {zones.map((z) => (
                <option key={z.key} value={z.key}>
                  {z.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Time">
            <select
              className={inputClass}
              value={draft.slot}
              onChange={(e) => setDraft({ ...draft, slot: e.target.value })}
            >
              <option value="">All slots</option>
              {SLOTS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Course">
            <input
              className={`${inputClass} w-28`}
              placeholder="CSE311"
              value={draft.course}
              onChange={(e) => setDraft({ ...draft, course: e.target.value })}
            />
          </Field>
          <Field label="Section">
            <input
              className={`${inputClass} w-24`}
              placeholder="62_E"
              value={draft.section}
              onChange={(e) => setDraft({ ...draft, section: e.target.value })}
            />
          </Field>
          <Button type="submit" disabled={loading}>
            {loading ? "Building…" : "Apply"}
          </Button>
          {active ? (
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setDraft(EMPTY);
                setFilters(EMPTY);
              }}
            >
              Clear filters
            </Button>
          ) : null}
          <div className="ml-auto flex gap-2">
            <a
              href={pdfUrl.overview(periodQuery(period), filters)}
              className="inline-flex items-center rounded-lg bg-brand px-3 py-2 text-sm font-medium text-white hover:bg-brand/90"
            >
              Download PDF
            </a>
            {data ? (
              <Button type="button" variant="secondary" onClick={() => exportTeachers(data)}>
                CSV
              </Button>
            ) : null}
          </div>
        </form>
      </Card>

      {error ? <ErrorNote message={error} /> : null}
      {loading && !data ? <Spinner label="Building the report…" /> : null}
      {data ? <OverviewBody data={data} period={period} onOpenTeacher={onOpenTeacher} /> : null}
    </div>
  );
}

function OverviewBody({
  data,
  period,
  onOpenTeacher,
}: {
  data: Overview;
  period: Period;
  onOpenTeacher: (initial: string, period: Period) => void;
}) {
  const t = data.totals;
  const shortCourses = data.by_course.filter((c) => c.below_minimum);
  const mostMissed = data.by_teacher
    .filter((r) => r.missed > 0)
    .sort((a, b) => b.missed - a.missed)
    .slice(0, 10)
    .map((r) => ({ teacher_initial: r.teacher_initial, teacher_name: r.teacher_name, value: r.missed }));

  if (t.total === 0) {
    return (
      <Card>
        <EmptyState title="No classes match" body="Change the period or clear the filters." />
      </Card>
    );
  }

  return (
    <>
      <p className="text-sm text-ink-soft">
        <span className="font-semibold text-ink">{period.label}</span> · {data.range.from} to{" "}
        {data.range.to}
      </p>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-8">
        <SummaryCard
          label="Classes"
          value={t.total}
          hint={`${t.scheduled} in the routine${t.extra_held ? ` · ${t.extra_held} extra held` : ""}`}
        />
        <SummaryCard label="Held" value={t.held} tone="ok" hint="on time + late" />
        <SummaryCard label="Late" value={t.late} tone="warn" hint={t.late ? `avg ${t.avg_late_minutes} min` : undefined} />
        <SummaryCard label="Missed" value={t.missed} tone="bad" hint="teacher absent" />
        <SummaryCard label="Not checked" value={t.not_checked} tone="gap" hint="staff gap" />
        <SummaryCard label="Rescheduled" value={t.rescheduled} tone="info" hint={`${t.makeup_held} makeups held`} />
        <SummaryCard label="Conduct rate" value={`${t.conduct_rate}%`} hint="held ÷ (held + missed)" />
        <SummaryCard
          label={`Courses < ${data.min_conducted}`}
          value={shortCourses.length}
          tone={shortCourses.length ? "bad" : "ok"}
          hint={`of ${data.by_course.length} course-sections`}
        />
      </div>

      <Card className="p-4">
        <h2 className="mb-3 text-sm font-semibold">Where every class stands</h2>
        <OutcomeShare tally={t} />
      </Card>

      <Card className="p-4">
        <h2 className="mb-3 text-sm font-semibold">
          Over time <span className="font-normal text-ink-faint">· per {data.granularity}</span>
        </h2>
        <OutcomeBars
          data={data.trend}
          category="date"
          label={(p) => bucketLabel(p.date, data.granularity)}
        />
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-4">
          <h2 className="mb-3 text-sm font-semibold">By floor</h2>
          <OutcomeBars data={data.by_floor} category="key" label={(f) => f.short_label} horizontal />
        </Card>
        <Card className="p-4">
          <h2 className="mb-3 text-sm font-semibold">By time of day</h2>
          <OutcomeBars
            data={data.by_slot}
            category="time_slot"
            label={(s) => s.time_slot.split("-")[0]}
          />
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-4">
          <h2 className="text-sm font-semibold">Classes held per course-section</h2>
          <p className="mb-3 text-xs text-ink-faint">
            Red: fewer than {data.min_conducted} held so far, {minimumNote(data.term)}.
          </p>
          <HeldDistribution held={data.by_course.map((c) => c.held)} minimum={data.min_conducted} />
        </Card>
        <Card className="p-4">
          <h2 className="text-sm font-semibold">Most missed classes</h2>
          <p className="mb-3 text-xs text-ink-faint">Top 10 teachers, confirmed absences only.</p>
          <TeacherBars rows={mostMissed} value="Missed" color="#b91c1c" unit="missed" />
        </Card>
      </div>

      <TeacherTable data={data} period={period} onOpenTeacher={onOpenTeacher} />
      {shortCourses.length ? <ShortCourses data={data} /> : null}
    </>
  );
}

type SortKey = "flagged" | "held" | "missed" | "not_checked" | "conduct_rate" | "teacher_initial";

function TeacherTable({
  data,
  period,
  onOpenTeacher,
}: {
  data: Overview;
  period: Period;
  onOpenTeacher: (initial: string, period: Period) => void;
}) {
  const [query, setQuery] = useState("");
  const [onlyFlagged, setOnlyFlagged] = useState(false);
  const [sort, setSort] = useState<SortKey>("flagged");

  const rows = useMemo(() => {
    const matches = teacherMatcher(query, data.by_teacher.map((r) => r.teacher_initial));
    const list = data.by_teacher.filter(
      (r) => (!onlyFlagged || r.flagged) && matches(r.teacher_initial, r.teacher_name),
    );
    const by: Record<SortKey, (a: TeacherTally, b: TeacherTally) => number> = {
      flagged: (a, b) => b.courses_below_minimum - a.courses_below_minimum || a.held - b.held,
      held: (a, b) => a.held - b.held,
      missed: (a, b) => b.missed - a.missed,
      not_checked: (a, b) => b.not_checked - a.not_checked,
      conduct_rate: (a, b) => a.conduct_rate - b.conduct_rate,
      teacher_initial: (a, b) => a.teacher_initial.localeCompare(b.teacher_initial),
    };
    return [...list].sort(by[sort]);
  }, [data.by_teacher, query, onlyFlagged, sort]);

  const flagged = data.by_teacher.filter((r) => r.flagged).length;
  const th = (key: SortKey, label: string) => (
    <th className="px-3 py-2 font-medium">
      <button
        type="button"
        onClick={() => setSort(key)}
        className={`uppercase tracking-wide ${sort === key ? "text-brand" : "hover:text-ink"}`}
      >
        {label}
        {sort === key ? " ↓" : ""}
      </button>
    </th>
  );

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
        <h2 className="text-sm font-semibold">
          Teachers ({data.by_teacher.length})
          {flagged ? (
            <span className="ml-2 rounded-full bg-bad-soft px-2 py-0.5 text-xs font-semibold text-bad">
              {flagged} below {data.min_conducted}
            </span>
          ) : null}
        </h2>
        <input
          className={`${inputClass} ml-auto w-44`}
          placeholder="Search initial or name"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <label className="flex items-center gap-1.5 text-sm text-ink-soft">
          <input
            type="checkbox"
            checked={onlyFlagged}
            onChange={(e) => setOnlyFlagged(e.target.checked)}
          />
          Only red
        </label>
      </div>
      <div className="max-h-[32rem] overflow-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-surface">
            <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-faint">
              {th("teacher_initial", "Teacher")}
              <th className="px-3 py-2 font-medium">Name</th>
              {th("held", "Held")}
              <th className="px-3 py-2 font-medium">Late</th>
              {th("missed", "Missed")}
              {th("not_checked", "Not checked")}
              <th className="px-3 py-2 font-medium">Resch.</th>
              {th("conduct_rate", "Rate")}
              {th("flagged", `Courses < ${data.min_conducted}`)}
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((r) => (
              <tr key={r.teacher_initial} className={r.flagged ? "bg-bad-soft/60" : undefined}>
                <td className={`px-3 py-2 font-semibold ${r.flagged ? "text-bad" : ""}`}>
                  {r.teacher_initial}
                </td>
                <td className="max-w-56 truncate px-3 py-2 text-ink-soft">{r.teacher_name ?? "—"}</td>
                <td className="px-3 py-2 tabular-nums">{r.held}</td>
                <td className="px-3 py-2 tabular-nums text-ink-soft">{r.late}</td>
                <td className="px-3 py-2 tabular-nums">{r.missed}</td>
                <td className="px-3 py-2 tabular-nums text-ink-soft">{r.not_checked}</td>
                <td className="px-3 py-2 tabular-nums text-ink-soft">{r.rescheduled}</td>
                <td className="px-3 py-2 tabular-nums">{r.conduct_rate}%</td>
                <td className={`px-3 py-2 tabular-nums ${r.flagged ? "font-bold text-bad" : "text-ink-faint"}`}>
                  {r.courses_below_minimum} of {r.courses}
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
    </Card>
  );
}

function ShortCourses({ data }: { data: Overview }) {
  const [open, setOpen] = useState(false);
  const short = data.by_course.filter((c) => c.below_minimum);
  const shown = open ? short : short.slice(0, 10);
  return (
    <Card>
      <div className="border-b border-line px-4 py-3">
        <h2 className="text-sm font-semibold text-bad">
          Course-sections below {data.min_conducted} classes held ({short.length})
        </h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-faint">
              <th className="px-4 py-2 font-medium">Teacher</th>
              <th className="px-4 py-2 font-medium">Course</th>
              <th className="px-4 py-2 font-medium">Section</th>
              <th className="px-4 py-2 font-medium">Held</th>
              <th className="px-4 py-2 font-medium">Missed</th>
              <th className="px-4 py-2 font-medium">Not checked</th>
              <th className="px-4 py-2 font-medium">Short by</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {shown.map((c) => (
              <tr key={`${c.teacher_initial}-${c.course_code}-${c.section}`} className="bg-bad-soft/40">
                <td className="px-4 py-2 font-semibold">{c.teacher_initial}</td>
                <td className="px-4 py-2">{c.course_code}</td>
                <td className="px-4 py-2 text-ink-soft">{c.section}</td>
                <td className="px-4 py-2 font-bold tabular-nums text-bad">{c.held}</td>
                <td className="px-4 py-2 tabular-nums">{c.missed}</td>
                <td className="px-4 py-2 tabular-nums text-ink-soft">{c.not_checked}</td>
                <td className="px-4 py-2 tabular-nums text-bad">{data.min_conducted - c.held}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {short.length > 10 ? (
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="w-full border-t border-line py-2 text-sm font-semibold text-brand hover:bg-canvas"
        >
          {open ? "Show fewer" : `Show all ${short.length}`}
        </button>
      ) : null}
    </Card>
  );
}

function exportTeachers(data: Overview) {
  downloadCsv(`classtrack-teachers-${data.range.from}-${data.range.to}.csv`, [
    ["Initial", "Name", "Classes", "Held", "On time", "Late", "Missed", "Not checked",
      "Rescheduled", "Makeups held", "Extra held", "Conduct rate %",
      `Courses below ${data.min_conducted}`,
      "Courses", "Flagged"],
    ...data.by_teacher.map((r) => [
      r.teacher_initial, r.teacher_name, r.total, r.held, r.conducted, r.late, r.missed,
      r.not_checked, r.rescheduled, r.makeup_held, r.extra_held, r.conduct_rate,
      r.courses_below_minimum,
      r.courses, r.flagged ? "yes" : "no",
    ]),
  ]);
}
