"use client";

import { useEffect, useState } from "react";
import { ErrorNote } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import type { ConflictReport, FreeRoom } from "@/lib/types";

/** The empty rooms of one cell, reloaded whenever the cell changes -- or
 *  `refresh` does, e.g. after a booking took one. Null until there is a cell to
 *  ask about, or while `enabled` is false. */
export function useFreeRooms(date: string, slot: string, enabled = true, refresh = 0) {
  const [rooms, setRooms] = useState<FreeRoom[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled || !date || !slot) {
      setRooms(null);
      return;
    }
    let alive = true;
    setLoading(true);
    setError(null);
    api
      .freeRooms(date, slot)
      .then((r) => {
        if (alive) setRooms(r);
      })
      .catch((err) => {
        if (!alive) return;
        setRooms([]);
        setError(err instanceof ApiError ? err.message : "Could not load empty rooms.");
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [enabled, date, slot, refresh]);

  return { rooms, loading, error };
}

/**
 * Pick one empty room, offered as large tiles a teacher can hit on a phone.
 * `roomType` narrows the list to rooms like the class usually meets in, with a
 * box to show every type.
 */
export function RoomPicker({
  date,
  rooms,
  loading,
  error,
  room,
  onPick,
  roomType,
}: {
  date: string;
  rooms: FreeRoom[] | null;
  loading: boolean;
  error: string | null;
  room: string;
  onPick: (room: string) => void;
  roomType?: string | null;
}) {
  const [sameType, setSameType] = useState(true);

  // A room picked for one slot may be taken in the next.
  useEffect(() => {
    if (rooms && room && !rooms.some((r) => r.room === room)) onPick("");
  }, [rooms, room, onPick]);

  const narrowed = sameType && !!roomType;
  const shown = rooms?.filter((r) => !narrowed || r.room_type === roomType) ?? [];
  const typeLabel = roomType?.toLowerCase() ?? "";

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <span className="text-base font-semibold">Empty room{room ? ` · ${room}` : ""}</span>
        {roomType ? (
          <label className="flex items-center gap-2 text-base text-ink-soft">
            <input
              type="checkbox"
              className="size-5 accent-brand"
              checked={sameType}
              onChange={(e) => setSameType(e.target.checked)}
            />
            Only {typeLabel} rooms
          </label>
        ) : null}
      </div>

      {error ? (
        <ErrorNote message={error} />
      ) : !date ? (
        <p className="rounded-xl bg-canvas px-4 py-3 text-base text-ink-soft">
          Pick a date and time to see which rooms are empty.
        </p>
      ) : loading ? (
        <p className="text-base text-ink-faint">Finding empty rooms…</p>
      ) : shown.length === 0 ? (
        <p className="rounded-xl bg-canvas px-4 py-3 text-base text-ink-soft">
          No empty {narrowed ? `${typeLabel} ` : ""}rooms at this time. Try another time
          {narrowed ? " or include every room type" : ""}.
        </p>
      ) : (
        <div className="grid max-h-96 grid-cols-2 gap-2 overflow-y-auto p-0.5 sm:grid-cols-4">
          {shown.map((r) => {
            const on = room === r.room;
            return (
              <button
                key={r.room}
                type="button"
                aria-pressed={on}
                onClick={() => onPick(r.room)}
                className={`min-h-16 rounded-xl px-3 py-2 text-left ring-2 ring-inset transition-colors ${
                  on
                    ? "bg-brand text-white ring-brand"
                    : "bg-surface text-ink ring-line hover:bg-canvas"
                }`}
              >
                <span className="block text-lg font-bold">{r.room}</span>
                <span className="block text-sm opacity-80">
                  {r.zone}
                  {narrowed ? "" : ` · ${r.room_type}`}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

/** What stands in the way of a proposed time: room, teacher, section, holiday. */
export function ConflictList({ report }: { report: ConflictReport }) {
  return (
    <div className="rounded-xl border-2 border-bad/30 bg-bad-soft px-4 py-3">
      <p className="text-lg font-bold text-bad">
        {report.conflicts.length} conflict{report.conflicts.length === 1 ? "" : "s"}
      </p>
      <ul className="mt-1 space-y-1">
        {report.conflicts.map((c, i) => (
          <li key={i} className="text-base text-bad">
            <span className="font-semibold">{c.type}:</span> {c.message}
          </li>
        ))}
      </ul>
    </div>
  );
}
