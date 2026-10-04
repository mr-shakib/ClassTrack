"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { formatDay } from "@/components/MakeupTracker";
import { ConflictList, RoomPicker, useFreeRooms } from "@/components/RoomPicker";
import StatusBadge from "@/components/StatusBadge";
import {
  Button,
  Card,
  EmptyState,
  ErrorNote,
  Field,
  Spinner,
  bigInputClass,
} from "@/components/ui";
import { ApiError, SLOTS, api, todayISO } from "@/lib/api";
import { mayBookExtra, useRequireAccess } from "@/lib/auth";
import type { ClassInstance, ConflictReport, ExtraSection } from "@/lib/types";


const key = (s: ExtraSection) => `${s.course_code}|${s.section}`;

export default function ExtraClassPage() {
  const { permitted, loading: authLoading } = useRequireAccess(mayBookExtra);

  const [sections, setSections] = useState<ExtraSection[] | null>(null);
  const [booked, setBooked] = useState<ClassInstance[]>([]);
  const [error, setError] = useState<string | null>(null);

  const loadBooked = useCallback(async () => {
    try {
      setBooked(await api.extraClasses());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load your extra classes.");
    }
  }, []);

  useEffect(() => {
    if (!permitted) return;
    api
      .extraSections()
      .then(setSections)
      .catch((err) => {
        setSections([]);
        setError(err instanceof ApiError ? err.message : "Could not load your sections.");
      });
    void loadBooked();
  }, [permitted, loadBooked]);

  if (authLoading || !permitted) return <Spinner />;

  // Still to come first, soonest at the top; the rest as they happened.
  const upcoming = booked
    .filter((b) => b.status === "UPCOMING")
    .sort((a, b) => a.date.localeCompare(b.date) || a.time_slot.localeCompare(b.time_slot));
  const past = booked.filter((b) => b.status !== "UPCOMING");

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Book an extra class</h1>
        <p className="mt-1 text-base text-ink-soft">
          Take an empty room for one of your sections. It is booked at once, with no
          approval, and staff check it like any class. Held, it counts towards the
          course&apos;s classes; if you do not come, it is recorded as missed.
        </p>
      </div>

      {error ? <ErrorNote message={error} /> : null}

      {sections === null ? (
        <Spinner label="Loading your sections…" />
      ) : sections.length === 0 ? (
        <Card className="p-6">
          <EmptyState
            title="No sections to book for"
            body="You have no classes on the routine in force."
          />
        </Card>
      ) : (
        <BookingForm sections={sections} onBooked={loadBooked} />
      )}

      <Card>
        <div className="border-b border-line px-4 py-3 sm:px-5">
          <h2 className="text-xl font-bold">Your extra classes ({upcoming.length} coming)</h2>
        </div>
        {booked.length === 0 ? (
          <EmptyState title="None booked yet." />
        ) : (
          <ul className="divide-y divide-line">
            {[...upcoming, ...past].map((b) => (
              <BookedRow key={b.id} inst={b} onChanged={loadBooked} />
            ))}
          </ul>
        )}
      </Card>

      <p className="text-center text-base">
        <Link href="/teacher" className="font-semibold text-brand hover:underline">
          Back to My classes
        </Link>
      </p>
    </div>
  );
}

