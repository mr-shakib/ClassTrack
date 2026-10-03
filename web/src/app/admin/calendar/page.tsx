"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Button,
  Card,
  EmptyState,
  ErrorNote,
  Field,
  Spinner,
  inputClass,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { MANAGEMENT_ROLES, useRequireRole } from "@/lib/auth";
import type { Holiday, Semester } from "@/lib/types";

const KINDS = ["HOLIDAY", "EXAM", "CLOSED", "SPECIAL"] as const;

export default function CalendarPage() {
  const { permitted, loading: authLoading } = useRequireRole(MANAGEMENT_ROLES);
  const [rows, setRows] = useState<Holiday[]>([]);
  const [semesters, setSemesters] = useState<Semester[]>([]);
  /** Whose calendar is shown and added to. Defaults to the current semester. */
  const [semesterId, setSemesterId] = useState<number | null>(null);
  const [date, setDate] = useState("");
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<string>("HOLIDAY");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!permitted) return;
    api
      .semesters()
      .then((ss) => {
        setSemesters(ss);
        setSemesterId(ss.find((s) => s.is_active)?.id ?? ss[0]?.id ?? null);
      })
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Could not load the semesters."),
      );
  }, [permitted]);

  const load = useCallback(async () => {
    if (semesterId == null) return;
    try {
      setRows(await api.holidays(semesterId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the calendar.");
    }
  }, [semesterId]);

  useEffect(() => {
    void load();
  }, [load]);

  const semester = semesters.find((s) => s.id === semesterId);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await api.addHoliday({ date, title, kind, semester_id: semesterId ?? undefined });
      setDate("");
      setTitle("");
      setNotice(
        kind === "SPECIAL"
          ? "Added."
          : "Added. Upcoming classes on that day are off the schedule.",
      );
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not add the day.");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: number) => {
    setBusy(true);
    setError(null);
    try {
      setNotice((await api.removeHoliday(id)).detail);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not remove the day.");
    } finally {
      setBusy(false);
    }
  };

  if (authLoading || !permitted) return <Spinner />;

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold">Add a calendar day</h2>
            <p className="mt-1 text-sm text-ink-soft">
              Holidays and closed days take a day&apos;s classes off the schedule at once.
              A special day does not. The mid-term and final exams are set on the
              Semesters tab.
            </p>
          </div>
          {semesters.length > 1 ? (
            <Field label="Semester">
              <select
                className={inputClass}
                value={semesterId ?? ""}
                onChange={(e) => setSemesterId(Number(e.target.value))}
              >
                {semesters.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                    {s.is_active ? " (current)" : ""}
                  </option>
                ))}
              </select>
            </Field>
          ) : null}
        </div>
        <form onSubmit={add} className="mt-3 flex flex-wrap items-end gap-3">
          <Field label="Date">
            <input
              type="date"
              className={inputClass}
              value={date}
              min={semester?.start_date}
              max={semester?.end_date}
              onChange={(e) => setDate(e.target.value)}
              required
            />
          </Field>
          <Field label="Title">
            <input
              className={inputClass}
              placeholder="e.g. Victory Day"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
          </Field>
          <Field label="Kind">
            <select
              className={inputClass}
              value={kind}
              onChange={(e) => setKind(e.target.value)}
            >
              {KINDS.map((k) => (
                <option key={k} value={k}>
                  {k.toLowerCase()}
                </option>
              ))}
            </select>
          </Field>
          <Button type="submit" disabled={busy || semesterId == null}>
            Add
          </Button>
        </form>
      </Card>

      {error ? <ErrorNote message={error} /> : null}
      {notice ? (
        <div className="rounded-lg border border-warn/20 bg-warn-soft px-3 py-2 text-sm text-warn">
          {notice}
        </div>
      ) : null}

      <Card>
        <div className="border-b border-line px-4 py-3">
          <h2 className="text-sm font-semibold">
            {semester ? `${semester.name} calendar` : "Academic calendar"} ({rows.length})
          </h2>
          {semester ? (
            <p className="text-xs text-ink-faint">
              {semester.start_date} to {semester.end_date} · mid-term exams{" "}
              {semester.mid_exam_start && semester.mid_exam_end
                ? `${semester.mid_exam_start} to ${semester.mid_exam_end}`
                : "not set"}{" "}
              · final exams from {semester.final_exam_start ?? "not set"}
            </p>
          ) : null}
        </div>
        {rows.length === 0 ? (
          <EmptyState
            title="No calendar entries"
            body="Every working day currently generates classes."
          />
        ) : (
          <ul className="divide-y divide-line">
            {rows.map((h) => (
              <li key={h.id} className="flex items-center gap-3 px-4 py-2.5">
                <span className="w-28 shrink-0 text-sm tabular-nums">{h.date}</span>
                <span className="min-w-0 flex-1 truncate text-sm">{h.title}</span>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                    h.kind === "SPECIAL"
                      ? "bg-info-soft text-info"
                      : "bg-bad-soft text-bad"
                  }`}
                >
                  {h.kind.toLowerCase()}
                </span>
                <Button variant="ghost" onClick={() => remove(h.id)} disabled={busy}>
                  Remove
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
