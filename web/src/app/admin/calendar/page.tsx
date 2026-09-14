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
import { ADMIN_ROLES, useRequireRole } from "@/lib/auth";
import type { Holiday } from "@/lib/types";

const KINDS = ["HOLIDAY", "EXAM", "CLOSED", "SPECIAL"] as const;

export default function CalendarPage() {
  const { permitted, loading: authLoading } = useRequireRole(ADMIN_ROLES);
  const [rows, setRows] = useState<Holiday[]>([]);
  const [date, setDate] = useState("");
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<string>("HOLIDAY");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setRows(await api.holidays());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the calendar.");
    }
  }, []);

  useEffect(() => {
    if (permitted) void load();
  }, [permitted, load]);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await api.addHoliday({ date, title, kind });
      setDate("");
      setTitle("");
      setNotice("Added. Re-run instance generation to apply it to the schedule.");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not add the day.");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: number) => {
    setBusy(true);
    try {
      await api.removeHoliday(id);
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
        <h2 className="text-sm font-semibold">Add a calendar day</h2>
        <p className="mt-1 text-sm text-ink-soft">
          Holidays, exam periods and closed days stop class instances being
          generated. A special day does not.
        </p>
        <form onSubmit={add} className="mt-3 flex flex-wrap items-end gap-3">
          <Field label="Date">
            <input
              type="date"
              className={inputClass}
              value={date}
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
          <Button type="submit" disabled={busy}>
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
          <h2 className="text-sm font-semibold">Academic calendar ({rows.length})</h2>
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
