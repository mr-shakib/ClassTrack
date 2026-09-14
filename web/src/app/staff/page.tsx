"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import RoomCard from "@/components/RoomCard";
import { Card, EmptyState, ErrorNote, Spinner } from "@/components/ui";
import { SLOTS, api, todayISO } from "@/lib/api";
import { CHECKING_ROLES, OVERRIDE_ROLES, useAuth, useRequireRole } from "@/lib/auth";
import type { CheckingScreen, FloorSummary, RoomRow } from "@/lib/types";

const SLOT_STATE_COPY: Record<string, { label: string; className: string }> = {
  UPCOMING: { label: "Not started", className: "bg-canvas text-ink-soft" },
  ONGOING: { label: "Open for checking", className: "bg-ok-soft text-ok" },
  CLOSED: { label: "Reporting closed for the day", className: "bg-gap-soft text-gap" },
};

/**
 * Room-wise checking, in two steps: pick a floor, then check its classes.
 *
 * Every floor is offered to everyone. A staff member's assigned floors come
 * first and are marked, but anyone passing another floor can check it too.
 */
export default function StaffPage() {
  const { permitted, loading: authLoading } = useRequireRole(CHECKING_ROLES);
  const { user } = useAuth();
  // Staff can report until the end of the class's day; an admin or the
  // committee may correct it afterwards.
  const canOverride = user != null && OVERRIDE_ROLES.includes(user.role);

  const [date, setDate] = useState(todayISO());
  const [slot, setSlot] = useState<string | null>(null);
  const [floor, setFloor] = useState<{ key: string; label: string } | null>(null);
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

  // Counted from the rooms rather than taken from the server's summary, so a
  // check saved on this screen moves the floor's count straight away.
  const floors = useMemo<FloorSummary[]>(() => {
    const rooms = screen?.rooms ?? [];
    return (screen?.floors ?? []).map((f) => {
      const onFloor = rooms.filter((r) => r.zone_key === f.key);
      return {
        ...f,
        total: onFloor.length,
        checked: onFloor.filter((r) => r.check != null).length,
      };
    });
  }, [screen]);

  const { rooms, pending, done } = useMemo(() => {
    const all = screen?.rooms ?? [];
    const shown = floor ? all.filter((r) => r.zone_key === floor.key) : all;
    return {
      rooms: shown,
      pending: shown.filter((r) => r.check == null),
      done: shown.filter((r) => r.check != null),
    };
  }, [screen, floor]);

  const openFloor = (next: { key: string; label: string } | null) => {
    setFloor(next);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  if (authLoading || !permitted) return <Spinner />;

  const slotIndex = slot ? SLOTS.indexOf(slot as (typeof SLOTS)[number]) : -1;
  const state = screen ? SLOT_STATE_COPY[screen.slot_state] : null;
  const locked = screen ? screen.slot_state !== "ONGOING" : false;
  const closed = screen?.slot_state === "CLOSED";
  const selected = floor ? floors.find((f) => f.key === floor.key) ?? null : null;

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <div className="rounded-2xl bg-brand px-4 py-4 text-white">
        <div className="flex items-end justify-between gap-3">
          <div className="min-w-0">
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
            <div className="shrink-0 text-right">
              <p className="text-4xl font-bold tabular-nums">
                {done.length}
                <span className="text-2xl opacity-70">/{rooms.length}</span>
              </p>
              <p className="text-sm font-medium opacity-80">
                {floor ? "done on this floor" : "rooms done"}
              </p>
            </div>
          ) : null}
        </div>
        {screen && rooms.length > 0 ? (
          <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-white/25">
            <div
              className="h-full rounded-full bg-white transition-all duration-300"
              style={{ width: `${(done.length / rooms.length) * 100}%` }}
            />
          </div>
        ) : null}
      </div>

      {/* Slot and date controls. Deliberately compact: the cards are what
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
          You can report these classes any time today.
        </p>
      ) : null}

      <input
        type="date"
        value={date}
        onChange={(e) => setDate(e.target.value)}
        className="min-h-12 rounded-xl border-2 border-line bg-surface px-3 text-base"
        aria-label="Date"
      />

      {error ? <ErrorNote message={error} /> : null}

      {screen && locked ? (
        <div
          className={`rounded-2xl border-2 px-4 py-4 text-lg font-semibold ${
            closed ? "border-gap/30 bg-gap-soft text-gap" : "border-line bg-canvas text-ink-soft"
          }`}
        >
          {closed
            ? "This day is over. Classes nobody reported are recorded as not checked."
            : `This class has not started yet. It opens at ${
                screen.rooms[0]?.scheduled_start ?? screen.time_slot.split("-")[0]
              }.`}
        </div>
      ) : null}

      {loading ? (
        <Spinner label="Loading classes…" />
      ) : floor == null ? (
        // --- step 1: pick a floor --------------------------------------------
        floors.length === 0 ? (
          <Card>
            <EmptyState
              title="No classes in this slot"
              body="Nothing is scheduled here, or the routine has no entry for this day."
            />
          </Card>
        ) : (
          <section className="space-y-3">
            <div>
              <h2 className="text-2xl font-bold">Choose a floor</h2>
              <p className="mt-0.5 text-base text-ink-soft">
                Your floors come first. You can check classes on any floor.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {floors.map((f) => (
                <FloorCard
                  key={f.key}
                  floor={f}
                  closed={closed}
                  onOpen={() => openFloor({ key: f.key, label: f.label })}
                />
              ))}
            </div>
          </section>
        )
      ) : (
        // --- step 2: the classes on that floor -------------------------------
        <section className="space-y-4">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => openFloor(null)}
              className="min-h-14 shrink-0 rounded-xl bg-surface px-4 text-lg font-bold text-brand ring-2 ring-inset ring-line"
            >
              ‹ Floors
            </button>
            <div className="min-w-0">
              <h2 className="truncate text-2xl font-bold tracking-tight">{floor.label}</h2>
              <p
                className={`text-base ${
                  selected?.is_mine ? "font-semibold text-brand" : "text-ink-soft"
                }`}
              >
                {selected?.is_mine ? "Your floor" : "Not your floor — you can still check it"}
              </p>
            </div>
          </div>

          {rooms.length === 0 ? (
            <Card>
              <EmptyState
                title="No classes on this floor at this time"
                body="Go back and pick another floor, or change the time."
              />
            </Card>
          ) : (
            <>
              {pending.length > 0 ? (
                <div className="space-y-2.5">
                  <h3 className="text-xl font-bold">
                    {locked ? "Not reported" : "To do"}{" "}
                    <span className="text-ink-faint">({pending.length})</span>
                  </h3>
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
                </div>
              ) : null}

              {pending.length === 0 && !locked ? (
                <div className="rounded-2xl bg-ok px-4 py-6 text-center text-white">
                  <p className="text-2xl font-bold">This floor is done</p>
                  <button
                    type="button"
                    onClick={() => openFloor(null)}
                    className="mt-3 min-h-12 rounded-xl bg-white px-5 text-lg font-bold text-ok"
                  >
                    Pick the next floor
                  </button>
                </div>
              ) : null}

              {done.length > 0 ? (
                <div className="space-y-2.5">
                  <h3 className="text-xl font-bold text-ok">
                    Done <span className="text-ink-faint">({done.length})</span>
                  </h3>
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
                </div>
              ) : null}
            </>
          )}
        </section>
      )}
    </div>
  );
}

/** One floor: how many classes it has, how many are checked, and a big way in. */
function FloorCard({
  floor: f,
  closed,
  onOpen,
}: {
  floor: FloorSummary;
  closed: boolean;
  onOpen: () => void;
}) {
  const left = f.total - f.checked;
  const complete = left === 0;
  return (
    <button
      type="button"
      onClick={onOpen}
      className={`w-full rounded-2xl border-2 bg-surface p-4 text-left transition-transform active:scale-[0.98] ${
        f.is_mine ? "border-brand" : "border-line"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-2xl font-bold tracking-tight">{f.label}</p>
          <p className="text-base text-ink-soft">
            {f.total} {f.total === 1 ? "class" : "classes"}
          </p>
        </div>
        {f.is_mine ? (
          <span className="shrink-0 rounded-lg bg-brand-soft px-2.5 py-1 text-sm font-bold text-brand">
            Your floor
          </span>
        ) : null}
      </div>

      <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-canvas">
        <div
          className={`h-full rounded-full ${complete ? "bg-ok" : "bg-brand"}`}
          style={{ width: `${f.total ? (f.checked / f.total) * 100 : 0}%` }}
        />
      </div>

      <div className="mt-3 flex items-center justify-between gap-2">
        <p
          className={`text-lg font-bold ${
            complete ? "text-ok" : closed ? "text-gap" : "text-ink"
          }`}
        >
          {complete ? "All done" : closed ? `${left} not reported` : `${left} to check`}
        </p>
        <span className="text-lg font-semibold tabular-nums text-ink-soft">
          {f.checked}/{f.total}
        </span>
      </div>

      <span className="mt-3 flex min-h-12 items-center justify-center rounded-xl bg-brand text-lg font-bold text-white">
        Open floor ›
      </span>
    </button>
  );
}
