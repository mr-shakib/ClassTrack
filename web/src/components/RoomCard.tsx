"use client";

import { useState } from "react";
import { ApiError, api } from "@/lib/api";
import type { CheckOutcome, RoomRow } from "@/lib/types";

/**
 * One room on the checking screen.
 *
 * This is used one-handed, while walking, by people who were not hired for
 * their comfort with software. Everything here follows from that:
 *
 * * The normal case -- the class is running -- is **one tap**. No dialog, no
 *   confirmation, no scrolling.
 * * Late is **two taps**: the arrival time is pre-filled with now, so the
 *   second tap is a confirmation rather than data entry.
 * * Targets are large and full-width. Nothing important is a small link.
 * * Words, not icons alone. "Teacher absent" beats a red cross.
 */
export default function RoomCard({
  row,
  onChanged,
  locked = false,
  canOverride = false,
}: {
  row: RoomRow;
  onChanged: (next: Partial<RoomRow>) => void;
  locked?: boolean;
  canOverride?: boolean;
}) {
  const [busy, setBusy] = useState<CheckOutcome | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmingLate, setConfirmingLate] = useState(false);
  const [arrival, setArrival] = useState("");
  const [reason, setReason] = useState("");
  const [overriding, setOverriding] = useState(false);
  const [noteOpen, setNoteOpen] = useState(false);
  const [remark, setRemark] = useState(row.check?.remark ?? "");

  const submitted = row.check != null;

  const nowHHMM = () => {
    const d = new Date();
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  };

  const submit = async (outcome: CheckOutcome, arrivalTime?: string) => {
    setBusy(outcome);
    setError(null);

    const previous = { status: row.status, check: row.check };
    onChanged({
      status: outcome === "TEACHER_NOT_FOUND" ? null : outcome,
      check: {
        outcome,
        arrival_time: arrivalTime ?? null,
        late_minutes: null,
        remark: remark || null,
        checked_at: new Date().toISOString(),
        checked_by: null,
      },
    });

    try {
      const res = await api.submitCheck(row.instance_id, {
        outcome,
        arrival_time: arrivalTime ?? null,
        remark: remark || null,
        reason: reason || null,
      });
      onChanged({
        status: res.status,
        check: {
          outcome,
          arrival_time: arrivalTime ?? null,
          late_minutes: res.late_minutes,
          remark: remark || null,
          checked_at: res.checked_at,
          checked_by: res.checked_by,
        },
      });
      setConfirmingLate(false);
      setOverriding(false);
    } catch (err) {
      onChanged(previous);
      setError(err instanceof ApiError ? err.message : "Could not save. Try again.");
    } finally {
      setBusy(null);
    }
  };

  // --- submitted: a big, unmistakable result -------------------------------
  if (submitted && !confirmingLate && !overriding) {
    const outcome = row.check!.outcome;
    const done = {
      RUNNING: { text: "Class is running", className: "bg-ok text-white" },
      LATE: {
        text: `Teacher was late${
          row.check!.late_minutes != null ? ` — ${row.check!.late_minutes} min` : ""
        }`,
        className: "bg-warn text-white",
      },
      TEACHER_NOT_FOUND: {
        text: "Teacher not found",
        className: "bg-bad text-white",
      },
    }[outcome];

    return (
      <div className="overflow-hidden rounded-2xl border-2 border-line bg-surface">
        <div className="flex items-baseline justify-between gap-2 px-4 pt-3">
          <span className="text-2xl font-bold tracking-tight">{row.room}</span>
          <span className="text-base font-semibold tabular-nums text-ink-soft">
            {row.scheduled_start}
          </span>
        </div>
        <div className="px-4 pb-3 text-base text-ink-soft">
          {row.course_code} · {row.section}
        </div>

        <div className={`flex items-center gap-2 px-4 py-3 text-lg font-bold ${done.className}`}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
            <path d="M9 16.2 4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4z" />
          </svg>
          {done.text}
        </div>

        <div className="flex items-center justify-between gap-2 px-4 py-2">
          <span className="text-sm text-ink-faint">
            {row.check!.checked_by ? `by ${row.check!.checked_by}` : "Saved"}
          </span>
          {!locked || canOverride ? (
            <button
              className="rounded-lg px-3 py-2 text-base font-semibold text-brand hover:bg-brand-soft"
              onClick={() => {
                if (locked) setOverriding(true);
                setArrival(nowHHMM());
                setConfirmingLate(false);
                onChanged({ check: null, status: null });
              }}
            >
              Change
            </button>
          ) : null}
        </div>
      </div>
    );
  }

  // --- reporting closed for the day, nothing to do -------------------------
  if (locked && !overriding) {
    return (
      <div className="rounded-2xl border-2 border-line bg-surface p-4 opacity-80">
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-2xl font-bold tracking-tight">{row.room}</span>
          <span className="text-base font-semibold tabular-nums text-ink-soft">
            {row.scheduled_start}
          </span>
        </div>
        <div className="mt-0.5 text-base text-ink-soft">
          {row.course_code} · {row.section}
        </div>
        <div className="mt-3 rounded-xl bg-gap-soft px-3 py-2.5 text-base font-semibold text-gap">
          Not reported — the day is over
        </div>
        {canOverride ? (
          <button
            className="mt-2 w-full rounded-xl border-2 border-brand/30 px-3 py-2.5 text-base font-semibold text-brand"
            onClick={() => setOverriding(true)}
          >
            Correct this record
          </button>
        ) : null}
      </div>
    );
  }

  // --- the two-tap late confirmation ---------------------------------------
  if (confirmingLate) {
    return (
      <div className="rounded-2xl border-2 border-warn bg-surface p-4">
        <div className="text-2xl font-bold tracking-tight">{row.room}</div>
        <div className="mt-0.5 text-base text-ink-soft">
          {row.course_code} · {row.section}
        </div>

        <p className="mt-3 text-base font-semibold text-ink">Teacher arrived at</p>
        <input
          type="time"
          value={arrival}
          onChange={(e) => setArrival(e.target.value)}
          className="mt-1.5 w-full rounded-xl border-2 border-warn/40 bg-surface px-4 py-3 text-center text-3xl font-bold tabular-nums"
        />

        <button
          onClick={() => submit("LATE", arrival)}
          disabled={!arrival || busy != null}
          className="mt-3 min-h-16 w-full rounded-xl bg-warn px-4 text-xl font-bold text-white disabled:opacity-50"
        >
          {busy === "LATE" ? "Saving…" : "Save"}
        </button>
        <button
          onClick={() => setConfirmingLate(false)}
          className="mt-2 min-h-12 w-full rounded-xl text-lg font-semibold text-ink-soft"
        >
          Back
        </button>

        {error ? (
          <p className="mt-2 rounded-lg bg-bad-soft px-3 py-2 text-base font-semibold text-bad">
            {error}
          </p>
        ) : null}
      </div>
    );
  }

  // --- the default: three big choices --------------------------------------
  return (
    <div className="rounded-2xl border-2 border-line bg-surface p-4">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-2xl font-bold tracking-tight">{row.room}</span>
        <span className="text-base font-semibold tabular-nums text-ink-soft">
          {row.scheduled_start}–{row.scheduled_end}
        </span>
      </div>

      <div className="mt-1 text-lg font-medium">
        {row.course_code} · {row.section}
      </div>
      <div className="text-base text-ink-soft">
        {row.teacher_name ?? row.teacher_initial}
      </div>

      {row.is_makeup ? (
        <div className="mt-2 inline-block rounded-lg bg-info-soft px-2.5 py-1 text-sm font-bold uppercase tracking-wide text-info">
          Makeup class
        </div>
      ) : null}

      {overriding ? (
        <div className="mt-3 rounded-xl bg-brand-soft p-3">
          <p className="text-sm font-semibold text-brand">
            Reason for the change (optional)
          </p>
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Not required"
            className="mt-1.5 w-full rounded-lg border-2 border-brand/30 bg-surface px-3 py-2.5 text-base"
          />
        </div>
      ) : null}

      {/* One tap for the normal case. Full width, tall, plain words. */}
      <div className="mt-3 space-y-2">
        <button
          onClick={() => submit("RUNNING")}
          disabled={busy != null}
          className="min-h-16 w-full rounded-xl bg-ok px-4 text-xl font-bold text-white transition-transform active:scale-[0.98] disabled:opacity-50"
        >
          {busy === "RUNNING" ? "Saving…" : "Class is running"}
        </button>

        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => {
              setArrival(nowHHMM());
              setConfirmingLate(true);
            }}
            disabled={busy != null}
            className="min-h-16 rounded-xl bg-warn px-3 text-lg font-bold leading-tight text-white transition-transform active:scale-[0.98] disabled:opacity-50"
          >
            Teacher late
          </button>
          <button
            onClick={() => submit("TEACHER_NOT_FOUND")}
            disabled={busy != null}
            className="min-h-16 rounded-xl bg-bad px-3 text-lg font-bold leading-tight text-white transition-transform active:scale-[0.98] disabled:opacity-50"
          >
            {busy === "TEACHER_NOT_FOUND" ? "Saving…" : "Teacher absent"}
          </button>
        </div>
      </div>

      {noteOpen ? (
        <input
          value={remark}
          onChange={(e) => setRemark(e.target.value)}
          placeholder="Note (not required)"
          className="mt-2 w-full rounded-xl border-2 border-line px-3 py-2.5 text-base"
        />
      ) : (
        <button
          onClick={() => setNoteOpen(true)}
          className="mt-2 w-full rounded-xl py-2 text-base font-medium text-ink-faint"
        >
          + Add a note
        </button>
      )}

      {error ? (
        <p className="mt-2 rounded-lg bg-bad-soft px-3 py-2 text-base font-semibold text-bad">
          {error}
        </p>
      ) : null}
    </div>
  );
}
