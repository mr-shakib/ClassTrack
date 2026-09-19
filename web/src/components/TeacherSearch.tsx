"use client";

import { useMemo, useState } from "react";
import RoomCard from "@/components/RoomCard";
import { shortDay } from "@/components/Rescheduled";
import { Card, EmptyState, ErrorNote, Spinner } from "@/components/ui";
import { api, todayISO } from "@/lib/api";
import type { RoomRow } from "@/lib/types";

const daysAgo = (n: number) => {
  const d = new Date(`${todayISO()}T00:00:00`);
  d.setDate(d.getDate() - n);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

/**
 * Find a teacher's classes by initial, to correct a past record without
 * walking back through each day, slot and floor. Each card locks by its own
 * day: staff can still change today's, admins and the committee any day's.
 */
export default function TeacherSearch({ canOverride }: { canOverride: boolean }) {
  const [initial, setInitial] = useState("");
  const [from, setFrom] = useState(daysAgo(14));
  const [to, setTo] = useState(todayISO());
  const [rows, setRows] = useState<RoomRow[] | null>(null);
  const [searched, setSearched] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = async () => {
    const q = initial.trim().toUpperCase();
    if (!q) return;
    setLoading(true);
    setError(null);
    try {
      setRows(await api.searchChecking(q, from, to));
      setSearched(q);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not search.");
    } finally {
      setLoading(false);
    }
  };

  const patch = (id: number, next: Partial<RoomRow>) =>
    setRows((prev) => prev?.map((r) => (r.instance_id === id ? { ...r, ...next } : r)) ?? prev);

  const byDay = useMemo(() => {
    const groups = new Map<string, RoomRow[]>();
    for (const r of rows ?? []) {
      const key = r.date ?? "";
      groups.set(key, [...(groups.get(key) ?? []), r]);
    }
    return [...groups.entries()];
  }, [rows]);

  return (
    <section className="space-y-4">
      <form
        className="space-y-3 rounded-2xl border-2 border-line bg-surface p-4"
        onSubmit={(e) => {
          e.preventDefault();
          void search();
        }}
      >
        <label className="block">
          <span className="mb-1.5 block text-base font-semibold">Teacher initial</span>
          <input
            value={initial}
            onChange={(e) => setInitial(e.target.value.toUpperCase())}
            placeholder="e.g. SRH"
            autoCapitalize="characters"
            autoFocus
            className="min-h-14 w-full rounded-xl border-2 border-line px-4 text-2xl font-bold uppercase tracking-wider placeholder:font-normal placeholder:tracking-normal"
          />
        </label>
        <div className="grid grid-cols-2 gap-2">
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-ink-soft">From</span>
            <input type="date" value={from} max={to} onChange={(e) => e.target.value && setFrom(e.target.value)}
              className="min-h-12 w-full rounded-xl border-2 border-line px-3 text-base" />
          </label>
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-ink-soft">To</span>
            <input type="date" value={to} min={from} onChange={(e) => e.target.value && setTo(e.target.value)}
              className="min-h-12 w-full rounded-xl border-2 border-line px-3 text-base" />
          </label>
        </div>
        <button
          type="submit"
          disabled={loading || !initial.trim()}
          className="min-h-14 w-full rounded-xl bg-brand text-lg font-bold text-white disabled:opacity-50"
        >
          {loading ? "Searching…" : "Find classes"}
        </button>
        {!canOverride ? (
          <p className="text-sm text-ink-soft">
            You can change today&apos;s classes. Older ones are shown for reference.
          </p>
        ) : null}
      </form>

      {error ? <ErrorNote message={error} /> : null}

      {loading ? (
        <Spinner label="Searching…" />
      ) : rows == null ? null : rows.length === 0 ? (
        <Card>
          <EmptyState
            title={`No classes for ${searched}`}
            body="Check the initial, or widen the dates."
          />
        </Card>
      ) : (
        <>
          <p className="text-base text-ink-soft">
            <span className="font-bold text-ink">{rows.length}</span> classes for{" "}
            <span className="font-bold text-ink">{searched}</span>
            {rows[0]?.teacher_name ? ` · ${rows[0].teacher_name}` : ""}, newest first
          </p>
          {byDay.map(([day, list]) => (
            <div key={day} className="space-y-2.5">
              <h3 className="text-xl font-bold">{day ? shortDay(day) : "—"}</h3>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {list.map((row) => (
                  <RoomCard
                    key={row.instance_id}
                    row={row}
                    showWhen
                    locked={row.slot_state !== "ONGOING"}
                    canOverride={canOverride}
                    onChanged={(next) => patch(row.instance_id, next)}
                  />
                ))}
              </div>
            </div>
          ))}
        </>
      )}
    </section>
  );
}
