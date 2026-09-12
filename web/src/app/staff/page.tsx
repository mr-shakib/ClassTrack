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

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Room checking</h1>
        <p className="mt-0.5 text-sm text-ink-soft">
          Tap once for a class that is running.
          {screen && screen.zones.length > 0
            ? " Showing only the floors assigned to you."
            : ""}
        </p>
      </div>

      {/* Slot and date controls. Deliberately compact: the room cards are what
          matters on a phone. */}
      <Card className="p-3">
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="rounded-lg border border-line px-2.5 py-2 text-sm"
          />
          <div className="flex items-center gap-1">
            <button
              onClick={() => slotIndex > 0 && setSlot(SLOTS[slotIndex - 1])}
              disabled={slotIndex <= 0}
              className="min-h-10 rounded-lg px-2.5 text-sm font-medium text-ink-soft ring-1 ring-inset ring-line disabled:opacity-40"
              aria-label="Previous slot"
            >
              ‹
            </button>
            <select
              value={slot ?? ""}
              onChange={(e) => setSlot(e.target.value)}
              className="min-h-10 rounded-lg border border-line px-2.5 text-sm font-medium tabular-nums"
            >
              {SLOTS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
            <button
              onClick={() =>
                slotIndex >= 0 &&
                slotIndex < SLOTS.length - 1 &&
                setSlot(SLOTS[slotIndex + 1])
              }
              disabled={slotIndex < 0 || slotIndex >= SLOTS.length - 1}
              className="min-h-10 rounded-lg px-2.5 text-sm font-medium text-ink-soft ring-1 ring-inset ring-line disabled:opacity-40"
              aria-label="Next slot"
            >
              ›
            </button>
          </div>

          {state ? (
            <span
              className={`ml-auto rounded-full px-2.5 py-1 text-xs font-semibold ${state.className}`}
            >
              {state.label}
            </span>
          ) : null}
        </div>

        {screen ? (
          <p className="mt-2 text-xs text-ink-faint">
            {done.length} of {screen.rooms.length} checked
            {screen.slot_state === "ONGOING"
              ? ` · window closes ${new Date(screen.window_closes_at).toLocaleTimeString(
                  [],
                  { hour: "2-digit", minute: "2-digit" },
                )}`
              : ""}
            {screen.zones.length > 0
              ? ` · your floors: ${screen.zones.join(", ")}`
              : ""}
          </p>
        ) : null}
      </Card>

      {error ? <ErrorNote message={error} /> : null}

      {screen && locked ? (
        <div
          className={`rounded-lg border px-3 py-2.5 text-sm ${
            screen.slot_state === "CLOSED"
              ? "border-gap/20 bg-gap-soft text-gap"
              : "border-line bg-canvas text-ink-soft"
          }`}
        >
          {screen.slot_state === "CLOSED" ? (
            <>
              <strong>The checking window for this slot has closed.</strong>{" "}
              Anything still unchecked is recorded as Not Checked.
              {canOverride ? " You can correct a record from here." : ""}
            </>
          ) : (
            <>
              <strong>This slot has not started yet.</strong> Checking opens at{" "}
              {screen.rooms[0]?.scheduled_start ?? screen.time_slot.split("-")[0]}.
            </>
          )}
        </div>
      ) : null}

      {loading ? (
        <Spinner label="Loading classes…" />
      ) : screen && screen.rooms.length === 0 ? (
        <Card>
          <EmptyState
            title="No classes in this slot"
            body={
              screen.zones.length > 0
                ? `Nothing scheduled on your floors (${screen.zones.join(", ")}) in this slot.`
                : "Nothing is scheduled here, or the routine has no entry for this day."
            }
          />
        </Card>
      ) : (
        <>
          {pending.length > 0 ? (
            <section className="space-y-2.5">
              <h2 className="text-sm font-semibold text-ink-soft">
                {locked
                  ? `Not checked (${pending.length})`
                  : `Needs checking (${pending.length})`}
              </h2>
              <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
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

          {done.length > 0 ? (
            <section className="space-y-2.5">
              <h2 className="text-sm font-semibold text-ink-soft">
                Checked ({done.length})
              </h2>
              <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
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
