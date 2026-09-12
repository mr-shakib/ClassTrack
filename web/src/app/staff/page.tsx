"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import RoomCard from "@/components/RoomCard";
import { Card, EmptyState, ErrorNote, Spinner } from "@/components/ui";
import { SLOTS, api, todayISO } from "@/lib/api";
import { useAuth, useRequireRole } from "@/lib/auth";
import type { CheckingScreen, RoomRow } from "@/lib/types";

const SLOT_STATE_COPY: Record<string, { label: string; className: string }> = {
  UPCOMING: { label: "Not started", className: "bg-canvas text-ink-soft" },
  ONGOING: { label: "Open for checking", className: "bg-ok-soft text-ok" },
  CLOSED: { label: "Checking window closed", className: "bg-gap-soft text-gap" },
};

export default function StaffPage() {
  const { permitted, loading: authLoading } = useRequireRole([
    "STAFF",
    "HOD",
    "SUPER_ADMIN",
  ]);
  const { user } = useAuth();
  // Staff are bound by the checking window; an admin may correct afterwards.
  const canOverride = user?.role === "HOD" || user?.role === "SUPER_ADMIN";
  const isStaff = user?.role === "STAFF";

  const [date, setDate] = useState(todayISO());
  const [slot, setSlot] = useState<string | null>(null);
  const [screen, setScreen] = useState<CheckingScreen | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (showSpinner = false) => {
      if (showSpinner) setLoading(true);
      try {
        const data = await api.checkingRooms(date, slot ?? undefined);
        setScreen(data);
        // First load: adopt whatever slot the backend decided is current.
        if (slot == null) setSlot(data.time_slot);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not load classes.");
      } finally {
        setLoading(false);
      }
    },
    [date, slot],
  );

  useEffect(() => {
    if (!permitted) return;
    void load(true);
    // Refresh so a second staff member's checks show up without a reload.
    const timer = setInterval(() => void load(false), 30_000);
    return () => clearInterval(timer);
  }, [permitted, load]);

  const patchRow = (instanceId: number, next: Partial<RoomRow>) => {
    setScreen((prev) =>
      prev
        ? {
            ...prev,
            rooms: prev.rooms.map((r) =>
              r.instance_id === instanceId ? { ...r, ...next } : r,
            ),
          }
        : prev,
    );
  };

  const { pending, done } = useMemo(() => {
    const rooms = screen?.rooms ?? [];
    return {
      pending: rooms.filter((r) => r.check == null),
      done: rooms.filter((r) => r.check != null),
    };
  }, [screen]);

  if (authLoading || !permitted) return <Spinner />;

  const slotIndex = slot ? SLOTS.indexOf(slot as (typeof SLOTS)[number]) : -1;
  const state = screen ? SLOT_STATE_COPY[screen.slot_state] : null;
  const locked = screen ? screen.slot_state !== "ONGOING" : false;
  // A staff member with no floor has no workload -- say that, rather than
  // letting it read as "nothing is scheduled today".
  const noFloor = isStaff && screen != null && screen.zones.length === 0;

  return (
    <div className="space-y-4">
      <div className="rounded-2xl bg-brand px-4 py-4 text-white">
        <div className="flex items-end justify-between gap-3">
          <div>
            <p className="text-sm font-medium opacity-80">
              {new Date(`${date}T00:00:00`).toLocaleDateString([], {
                weekday: "long",
                day: "numeric",
                month: "short",
              })}
            </p>
            <p className="text-3xl font-bold tabular-nums">{slot ?? "—"}</p>
          </div>
          {screen ? (
            <div className="text-right">
              <p className="text-4xl font-bold tabular-nums">
                {done.length}
                <span className="text-2xl opacity-70">/{screen.rooms.length}</span>
              </p>
              <p className="text-sm font-medium opacity-80">rooms done</p>
            </div>
          ) : null}
        </div>
        {screen && screen.rooms.length > 0 ? (
          <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-white/25">
            <div
              className="h-full rounded-full bg-white transition-all duration-300"
              style={{ width: `${(done.length / screen.rooms.length) * 100}%` }}
            />
          </div>
        ) : null}
      </div>

      {/* Slot and date controls. Deliberately compact: the room cards are what
          matters on a phone. */}
      <div className="flex items-stretch gap-2">
        <button
          onClick={() => slotIndex > 0 && setSlot(SLOTS[slotIndex - 1])}
          disabled={slotIndex <= 0}
          className="min-h-14 min-w-14 rounded-xl bg-surface text-2xl font-bold text-ink-soft ring-2 ring-inset ring-line disabled:opacity-30"
          aria-label="Previous time"
        >
          ‹
        </button>
        <select
          value={slot ?? ""}
          onChange={(e) => setSlot(e.target.value)}
          className="min-h-14 flex-1 rounded-xl border-2 border-line bg-surface px-3 text-center text-lg font-bold tabular-nums"
          aria-label="Time"
        >
          {SLOTS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <button
          onClick={() =>
            slotIndex >= 0 && slotIndex < SLOTS.length - 1 && setSlot(SLOTS[slotIndex + 1])
          }
          disabled={slotIndex < 0 || slotIndex >= SLOTS.length - 1}
          className="min-h-14 min-w-14 rounded-xl bg-surface text-2xl font-bold text-ink-soft ring-2 ring-inset ring-line disabled:opacity-30"
          aria-label="Next time"
        >
          ›
        </button>
      </div>

      {state && screen && screen.slot_state === "ONGOING" ? (
        <p className="text-center text-base font-semibold text-ok">
          Open until{" "}
          {new Date(screen.window_closes_at).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-2">
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="min-h-12 rounded-xl border-2 border-line bg-surface px-3 text-base"
        />
        {screen && screen.zones.length > 0 ? (
          <span className="text-base font-medium text-ink-soft">
            Your floors: {screen.zones.join(", ")}
          </span>
        ) : null}
      </div>

      {error ? <ErrorNote message={error} /> : null}

      {noFloor ? (
        <div className="rounded-2xl border-2 border-warn/30 bg-warn-soft px-4 py-4 text-lg font-semibold text-warn">
          No floor assigned to you yet. Ask the office to assign your floor.
        </div>
      ) : null}

      {screen && locked && !noFloor ? (
        <div
          className={`rounded-2xl border-2 px-4 py-4 text-lg font-semibold ${
            screen.slot_state === "CLOSED"
              ? "border-gap/30 bg-gap-soft text-gap"
              : "border-line bg-canvas text-ink-soft"
          }`}
        >
          {screen.slot_state === "CLOSED"
            ? "This time is over. Anything not reported counts as missed."
            : `This class has not started yet. It opens at ${
                screen.rooms[0]?.scheduled_start ?? screen.time_slot.split("-")[0]
              }.`}
        </div>
      ) : null}

      {loading ? (
        <Spinner label="Loading classes…" />
      ) : screen && screen.rooms.length === 0 ? (
        <Card>
          <EmptyState
            title={noFloor ? "No floor assigned" : "No classes in this slot"}
            body={
              noFloor
                ? "Ask an administrator to assign your floor."
                : screen.zones.length > 0
                  ? `Nothing scheduled on your floors (${screen.zones.join(", ")}) in this slot.`
                  : "Nothing is scheduled here, or the routine has no entry for this day."
            }
          />
        </Card>
      ) : (
        <>
          {pending.length > 0 ? (
            <section className="space-y-2.5">
              <h2 className="text-xl font-bold">
                {locked ? "Not reported" : "To do"}{" "}
                <span className="text-ink-faint">({pending.length})</span>
              </h2>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {pending.map((row) => (
                  <RoomCard
                    key={row.instance_id}
                    row={row}
                    locked={locked}
                    canOverride={canOverride}
                    onChanged={(next) => patchRow(row.instance_id, next)}
                  />
                ))}
              </div>
            </section>
          ) : null}

          {pending.length === 0 && done.length > 0 && !locked ? (
            <div className="rounded-2xl bg-ok px-4 py-6 text-center text-white">
              <p className="text-2xl font-bold">All rooms done</p>
              <p className="mt-1 text-base opacity-90">
                Nothing left for this time.
              </p>
            </div>
          ) : null}

          {done.length > 0 ? (
            <section className="space-y-2.5">
              <h2 className="text-xl font-bold text-ok">
                Done <span className="text-ink-faint">({done.length})</span>
              </h2>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {done.map((row) => (
                  <RoomCard
                    key={row.instance_id}
                    row={row}
                    locked={locked}
                    canOverride={canOverride}
                    onChanged={(next) => patchRow(row.instance_id, next)}
                  />
                ))}
              </div>
            </section>
          ) : null}
        </>
      )}
    </div>
  );
}
