"use client";

import { useEffect, useState } from "react";
import { Field, inputClass } from "@/components/ui";
import { api, todayISO } from "@/lib/api";
import type { Semester } from "@/lib/types";

export type PeriodMode = "month" | "semester" | "custom";

export interface Period {
  mode: PeriodMode;
  from: string;
  to: string;
  /** "September 2026", "Fall 2026", or the two dates. */
  label: string;
}

const lastDay = (month: string) => {
  const [y, m] = month.split("-").map(Number);
  return `${month}-${String(new Date(y, m, 0).getDate()).padStart(2, "0")}`;
};

/** Monthly and semester reports stop at today: what has happened so far. */
const upToToday = (to: string) => (to > todayISO() ? todayISO() : to);

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

/**
 * Monthly, semester, or any two dates. The semester list is admin-only, so a
 * teacher simply does not see that option.
 */
export default function PeriodPicker({
  value,
  onChange,
}: {
  value: Period;
  onChange: (next: Period) => void;
}) {
  const [semesters, setSemesters] = useState<Semester[]>([]);
  const [month, setMonth] = useState(value.from.slice(0, 7));
  const [semesterId, setSemesterId] = useState<number | null>(null);

  useEffect(() => {
    api
      .semesters()
      .then(setSemesters)
      .catch(() => setSemesters([]));
  }, []);

  const pickSemester = (id: number) => {
    const s = semesters.find((x) => x.id === id);
    if (!s) return;
    setSemesterId(id);
    onChange({ mode: "semester", from: s.start_date, to: upToToday(s.end_date), label: s.name });
  };

  const modes: { key: PeriodMode; label: string }[] = [
    { key: "month", label: "Monthly" },
    ...(semesters.length ? [{ key: "semester" as const, label: "Semester" }] : []),
    { key: "custom", label: "Custom" },
  ];

  return (
    <div className="flex flex-wrap items-end gap-3">
      <div>
        <span className="mb-1 block text-sm font-medium text-ink-soft">Period</span>
        <div className="flex rounded-lg bg-canvas p-0.5 ring-1 ring-inset ring-line">
          {modes.map((m) => (
            <button
              key={m.key}
              type="button"
              onClick={() => {
                if (m.key === "month") onChange(monthPeriod(month));
                else if (m.key === "semester") {
                  const active = semesters.find((s) => s.is_active) ?? semesters[0];
                  pickSemester(semesterId ?? active.id);
                } else onChange({ ...value, mode: "custom", label: "Custom range" });
              }}
              className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                value.mode === m.key ? "bg-surface text-brand shadow-sm" : "text-ink-soft"
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
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
        <Field label="Semester">
          <select
            className={inputClass}
            value={semesterId ?? ""}
            onChange={(e) => pickSemester(Number(e.target.value))}
          >
            {semesters.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
                {s.is_active ? " (current)" : ""}
              </option>
            ))}
          </select>
        </Field>
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
