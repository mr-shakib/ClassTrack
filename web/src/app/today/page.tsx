"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { OUTCOME, OUTCOME_ORDER } from "@/components/OutcomeBadge";
import { MovedToTag, RescheduledTag, rescheduledRowClass } from "@/components/Rescheduled";
import StatusBadge from "@/components/StatusBadge";
import { Card, EmptyState, ErrorNote, Field, Spinner, inputClass } from "@/components/ui";
import { SLOTS, api, todayISO } from "@/lib/api";
import { MANAGEMENT_ROLES, useRequireRole } from "@/lib/auth";
import type { DayRow, DayStatus, Outcome } from "@/lib/types";

type Filter = {
  q: string;
  floor: string;
  slot: string;
  outcome: Outcome | "";
  makeupOnly: boolean;
};

const EMPTY: Filter = { q: "", floor: "", slot: "", outcome: "", makeupOnly: false };

/**
 * Every class on one day, filterable by teacher, floor, time and outcome.
 *
 * The dashboard answers "what is happening in this slot"; this answers "how is
 * the day going" and "where is this teacher today". One day is a few hundred
 * rows, so filtering happens here, on every keystroke, without a round trip.
 */
export default function DayStatusPage() {
  const { permitted, loading: authLoading } = useRequireRole(MANAGEMENT_ROLES);
  const [date, setDate] = useState(todayISO());
  const [data, setData] = useState<DayStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [f, setF] = useState<Filter>(EMPTY);

  const load = useCallback(async () => {
    try {
      setData(await api.dayStatus(date));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the day.");
    }
  }, [date]);

  useEffect(() => {
    if (!permitted) return;
    void load();
    // Only today changes under you; a past day is settled.
    if (date !== todayISO()) return;
    const timer = setInterval(load, 60_000);
    return () => clearInterval(timer);
  }, [permitted, load, date]);

  const floors = useMemo(() => {
    const seen = new Map<string, string>();
    for (const r of data?.rows ?? []) seen.set(r.zone_key, r.zone);
    return [...seen.entries()].sort((a, b) => a[1].localeCompare(b[1]));
  }, [data]);

  // Everything but the outcome filter: the outcome chips count within this.
  const scoped = useMemo(() => {
    const q = f.q.trim().toUpperCase();
    return (data?.rows ?? []).filter(
      (r) =>
        (!q ||
          r.teacher_initial.toUpperCase().startsWith(q) ||
          (r.teacher_name ?? "").toUpperCase().includes(q) ||
          r.course_code.toUpperCase().includes(q) ||
          r.room.toUpperCase().includes(q) ||
          r.section.toUpperCase().includes(q)) &&
        (!f.floor || r.zone_key === f.floor) &&
        (!f.slot || r.time_slot === f.slot) &&
        (!f.makeupOnly || r.is_makeup),
    );
  }, [data, f.q, f.floor, f.slot, f.makeupOnly]);

  const rows = useMemo(
    () => (f.outcome ? scoped.filter((r) => r.outcome === f.outcome) : scoped),
    [scoped, f.outcome],
  );

  const counts = useMemo(() => {
    const out: Partial<Record<Outcome, number>> = {};
    for (const r of scoped) out[r.outcome] = (out[r.outcome] ?? 0) + 1;
    return out;
  }, [scoped]);

  if (authLoading || !permitted) return <Spinner />;

  const filtered = JSON.stringify(f) !== JSON.stringify(EMPTY);
  const makeups = (data?.rows ?? []).filter((r) => r.is_makeup).length;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold">Day status</h1>
          <p className="mt-0.5 text-sm text-ink-soft">
            {new Date(`${date}T00:00:00`).toLocaleDateString([], {
              weekday: "long",
              day: "numeric",
              month: "long",
              year: "numeric",
            })}
            {data?.current_slot ? ` · now ${data.current_slot}` : ""}
          </p>
        </div>
        {date === todayISO() ? (
          <span className="flex items-center gap-1.5 text-xs text-ink-faint">
            <span className="size-2 animate-pulse rounded-full bg-ok" />
            refreshes every minute
          </span>
        ) : null}
      </div>

      <Card className="p-3">
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Date">
            <input
              type="date"
              className={inputClass}
              value={date}
              onChange={(e) => e.target.value && setDate(e.target.value)}
            />
          </Field>
          <Field label="Teacher initial, course or room">
            <input
              className={`${inputClass} w-56`}
              placeholder="e.g. SRH, CSE311, KT-305"
              value={f.q}
              onChange={(e) => setF({ ...f, q: e.target.value })}
              autoFocus
            />
          </Field>
          <Field label="Floor">
            <select className={inputClass} value={f.floor} onChange={(e) => setF({ ...f, floor: e.target.value })}>
              <option value="">All floors</option>
              {floors.map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Time">
            <select className={inputClass} value={f.slot} onChange={(e) => setF({ ...f, slot: e.target.value })}>
              <option value="">All day</option>
              {SLOTS.map((s) => (
                <option key={s} value={s}>
                  {s}
                  {s === data?.current_slot ? " (now)" : ""}
                </option>
              ))}
            </select>
          </Field>
          <label className="flex min-h-9 items-center gap-1.5 text-sm text-ink-soft">
            <input
              type="checkbox"
              checked={f.makeupOnly}
              onChange={(e) => setF({ ...f, makeupOnly: e.target.checked })}
            />
            Makeups only{makeups ? ` (${makeups})` : ""}
          </label>
          {filtered ? (
            <button
              type="button"
              className="rounded-lg px-3 py-2 text-sm font-medium text-ink-soft hover:bg-canvas"
              onClick={() => setF(EMPTY)}
            >
              Clear
            </button>
          ) : null}
        </div>

        {/* Outcome chips double as the day's summary. */}
        <div className="mt-3 flex flex-wrap gap-2 border-t border-line pt-3">
          <Chip active={!f.outcome} onClick={() => setF({ ...f, outcome: "" })} label="All" count={scoped.length} />
          {OUTCOME_ORDER.filter((o) => counts[o]).map((o) => (
            <Chip
              key={o}
              active={f.outcome === o}
              onClick={() => setF({ ...f, outcome: f.outcome === o ? "" : o })}
              label={OUTCOME[o].label}
              count={counts[o] ?? 0}
              tone={OUTCOME[o].className}
            />
          ))}
        </div>
      </Card>

      {error ? <ErrorNote message={error} /> : null}

      {!data ? (
        <Spinner />
      ) : data.rows.length === 0 ? (
        <Card>
          <EmptyState title="No classes on this day" body="A holiday, the weekend, or outside the semester." />
        </Card>
      ) : (
        <>
          <FloorSummary rows={scoped} onPick={(key) => setF({ ...f, floor: f.floor === key ? "" : key })} selected={f.floor} />

          <Card>
            <div className="border-b border-line px-4 py-3">
              <h2 className="text-sm font-semibold">
                {rows.length} {rows.length === 1 ? "class" : "classes"}
                {filtered ? <span className="font-normal text-ink-faint"> of {data.rows.length}</span> : null}
              </h2>
            </div>
            {rows.length === 0 ? (
              <EmptyState title="Nothing matches these filters" />
            ) : (
              <DayTable rows={rows} currentSlot={data.current_slot} />
            )}
          </Card>
        </>
      )}
    </div>
  );
}

