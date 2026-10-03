"use client";

import { useEffect, useState } from "react";
import { Field, inputClass } from "@/components/ui";
import { api, todayISO } from "@/lib/api";
import type { ReportPeriod, ReportSemester, Term } from "@/lib/types";

export type PeriodMode = "month" | "semester" | "custom";

export interface Period {
  mode: PeriodMode;
  from: string;
  to: string;
  /** Semester mode: the report is this term of this semester. */
  semester?: number;
  term?: Term;
  /** "September 2026", "Fall 2026 · Till mid-term", or the two dates. */
  label: string;
}

/**
 * What to ask the API for. A term is sent as itself rather than as its dates:
 * it also decides the minimum number of classes a course is held to.
 */
export const periodQuery = (p: Period): ReportPeriod =>
  p.mode === "semester" && p.semester != null && p.term
    ? { semester: p.semester, term: p.term }
    : { from: p.from, to: p.to };

const lastDay = (month: string) => {
  const [y, m] = month.split("-").map(Number);
  return `${month}-${String(new Date(y, m, 0).getDate()).padStart(2, "0")}`;
};

/** Monthly and semester reports stop at today: what has happened so far. */
const upToToday = (to: string) => (to > todayISO() ? todayISO() : to);

const shortDate = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString([], { day: "numeric", month: "short" });

export function monthPeriod(month: string): Period {
  const from = `${month}-01`;
  return {
    mode: "month",
    from,
    to: upToToday(lastDay(month)),
    label: new Date(`${from}T00:00:00`).toLocaleDateString([], {
      month: "long",
      year: "numeric",
    }),
  };
}

export const currentMonthPeriod = () => monthPeriod(todayISO().slice(0, 7));

/** Which minimum a report holds courses to. Each term has its own share. */
export const minimumNote = (term: Term | null) =>
  term === "MID"
    ? "the minimum due by the mid-term"
    : term === "FINAL"
      ? "the minimum due between the mid-term and the final"
      : "the minimum for the semester";

/** The term to land on: the one asked for if it can be reported, else the whole semester. */
const termFor = (s: ReportSemester, wanted: Term | undefined): Term =>
  s.terms.find((t) => t.term === wanted)?.available ? (wanted as Term) : "FULL";

/**
 * Monthly, a term of a semester, or any two dates. A semester is reported till
 * the mid-term, from the mid-term to the final, or whole.
 */
export default function PeriodPicker({
  value,
  onChange,
}: {
  value: Period;
  onChange: (next: Period) => void;
}) {
  const [semesters, setSemesters] = useState<ReportSemester[]>([]);
  const [month, setMonth] = useState(value.from.slice(0, 7));

  useEffect(() => {
    api
      .reportSemesters()
      .then(setSemesters)
      .catch(() => setSemesters([]));
  }, []);

  const pick = (s: ReportSemester, term: Term) => {
    const span = s.terms.find((t) => t.term === term);
    if (!span?.available || !span.from || !span.to) return;
    onChange({
      mode: "semester",
      semester: s.id,
      term,
      from: span.from,
      to: upToToday(span.to),
      label: `${s.name} · ${span.label}`,
    });
  };

  // A semester set up ahead of time has nothing to report until it begins.
  const begun = semesters.filter((s) => s.terms.some((t) => t.available));
  const selected = semesters.find((s) => s.id === value.semester);

  const modes: { key: PeriodMode; label: string }[] = [
    { key: "month", label: "Monthly" },
    ...(begun.length ? [{ key: "semester" as const, label: "Semester" }] : []),
    { key: "custom", label: "Custom" },
  ];

  const undated = selected?.terms.filter((t) => t.term !== "FULL" && t.from == null) ?? [];

  return (
    <div className="flex flex-wrap items-end gap-3">
      <div>
        <span className="mb-1 block text-sm font-medium text-ink-soft">Period</span>
        <Segmented
          options={modes.map((m) => ({ key: m.key, label: m.label }))}
          active={value.mode}
          onPick={(key) => {
            if (key === "month") onChange(monthPeriod(month));
            else if (key === "semester") {
              const s = selected ?? begun.find((x) => x.is_active) ?? begun[0];
              pick(s, termFor(s, value.term));
            } else onChange({ mode: "custom", from: value.from, to: value.to, label: "Custom range" });
          }}
        />
      </div>

      {value.mode === "month" ? (
        <Field label="Month">
          <input
            type="month"
            className={inputClass}
            value={month}
            max={todayISO().slice(0, 7)}
            onChange={(e) => {
              if (!e.target.value) return;
              setMonth(e.target.value);
              onChange(monthPeriod(e.target.value));
            }}
          />
        </Field>
      ) : value.mode === "semester" ? (
        <>
          <Field label="Semester">
            <select
              className={inputClass}
              value={value.semester ?? ""}
              onChange={(e) => {
                const s = semesters.find((x) => x.id === Number(e.target.value));
                if (s) pick(s, termFor(s, value.term));
              }}
            >
              {semesters.map((s) => {
                const open = begun.includes(s);
                return (
                  <option key={s.id} value={s.id} disabled={!open}>
                    {s.name}
                    {s.is_active ? " (current)" : ""}
                    {open ? "" : " (not begun)"}
                  </option>
                );
              })}
            </select>
          </Field>
          {selected ? (
            <div>
              <span className="mb-1 block text-sm font-medium text-ink-soft">Term</span>
              <Segmented
                options={selected.terms.map((t) => ({
                  key: t.term,
                  label: t.label,
                  disabled: !t.available,
                  title: t.from == null
                    ? "Its exam dates are not set yet"
                    : t.available
                      ? `${shortDate(t.from)} – ${shortDate(t.to ?? t.from)}`
                      : `Begins ${shortDate(t.from)}`,
                }))}
                active={value.term ?? "FULL"}
                onPick={(term) => pick(selected, term)}
              />
            </div>
          ) : null}
          {undated.length ? (
            <p className="basis-full text-xs text-ink-faint">
              {selected?.name} has no mid-term exam dates yet, so only the full semester can be
              reported. An administrator sets them under Administration → Semesters.
            </p>
          ) : null}
        </>
      ) : (
        <>
          <Field label="From">
            <input
              type="date"
              className={inputClass}
              value={value.from}
              onChange={(e) =>
                e.target.value && onChange({ ...value, from: e.target.value })
              }
            />
          </Field>
          <Field label="To">
            <input
              type="date"
              className={inputClass}
              value={value.to}
              onChange={(e) => e.target.value && onChange({ ...value, to: e.target.value })}
            />
          </Field>
        </>
      )}
    </div>
  );
}

function Segmented<K extends string>({
  options,
  active,
  onPick,
}: {
  options: { key: K; label: string; disabled?: boolean; title?: string }[];
  active: K;
  onPick: (key: K) => void;
}) {
  return (
    <div className="flex flex-wrap rounded-lg bg-canvas p-0.5 ring-1 ring-inset ring-line">
      {options.map((o) => (
        <button
          key={o.key}
          type="button"
          disabled={o.disabled}
          title={o.title}
          onClick={() => onPick(o.key)}
          className={`rounded-md px-3 py-1.5 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-40 ${
            active === o.key ? "bg-surface text-brand shadow-sm" : "text-ink-soft"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
