"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Button,
  Card,
  ErrorNote,
  Field,
  Spinner,
  inputClass,
} from "@/components/ui";
import { ApiError, SLOTS, api, todayISO } from "@/lib/api";
import { useRequireRole } from "@/lib/auth";
import type { ClassInstance, ConflictReport, FreeRoom, MakeupMode } from "@/lib/types";

function MakeupForm() {
  const { permitted, loading: authLoading } = useRequireRole([
    "TEACHER",
    "HOD",
    "SUPER_ADMIN",
  ]);
  const params = useSearchParams();
  const router = useRouter();
  const instanceId = Number(params.get("instance") ?? 0);

  const [original, setOriginal] = useState<ClassInstance | null>(null);
  const [mode, setMode] = useState<MakeupMode>("PHYSICAL");
  const [date, setDate] = useState("");
  const [slot, setSlot] = useState<string>(SLOTS[5]);
  const [room, setRoom] = useState("");
  const [rooms, setRooms] = useState<FreeRoom[] | null>(null);
  const [roomsLoading, setRoomsLoading] = useState(false);
  const [sameType, setSameType] = useState(true);
  const [reason, setReason] = useState("");
  const [report, setReport] = useState<ConflictReport | null>(null);
  const [checking, setChecking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!permitted || !instanceId) return;
    api
      .instance(instanceId)
      .then(setOriginal)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Could not load the class."),
      );
  }, [permitted, instanceId]);

  // The empty rooms depend on the cell, so reload them whenever it changes.
  useEffect(() => {
    if (mode !== "PHYSICAL" || !date || !slot) {
      setRooms(null);
      return;
    }
    let alive = true;
    setRoomsLoading(true);
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
        if (alive) setRoomsLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [mode, date, slot]);

  // A room picked for one slot may be taken in the next.
  useEffect(() => {
    if (rooms && room && !rooms.some((r) => r.room === room)) setRoom("");
  }, [rooms, room]);

  // The room list already excludes occupied rooms; this still catches the
  // teacher or section being busy at that time, and holidays (BR-14).
  const validate = useCallback(async () => {
    if (!date || !slot || !original || (mode === "PHYSICAL" && !room)) {
      setReport(null);
      return;
    }
    setChecking(true);
    try {
      setReport(
        await api.checkConflict({
          date,
          time_slot: slot,
          room: mode === "PHYSICAL" ? room : null,
          section: original.section,
        }),
      );
    } catch {
      setReport(null);
    } finally {
      setChecking(false);
    }
  }, [date, slot, room, mode, original]);

  useEffect(() => {
    const timer = setTimeout(() => void validate(), 350);
    return () => clearTimeout(timer);
  }, [validate]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.createMakeup({
        original_instance_id: instanceId,
        mode,
        date,
        time_slot: slot,
        room: mode === "PHYSICAL" ? room : null,
        reason: reason || null,
      });
      setDone(true);
      setTimeout(() => router.push("/teacher"), 2000);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not send the reschedule request.",
      );
    } finally {
      setBusy(false);
    }
  };

  if (authLoading || !permitted) return <Spinner />;

  if (!instanceId) {
    return (
      <Card className="p-6">
        <p className="text-sm text-ink-soft">
          Pick a missed class from{" "}
          <a className="text-brand hover:underline" href="/teacher">
            My classes
          </a>{" "}
          to reschedule it.
        </p>
      </Card>
    );
  }

  if (done) {
    return (
      <Card className="p-6 text-center">
        <p className="text-lg font-semibold text-ok">Reschedule requested</p>
        <p className="mt-1 text-sm text-ink-soft">
          Sent to the Head of Department.{" "}
          {mode === "ONLINE"
            ? "Once approved it is recorded as an online class."
            : `Once approved, staff will check ${room} on ${date} at ${slot}.`}
        </p>
      </Card>
    );
  }

  const blocked = report != null && !report.ok;
  const shown =
    rooms?.filter((r) => !sameType || !original || r.room_type === original.room_type) ?? [];
  const typeLabel = original?.room_type.toLowerCase() ?? "";

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Request a reschedule</h1>
        <p className="mt-0.5 text-sm text-ink-soft">
          Pick a new time and an empty room. The Head of Department approves it,
          and then staff check it like any other class.
        </p>
      </div>

      {original ? (
        <Card className="p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-faint">
            Missed class
          </p>
          <p className="mt-1 text-sm font-medium">
            {original.course_code} · {original.section}
          </p>
          <p className="text-xs text-ink-soft">
            {original.date} · {original.time_slot} · {original.room}
          </p>
        </Card>
      ) : (
        <Spinner label="Loading the original class…" />
      )}

      <Card className="p-4">
        <form onSubmit={submit} className="space-y-4">
          <Field label="Class mode">
            <div className="grid grid-cols-2 gap-2">
              {(["PHYSICAL", "ONLINE"] as MakeupMode[]).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMode(m)}
                  className={`min-h-11 rounded-lg px-3 py-2.5 text-sm font-medium ring-1 ring-inset transition-colors ${
                    mode === m
                      ? "bg-brand-soft text-brand ring-brand/30"
                      : "bg-surface text-ink-soft ring-line hover:bg-canvas"
                  }`}
                >
                  {m === "PHYSICAL" ? "In a room" : "Online"}
                </button>
              ))}
            </div>
            <p className="mt-1.5 text-xs text-ink-faint">
              {mode === "PHYSICAL"
                ? "Staff check it in the room you pick, at the new time."
                : "Excluded from physical room checking."}
            </p>
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Date">
              <input
                type="date"
                className={inputClass}
                value={date}
                min={todayISO()}
                onChange={(e) => setDate(e.target.value)}
                required
              />
            </Field>
            <Field label="Slot" hint="Classes run on fixed 90-minute slots.">
              <select
                className={inputClass}
                value={slot}
                onChange={(e) => setSlot(e.target.value)}
              >
                {SLOTS.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          {mode === "PHYSICAL" ? (
            // Not a <Field>: a <label> wrapping many buttons forwards stray
            // clicks to the first one.
            <div>
              <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm font-medium text-ink-soft">
                  Empty room{room ? ` · ${room}` : ""}
                </span>
                {original ? (
                  <label className="flex items-center gap-1.5 text-xs text-ink-soft">
                    <input
                      type="checkbox"
                      checked={sameType}
                      onChange={(e) => setSameType(e.target.checked)}
                    />
                    Only {typeLabel} rooms
                  </label>
                ) : null}
              </div>

              {!date ? (
                <p className="rounded-lg bg-canvas px-3 py-2 text-sm text-ink-faint">
                  Pick a date and slot to see which rooms are empty.
                </p>
              ) : roomsLoading ? (
                <p className="text-sm text-ink-faint">Finding empty rooms…</p>
              ) : shown.length === 0 ? (
                <p className="rounded-lg bg-canvas px-3 py-2 text-sm text-ink-soft">
                  No empty {sameType ? `${typeLabel} ` : ""}rooms at this time. Try
                  another slot{sameType ? " or include every room type" : ""}.
                </p>
              ) : (
                <div className="grid max-h-72 grid-cols-3 gap-1.5 overflow-y-auto sm:grid-cols-5">
                  {shown.map((r) => {
                    const on = room === r.room;
                    return (
                      <button
                        key={r.room}
                        type="button"
                        aria-pressed={on}
                        onClick={() => setRoom(r.room)}
                        className={`min-h-11 rounded-lg px-2 py-1.5 text-left ring-1 ring-inset transition-colors ${
                          on
                            ? "bg-brand-soft text-brand ring-brand/30"
                            : "bg-surface text-ink ring-line hover:bg-canvas"
                        }`}
                      >
                        <span className="block text-sm font-medium">{r.room}</span>
                        <span className="block text-[11px] opacity-70">
                          {r.zone}
                          {sameType ? "" : ` · ${r.room_type}`}
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          ) : null}

          <Field label="Reason">
            <input
              className={inputClass}
              placeholder="Why was the class missed?"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </Field>

          {checking ? (
            <p className="text-xs text-ink-faint">Checking availability…</p>
          ) : report && !report.ok ? (
            <div className="rounded-lg border border-bad/20 bg-bad-soft px-3 py-2">
              <p className="text-sm font-semibold text-bad">
                {report.conflicts.length} conflict
                {report.conflicts.length === 1 ? "" : "s"}
              </p>
              <ul className="mt-1 space-y-0.5">
                {report.conflicts.map((c, i) => (
                  <li key={i} className="text-xs text-bad">
                    <span className="font-semibold">{c.type}:</span> {c.message}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {error ? <ErrorNote message={error} /> : null}

          <Button
            type="submit"
            size="lg"
            className="w-full"
            disabled={
              busy || blocked || !date || !original || (mode === "PHYSICAL" && !room)
            }
          >
            {busy
              ? "Sending…"
              : blocked
                ? "Resolve the conflict first"
                : mode === "PHYSICAL" && !room
                  ? "Pick an empty room"
                  : "Send for approval"}
          </Button>
        </form>
      </Card>
    </div>
  );
}

export default function MakeupPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <MakeupForm />
    </Suspense>
  );
}