function Chip({
  active,
  onClick,
  label,
  count,
  tone,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  count: number;
  tone?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-semibold ring-1 ring-inset ${
        active
          ? "bg-brand text-white ring-brand"
          : tone ?? "bg-surface text-ink-soft ring-line"
      }`}
    >
      {label}
      <span className="tabular-nums opacity-80">{count}</span>
    </button>
  );
}

/** Classes per floor, with how many are settled -- a tap filters to that floor. */
function FloorSummary({
  rows,
  onPick,
  selected,
}: {
  rows: DayRow[];
  onPick: (key: string) => void;
  selected: string;
}) {
  const floors = useMemo(() => {
    const map = new Map<string, { key: string; label: string; total: number; held: number; missed: number; gap: number }>();
    for (const r of rows) {
      const f = map.get(r.zone_key) ?? { key: r.zone_key, label: r.zone, total: 0, held: 0, missed: 0, gap: 0 };
      f.total += 1;
      if (r.outcome === "CONDUCTED" || r.outcome === "LATE") f.held += 1;
      if (r.outcome === "MISSED") f.missed += 1;
      if (r.outcome === "NOT_CHECKED") f.gap += 1;
      map.set(r.zone_key, f);
    }
    return [...map.values()].sort((a, b) => a.label.localeCompare(b.label));
  }, [rows]);

  if (floors.length <= 1) return null;

  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-6">
      {floors.map((f) => (
        <button
          key={f.key}
          type="button"
          onClick={() => onPick(f.key)}
          className={`rounded-xl border bg-surface p-3 text-left transition-colors hover:border-brand/50 ${
            selected === f.key ? "border-brand ring-2 ring-brand/20" : "border-line"
          }`}
        >
          <p className="text-sm font-semibold">{f.label}</p>
          <p className="text-2xl font-semibold tabular-nums">{f.total}</p>
          <p className="text-xs text-ink-faint">
            <span className="text-ok">{f.held} held</span>
            {f.missed ? <span className="text-bad"> · {f.missed} missed</span> : null}
            {f.gap ? <span className="text-gap"> · {f.gap} unchecked</span> : null}
          </p>
        </button>
      ))}
    </div>
  );
}

function DayTable({ rows, currentSlot }: { rows: DayRow[]; currentSlot: string | null }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-faint">
            <th className="px-4 py-2 font-medium">Time</th>
            <th className="px-4 py-2 font-medium">Room</th>
            <th className="px-4 py-2 font-medium">Teacher</th>
            <th className="px-4 py-2 font-medium">Course</th>
            <th className="px-4 py-2 font-medium">Status</th>
            <th className="px-4 py-2 font-medium">Checked by</th>
            <th className="px-4 py-2 font-medium">Notes</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((r) => (
            <tr
              key={r.instance_id}
              className={
                r.is_makeup
                  ? rescheduledRowClass
                  : r.outcome === "MISSED"
                    ? "bg-bad-soft/40"
                    : r.outcome === "NOT_CHECKED"
                      ? "bg-gap-soft/40"
                      : undefined
              }
            >
              <td className="whitespace-nowrap px-4 py-2 tabular-nums">
                <span className={r.time_slot === currentSlot ? "font-semibold text-brand" : "text-ink-soft"}>
                  {r.start}–{r.end}
                </span>
              </td>
              <td className="whitespace-nowrap px-4 py-2 font-medium">
                {r.room}
                <span className="ml-1.5 text-xs font-normal text-ink-faint">{r.zone}</span>
              </td>
              <td className="px-4 py-2">
                <span className="font-semibold">{r.teacher_initial}</span>
                {r.teacher_name ? (
                  <span className="ml-1.5 hidden text-ink-faint xl:inline">{r.teacher_name}</span>
                ) : null}
              </td>
              <td className="whitespace-nowrap px-4 py-2 text-ink-soft">
                {r.course_code}
                <span className="ml-1 text-ink-faint">· {r.section}</span>
              </td>
              <td className="px-4 py-2">
                <StatusBadge status={r.status} lateMinutes={r.late_minutes} />
              </td>
              <td className="whitespace-nowrap px-4 py-2 text-ink-faint">
                {r.checked_by ? `${r.checked_by} · ${r.checked_at}` : "—"}
              </td>
              <td className="px-4 py-2">
                <div className="flex flex-wrap items-center gap-1.5">
                  {r.is_makeup ? <RescheduledTag from={r.rescheduled_from} /> : null}
                  {r.rescheduled_to ? <MovedToTag to={r.rescheduled_to} /> : null}
                  {r.remark ? <span className="text-xs text-ink-faint">{r.remark}</span> : null}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
