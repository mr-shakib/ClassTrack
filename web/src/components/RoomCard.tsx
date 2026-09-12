"use client";

import { useState } from "react";
import { ApiError, api } from "@/lib/api";
import type { CheckOutcome, RoomRow } from "@/lib/types";
import StatusBadge from "./StatusBadge";

/**
 * One room on the checking screen.
 *
 * This is the only interface used while walking between classrooms, so the
 * normal case -- the class is running -- must be a single tap with no dialog and
 * no confirmation. Everything else is secondary to that.
 */
export default function RoomCard({
  row,
  onChanged,
  locked = false,
  canOverride = false,
}: {
  row: RoomRow;
  onChanged: (next: Partial<RoomRow>) => void;
  /** The checking window is not open, so staff cannot submit. */
  locked?: boolean;
  /** An admin may still correct the record, with a reason. */
  canOverride?: boolean;
}) {
  const [busy, setBusy] = useState<CheckOutcome | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showLate, setShowLate] = useState(false);
  const [showRemark, setShowRemark] = useState(false);
  const [arrival, setArrival] = useState("");
  const [remark, setRemark] = useState(row.check?.remark ?? "");
  const [reason, setReason] = useState("");
  const [overriding, setOverriding] = useState(false);

  const submitted = row.check != null;

  const submit = async (outcome: CheckOutcome, arrivalTime?: string) => {
    setBusy(outcome);
    setError(null);

    // Optimistic: the card responds immediately, and reverts if the call fails.
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
      setShowLate(false);
    } catch (err) {
      onChanged(previous);
      setError(err instanceof ApiError ? err.message : "Could not save. Try again.");
    } finally {
      setBusy(null);
    }
  };

  const nowHHMM = () => {
    const d = new Date();
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  };

  return (
    <div
      className={`rounded-xl border bg-surface p-3.5 transition-colors ${
        submitted ? "border-line" : "border-line"
      }`}
    >
      {/* Header: room and time, the two things staff scan for. */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-base font-semibold">{row.room}</span>
            {row.zone ? (
              <span className="rounded bg-canvas px-1.5 py-0.5 text-[10px] font-semibold tracking-wide text-ink-faint">
                {row.zone}
              </span>
            ) : null}
            {row.is_makeup ? (
              <span className="rounded bg-info-soft px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-info">
                Makeup
              </span>
            ) : null}
          </div>
          <div className="mt-0.5 truncate text-sm text-ink-soft">
            {row.course_code} · {row.section}
          </div>
          <div className="truncate text-sm text-ink-faint">
            {row.teacher_name ?? row.teacher_initial}
            {row.teacher_name ? ` (${row.teacher_initial})` : ""}
          </div>
        </div>
        <div className="shrink-0 text-right">
          <div className="text-xs tabular-nums text-ink-faint">
            {row.scheduled_start}–{row.scheduled_end}
          </div>
          <div className="mt-1">
            <StatusBadge status={row.status} lateMinutes={row.check?.late_minutes} />
          </div>
        </div>
      </div>

      {/* Submitted: collapse to a summary, still amendable. */}
      {submitted && !showLate ? (
        <div className="mt-3 flex items-center justify-between gap-2 border-t border-line pt-2.5">
          <p className="text-xs text-ink-faint">
            {row.check?.outcome === "TEACHER_NOT_FOUND"
              ? "Teacher not found — awaiting threshold"
              : `Recorded${row.check?.checked_by ? ` by ${row.check.checked_by}` : ""}`}
            {row.check?.arrival_time ? ` · arrived ${row.check.arrival_time}` : ""}
          </p>
          {!locked || canOverride ? (
            <button
              className="shrink-0 text-xs font-medium text-brand hover:underline"
              onClick={() => {
                if (locked) setOverriding(true);
                setShowLate(true);
              }}
            >
              {locked ? "Correct" : "Amend"}
            </button>
          ) : null}
        </div>
      ) : locked && !overriding ? (
        <div className="mt-3 border-t border-line pt-2.5">
          <p className="text-xs text-ink-faint">
            {row.status === "NOT_CHECKED"
              ? "Recorded as not checked — the window closed with no result."
              : "The checking window for this class is closed."}
          </p>
          {canOverride ? (
            <button
              className="mt-1 text-xs font-medium text-brand hover:underline"
              onClick={() => setOverriding(true)}
            >
              Correct this record
            </button>
          ) : null}
        </div>
      ) : (
        <>
          {overriding ? (
            <div className="mt-3 rounded-lg bg-brand-soft/60 p-2.5">
              <p className="text-xs font-medium text-brand">
                Correcting after the window closed. A reason is required and is
                kept in the audit log.
              </p>
              <input
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Why is this being changed?"
                className="mt-1.5 w-full rounded-md border border-brand/30 bg-surface px-2 py-1.5 text-sm"
              />
            </div>
          ) : null}

          {/* Three primary actions. Large targets -- these get tapped hundreds
              of times a week, often one-handed while walking. */}
          <div className="mt-3 grid grid-cols-3 gap-2">
            <button
              onClick={() => submit("RUNNING")}
              disabled={busy != null || (overriding && !reason.trim())}
              className="min-h-11 rounded-lg bg-ok-soft px-2 py-2.5 text-sm font-semibold text-ok ring-1 ring-inset ring-ok/20 transition-colors hover:bg-ok/10 active:bg-ok/20 disabled:opacity-50"
            >
              {busy === "RUNNING" ? "…" : "Running"}
            </button>
            <button
              onClick={() => {
                setArrival(nowHHMM());
                setShowLate(true);
              }}
              disabled={busy != null || (overriding && !reason.trim())}
              className="min-h-11 rounded-lg bg-warn-soft px-2 py-2.5 text-sm font-semibold text-warn ring-1 ring-inset ring-warn/20 transition-colors hover:bg-warn/10 active:bg-warn/20 disabled:opacity-50"
            >
              Late
            </button>
            <button
              onClick={() => submit("TEACHER_NOT_FOUND")}
              disabled={busy != null || (overriding && !reason.trim())}
              className="min-h-11 rounded-lg bg-bad-soft px-2 py-2.5 text-xs font-semibold leading-tight text-bad ring-1 ring-inset ring-bad/20 transition-colors hover:bg-bad/10 active:bg-bad/20 disabled:opacity-50"
            >
              {busy === "TEACHER_NOT_FOUND" ? "…" : "Not found"}
            </button>
          </div>

          {/* Late: one extra tap. The time is pre-filled with now. */}
          {showLate ? (
            <div className="mt-2.5 rounded-lg bg-warn-soft/60 p-2.5">
              <div className="flex items-center gap-2">
                <label className="text-xs font-medium text-warn">Arrived at</label>
                <input
                  type="time"
                  value={arrival}
                  onChange={(e) => setArrival(e.target.value)}
                  className="rounded-md border border-warn/30 bg-surface px-2 py-1.5 text-sm tabular-nums"
                />
                <button
                  onClick={() => submit("LATE", arrival)}
                  disabled={!arrival || busy != null}
                  className="ml-auto min-h-9 rounded-md bg-warn px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
                >
                  {busy === "LATE" ? "…" : "Save"}
                </button>
                <button
                  onClick={() => setShowLate(false)}
                  className="min-h-9 rounded-md px-2 py-1.5 text-sm text-ink-soft"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : null}

          {/* Remark: secondary, collapsed by default. */}
          {showRemark ? (
            <input
              value={remark}
              onChange={(e) => setRemark(e.target.value)}
              placeholder="Optional remark"
              className="mt-2.5 w-full rounded-lg border border-line px-2.5 py-2 text-sm"
            />
          ) : (
            <button
              onClick={() => setShowRemark(true)}
              className="mt-2 text-xs text-ink-faint hover:text-ink-soft"
            >
              + remark
            </button>
          )}
        </>
      )}

      {error ? (
        <p className="mt-2 rounded-md bg-bad-soft px-2 py-1.5 text-xs text-bad">{error}</p>
      ) : null}
    </div>
  );
}
