"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { formatDay } from "@/components/MakeupTracker";
import {
  Button,
  Card,
  ErrorNote,
  Field,
  Spinner,
  bigInputClass,
} from "@/components/ui";
import { ApiError, SLOTS, api, todayISO } from "@/lib/api";
import { ADMIN_ROLES, useRequireRole } from "@/lib/auth";
import type { ClassInstance, ConflictReport, FreeRoom, MakeupMode, Role } from "@/lib/types";

const TEACHER_PAGE_ROLES: Role[] = ["TEACHER", ...ADMIN_ROLES];

/** A class runs 90 minutes, the same as every slot on the routine. */
const CLASS_MINUTES = 90;

/** The latest start that still finishes before midnight, as the input's `max`. */
const LATEST_START = "22:30";

/** "19:30" → "19:30-21:00", the label the backend will store. */
function endsLabel(start: string): string {
  const [h, m] = start.split(":").map(Number);
  const end = h * 60 + m + CLASS_MINUTES;
  return `${start}-${String(Math.floor(end / 60) % 24).padStart(2, "0")}:${String(end % 60).padStart(2, "0")}`;
}

function MakeupForm() {
  const { permitted, loading: authLoading } = useRequireRole(TEACHER_PAGE_ROLES);
  const params = useSearchParams();
  const router = useRouter();
  const instanceId = Number(params.get("instance") ?? 0);

  const [original, setOriginal] = useState<ClassInstance | null>(null);
  const [mode, setMode] = useState<MakeupMode>("PHYSICAL");
  const [date, setDate] = useState("");
  const [slot, setSlot] = useState<string>(SLOTS[5]);
  // Online only: a time the teacher picks off the clock, in 24-hour HH:MM.
  const [startTime, setStartTime] = useState("");
  const [room, setRoom] = useState("");
  const [rooms, setRooms] = useState<FreeRoom[] | null>(null);
  const [roomsLoading, setRoomsLoading] = useState(false);
  const [sameType, setSameType] = useState(true);
  const [reason, setReason] = useState("");
  const [driveLink, setDriveLink] = useState("");
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

  const online = mode === "ONLINE";
  // An online class may be held at any time, so the teacher picks one off the
  // clock instead of taking a routine slot.
  const ownTime = online && startTime !== "";

  // The room list already excludes occupied rooms; this still catches the
  // teacher or section being busy at that time, and holidays (BR-14). For a
  // time off the clock it is the only check there is, so it matters more.
  const validate = useCallback(async () => {
    if (!date || !original || (mode === "PHYSICAL" && !room)) {
      setReport(null);
      return;
    }
    if (online ? !startTime : !slot) {
      setReport(null);
      return;
    }
    setChecking(true);
    try {
      setReport(
        await api.checkConflict({
          date,
          time_slot: ownTime ? null : slot,
          start_time: ownTime ? startTime : null,
          room: mode === "PHYSICAL" ? room : null,
          section: original.section,
        }),
      );
    } catch {
      setReport(null);
    } finally {
      setChecking(false);
    }
  }, [date, slot, startTime, online, ownTime, room, mode, original]);

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
        time_slot: ownTime ? null : slot,
        start_time: ownTime ? startTime : null,
        room: mode === "PHYSICAL" ? room : null,
        reason: reason || null,
        drive_link: mode === "ONLINE" && driveLink.trim() ? driveLink.trim() : null,
      });
      setDone(true);
      setTimeout(() => router.push("/teacher"), 2500);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : mode === "PHYSICAL"
            ? "Could not book the room."
            : "Could not send the reschedule request.",
      );
    } finally {
      setBusy(false);
    }
  };

  if (authLoading || !permitted) return <Spinner />;

  if (!instanceId) {
    return (
      <Card className="mx-auto max-w-2xl p-6">
        <p className="text-lg text-ink-soft">
          Pick a missed class from{" "}
          <a className="font-semibold text-brand hover:underline" href="/teacher">
            My classes
          </a>{" "}
          to reschedule it.
        </p>
      </Card>
    );
  }

  if (done) {
    return (
      <div className="mx-auto max-w-2xl rounded-2xl bg-ok px-6 py-8 text-center text-white">
        <p className="text-2xl font-bold">
          {mode === "ONLINE" ? "Reschedule requested" : "Class rescheduled"}
        </p>
        <p className="mt-2 text-lg">
          {online
            ? `Sent to the Head of Department for ${formatDay(date)} at ${
                ownTime ? endsLabel(startTime) : slot
              }. You will get a notification when they decide. ${
                driveLink.trim()
                  ? "Your Drive link was sent with the request."
                  : "After the class, submit its Drive link."
              }`
            : `${room} is booked for you on ${formatDay(date)} at ${slot}. Staff will check it at that time.`}
        </p>
        <p className="mt-3 text-base opacity-80">Taking you back to My classes…</p>
      </div>
    );
  }

  const blocked = report != null && !report.ok;
  const shown =
    rooms?.filter((r) => !sameType || !original || r.room_type === original.room_type) ?? [];
  const typeLabel = original?.room_type.toLowerCase() ?? "";

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Reschedule a class</h1>
        <p className="mt-1 text-base text-ink-soft">
          Pick a new time and an empty room: it is booked at once, with no approval,
          and staff check it like any other class. Online instead lets you hold it at
          any time of any day, once the Head of Department approves.
        </p>
      </div>

      {original ? (
        <div className="rounded-2xl border-2 border-bad/30 bg-bad-soft p-4 sm:p-5">
          <p className="text-sm font-bold uppercase tracking-wide text-bad">Missed class</p>
          <p className="mt-1 text-2xl font-bold tracking-tight">{original.course_code}</p>
          <p className="text-lg">Section {original.section}</p>
          <p className="mt-1 text-base tabular-nums text-ink-soft">
            {formatDay(original.date)} · {original.time_slot} · {original.room}
          </p>
        </div>
      ) : (
        <Spinner label="Loading the original class…" />
      )}

      <Card className="p-4 sm:p-5">
        <form onSubmit={submit} className="space-y-6">
          {/* Not a <Field>: a <label> wrapping several buttons forwards stray
              clicks to the first one. */}
          <div>
            <p className="mb-2 text-base font-semibold">How will you hold it?</p>
            <div className="grid grid-cols-2 gap-3">
              {(["PHYSICAL", "ONLINE"] as MakeupMode[]).map((m) => (
                <button
                  key={m}
                  type="button"
                  aria-pressed={mode === m}
                  onClick={() => setMode(m)}
                  className={`min-h-16 rounded-xl px-3 py-3 text-lg font-bold ring-2 ring-inset transition-colors ${
                    mode === m
                      ? "bg-brand text-white ring-brand"
                      : "bg-surface text-ink ring-line hover:bg-canvas"
                  }`}
                >
                  {m === "PHYSICAL" ? "In a room" : "Online"}
                </button>
              ))}
            </div>
            <p className="mt-2 text-base text-ink-soft">
              {mode === "PHYSICAL"
                ? "Booked as soon as you pick an empty room. Staff check it there, at the new time."
                : "Hold it at any time of any day — nobody checks a room for it. Needs approval. You can add a Drive link now, or after the class."}
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Date" size="lg">
              <input
                type="date"
                className={bigInputClass}
                value={date}
                min={todayISO()}
                onChange={(e) => setDate(e.target.value)}
                required
              />
            </Field>
            {online ? (
              <Field
                label="Start time"
                size="lg"
                hint={
                  startTime
                    ? `Runs ${endsLabel(startTime)} — ${CLASS_MINUTES} minutes.`
                    : "Any time, any day. The class runs 90 minutes from there."
                }
              >
                <input
                  type="time"
                  className={bigInputClass}
                  value={startTime}
                  max={LATEST_START}
                  onChange={(e) => setStartTime(e.target.value)}
                  required
                />
              </Field>
            ) : (
              <Field label="Time" size="lg" hint="Classes run on fixed 90-minute slots.">
                <select
                  className={bigInputClass}
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
            )}
          </div>

          {mode === "PHYSICAL" ? (
            <div>
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <span className="text-base font-semibold">
                  Empty room{room ? ` · ${room}` : ""}
                </span>
                {original ? (
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

              {!date ? (
                <p className="rounded-xl bg-canvas px-4 py-3 text-base text-ink-soft">
                  Pick a date and time to see which rooms are empty.
                </p>
              ) : roomsLoading ? (
                <p className="text-base text-ink-faint">Finding empty rooms…</p>
              ) : shown.length === 0 ? (
                <p className="rounded-xl bg-canvas px-4 py-3 text-base text-ink-soft">
                  No empty {sameType ? `${typeLabel} ` : ""}rooms at this time. Try
                  another time{sameType ? " or include every room type" : ""}.
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
                        onClick={() => setRoom(r.room)}
                        className={`min-h-16 rounded-xl px-3 py-2 text-left ring-2 ring-inset transition-colors ${
                          on
                            ? "bg-brand text-white ring-brand"
                            : "bg-surface text-ink ring-line hover:bg-canvas"
                        }`}
                      >
                        <span className="block text-lg font-bold">{r.room}</span>
                        <span className="block text-sm opacity-80">
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

          {mode === "ONLINE" ? (
            <Field
              label="Drive link (optional)"
              size="lg"
              hint="The Head of Department or Associate Head can open it while deciding."
            >
              <input
                type="url"
                inputMode="url"
                className={bigInputClass}
                placeholder="https://drive.google.com/…"
                value={driveLink}
                onChange={(e) => setDriveLink(e.target.value)}
              />
            </Field>
          ) : null}

          <Field label="Reason" size="lg">
            <input
              className={bigInputClass}
              placeholder="Why was the class missed?"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </Field>

          {checking ? (
            <p className="text-base text-ink-faint">Checking availability…</p>
          ) : report && !report.ok ? (
            <div className="rounded-xl border-2 border-bad/30 bg-bad-soft px-4 py-3">
              <p className="text-lg font-bold text-bad">
                {report.conflicts.length} conflict
                {report.conflicts.length === 1 ? "" : "s"}
              </p>
              <ul className="mt-1 space-y-1">
                {report.conflicts.map((c, i) => (
                  <li key={i} className="text-base text-bad">
                    <span className="font-semibold">{c.type}:</span> {c.message}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {error ? <ErrorNote message={error} /> : null}

          <Button
            type="submit"
            size="xl"
            className="w-full"
            disabled={
              busy ||
              blocked ||
              !date ||
              !original ||
              (online ? !startTime : false) ||
              (mode === "PHYSICAL" && !room)
            }
          >
            {busy
              ? mode === "PHYSICAL"
                ? "Booking…"
                : "Sending…"
              : blocked
                ? "Resolve the conflict first"
                : mode === "PHYSICAL"
                  ? room
                    ? `Book ${room}`
                    : "Pick an empty room"
                  : !startTime
                    ? "Pick a start time"
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