function BookingForm({
  sections,
  onBooked,
}: {
  sections: ExtraSection[];
  onBooked: () => void;
}) {
  const [picked, setPicked] = useState(key(sections[0]));
  const [date, setDate] = useState("");
  const [slot, setSlot] = useState<string>(SLOTS[0]);
  const [room, setRoom] = useState("");
  const [report, setReport] = useState<ConflictReport | null>(null);
  const [checking, setChecking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  // Bumped by each booking, so the room just taken leaves the list.
  const [bookings, setBookings] = useState(0);

  const section = sections.find((s) => key(s) === picked) ?? sections[0];
  const freeRooms = useFreeRooms(date, slot, true, bookings);

  // The room list already leaves out taken rooms; this catches the section or
  // you being busy then, a holiday, or the exams.
  const validate = useCallback(async () => {
    if (!date || !room) {
      setReport(null);
      return;
    }
    setChecking(true);
    try {
      setReport(
        await api.checkConflict({ date, time_slot: slot, room, section: section.section }),
      );
    } catch {
      setReport(null);
    } finally {
      setChecking(false);
    }
  }, [date, slot, room, section.section]);

  useEffect(() => {
    const timer = setTimeout(() => void validate(), 350);
    return () => clearTimeout(timer);
  }, [validate]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const made = await api.bookExtraClass({
        course_code: section.course_code,
        section: section.section,
        date,
        time_slot: slot,
        room,
      });
      setNotice(
        `${made.room} is booked for ${made.course_code} · ${made.section} on ${formatDay(
          made.date,
        )} at ${made.time_slot}. Staff will check it then.`,
      );
      setRoom("");
      setReport(null);
      setBookings((n) => n + 1);
      onBooked();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not book the room.");
    } finally {
      setBusy(false);
    }
  };

  const blocked = report != null && !report.ok;

  return (
    <Card className="p-4 sm:p-5">
      <form onSubmit={submit} className="space-y-6">
        <Field label="Section" size="lg">
          <select
            className={bigInputClass}
            value={picked}
            onChange={(e) => setPicked(e.target.value)}
          >
            {sections.map((s) => (
              <option key={key(s)} value={key(s)}>
                {s.course_code} · {s.section}
                {s.course_title ? ` — ${s.course_title}` : ""}
              </option>
            ))}
          </select>
        </Field>

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
        </div>

        <RoomPicker
          date={date}
          rooms={freeRooms.rooms}
          loading={freeRooms.loading}
          error={freeRooms.error}
          room={room}
          onPick={setRoom}
          roomType={section.room_type}
        />

        {checking ? (
          <p className="text-base text-ink-faint">Checking availability…</p>
        ) : report && !report.ok ? (
          <ConflictList report={report} />
        ) : null}

        {error ? <ErrorNote message={error} /> : null}
        {notice ? (
          <p className="rounded-xl bg-ok-soft px-4 py-3 text-base font-semibold text-ok">
            {notice}
          </p>
        ) : null}

        <Button
          type="submit"
          size="xl"
          className="w-full"
          disabled={busy || blocked || !date || !room}
        >
          {busy
            ? "Booking…"
            : blocked
              ? "Resolve the conflict first"
              : room
                ? `Book ${room}`
                : "Pick an empty room"}
        </Button>
      </form>
    </Card>
  );
}

function BookedRow({ inst, onChanged }: { inst: ClassInstance; onChanged: () => void }) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cancel = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.cancelExtraClass(inst.id);
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not cancel the class.");
      setBusy(false);
    }
  };

  return (
    <li className="space-y-2 px-4 py-4 sm:px-5">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="min-w-0 flex-1">
          <p className="text-lg font-semibold">
            {inst.course_code} · {inst.section}
          </p>
          <p className="text-base tabular-nums text-ink-soft">
            {formatDay(inst.date)} · {inst.time_slot} · {inst.room}
          </p>
        </div>
        <StatusBadge status={inst.status} lateMinutes={inst.check?.late_minutes} size="lg" />
      </div>
      {inst.status === "UPCOMING" ? (
        confirming ? (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-base text-ink-soft">Give {inst.room} back?</span>
            <Button variant="danger" size="lg" onClick={cancel} disabled={busy}>
              {busy ? "Cancelling…" : "Yes, cancel it"}
            </Button>
            <Button variant="secondary" size="lg" onClick={() => setConfirming(false)}>
              Keep it
            </Button>
          </div>
        ) : (
          <Button variant="secondary" size="lg" onClick={() => setConfirming(true)}>
            Cancel this class
          </Button>
        )
      ) : null}
      {error ? <ErrorNote message={error} /> : null}
    </li>
  );
}
