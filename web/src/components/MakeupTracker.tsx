"use client";

import { useState } from "react";
import { ApiError, api } from "@/lib/api";
import type { Makeup } from "@/lib/types";
import { Button, bigInputClass } from "./ui";

const STEPS = ["Requested", "Approved", "Class time", "Done"] as const;

/** "Sunday, 20 September 2026" -- spelled out, so nobody misreads a date. */
export const formatDay = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString([], {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });

/** A reschedule the teacher still has to see through: undecided, or approved and not done. */
export const isOpenMakeup = (m: Makeup) =>
  m.status === "PENDING" || m.status === "SCHEDULED" || m.status === "APPROVED";

/** The step the makeup is waiting on, as an index into STEPS. */
function currentStep(m: Makeup, ended: boolean): number {
  if (m.status === "COMPLETED") return STEPS.length;
  if (m.status === "PENDING") return 1;
  return ended ? 3 : 2;
}

function CheckIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M5 12.5l4.5 4.5L19 7.5" />
    </svg>
  );
}

/** Online or in a room, in words and an icon, large enough to read at a glance. */
export function ModeBadge({ makeup }: { makeup: Makeup }) {
  const online = makeup.mode === "ONLINE";
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-2 rounded-xl px-3 py-2 text-base font-bold ring-2 ring-inset ${
        online ? "bg-info-soft text-info ring-info/25" : "bg-brand-soft text-brand ring-brand/25"
      }`}
    >
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        {online ? (
          <>
            <rect x="3" y="4" width="18" height="12" rx="2" />
            <path d="M8 20h8M12 16v4" />
          </>
        ) : (
          <>
            <path d="M4 21h16M6 21V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v17" />
            <circle cx="14.5" cy="12" r="1" fill="currentColor" />
          </>
        )}
      </svg>
      {online ? "Online class" : `In class · ${makeup.room}`}
    </span>
  );
}

/** The missed class beside its new time, the new time emphasised. */
export function MakeupTimes({
  makeup: m,
  newLabel = "Rescheduled to",
}: {
  makeup: Makeup;
  newLabel?: string;
}) {
  const online = m.mode === "ONLINE";
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <div className="rounded-xl bg-canvas p-3 sm:p-4">
        <p className="text-sm font-bold uppercase tracking-wide text-ink-faint">Missed class</p>
        <p className="mt-1 text-lg font-semibold">
          {m.original_date ? formatDay(m.original_date) : "—"}
        </p>
        <p className="text-base tabular-nums text-ink-soft">
          {[m.original_time_slot, m.original_room].filter(Boolean).join(" · ") || "—"}
        </p>
      </div>
      <div className="rounded-xl bg-brand-soft p-3 ring-2 ring-inset ring-brand/20 sm:p-4">
        <p className="text-sm font-bold uppercase tracking-wide text-brand">{newLabel}</p>
        <p className="mt-1 text-xl font-bold">{formatDay(m.date)}</p>
        <p className="text-lg font-semibold tabular-nums">
          {m.time_slot} · {online ? "Online" : `Room ${m.room}`}
        </p>
      </div>
    </div>
  );
}

function Steps({ step }: { step: number }) {
  return (
    <ol className="grid grid-cols-4 gap-2">
      {STEPS.map((label, i) => {
        const done = i < step;
        const current = i === step;
        return (
          <li
            key={label}
            aria-current={current ? "step" : undefined}
            className="flex flex-col items-center text-center"
          >
            <span
              className={`flex size-10 items-center justify-center rounded-full text-lg font-bold ${
                done
                  ? "bg-ok text-white"
                  : current
                    ? "bg-warn text-white ring-4 ring-warn/25"
                    : "bg-canvas text-ink-faint ring-2 ring-inset ring-line"
              }`}
            >
              {done ? <CheckIcon /> : i + 1}
            </span>
            <span
              className={`mt-1.5 text-sm font-semibold leading-tight ${
                done ? "text-ok" : current ? "text-warn" : "text-ink-faint"
              }`}
            >
              {label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

/**
 * One open reschedule: which class moved, to when and where, how far along it
 * is, and the one thing the teacher can do next. It stays on the page until the
 * teacher marks the class done.
 */
export function MakeupCard({
  makeup: m,
  now,
  onChanged,
}: {
  makeup: Makeup;
  /** Epoch ms, passed in so the card renders the same on every pass. */
  now: number;
  onChanged: () => void;
}) {
  // A link sent with the request is already on file; start from it.
  const [link, setLink] = useState(m.drive_link ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const online = m.mode === "ONLINE";
  const pending = m.status === "PENDING";
  const ended = m.ends_at != null && new Date(m.ends_at).getTime() <= now;

  const markDone = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.completeMakeup(m.id, online ? link.trim() : undefined);
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not mark the class done.");
    } finally {
      setBusy(false);
    }
  };

  const footerTone = pending
    ? "border-line bg-canvas"
    : ended
      ? "border-warn/25 bg-warn-soft"
      : "border-ok/20 bg-ok-soft";

  return (
    <li id={`makeup-${m.id}`} className="scroll-mt-24">
      <article className="overflow-hidden rounded-2xl border-2 border-line bg-surface">
        <header className="flex flex-wrap items-start justify-between gap-3 p-4 sm:p-5">
          <div className="min-w-0">
            <p className="text-2xl font-bold tracking-tight">{m.original_course_code ?? "—"}</p>
            <p className="text-lg text-ink-soft">Section {m.original_section ?? "—"}</p>
          </div>
          <ModeBadge makeup={m} />
        </header>

        <div className="space-y-5 px-4 pb-5 sm:px-5">
          <MakeupTimes makeup={m} />
          <Steps step={currentStep(m, ended)} />
          {m.decision_note ? (
            <p className="rounded-xl border-2 border-line px-4 py-3 text-base">
              <span className="font-semibold">Head of Department: </span>“{m.decision_note}”
            </p>
          ) : null}
          {m.drive_link ? (
            <a
              href={m.drive_link}
              target="_blank"
              rel="noopener noreferrer"
              className="flex min-h-12 items-center justify-between gap-3 rounded-xl border-2 border-line px-4 py-2 text-base font-semibold text-brand hover:bg-brand-soft"
            >
              <span>Drive link sent</span>
              <span aria-hidden className="shrink-0 whitespace-nowrap">
                Open ↗
              </span>
            </a>
          ) : null}
        </div>

        <footer className={`border-t-2 p-4 sm:p-5 ${footerTone}`}>
          {pending ? (
            <>
              <p className="text-lg font-bold">Waiting for the Head of Department</p>
              <p className="mt-1 text-base text-ink-soft">
                You will get a notification as soon as they decide.
              </p>
            </>
          ) : !ended ? (
            <>
              <p className="text-lg font-bold text-ok">Approved — hold the class at the new time</p>
              <p className="mt-1 text-base">
                {online
                  ? m.drive_link
                    ? "It is not checked in a room. Your Drive link is saved — after the class, come back here and mark it done."
                    : "It is not checked in a room. After it ends, come back here and submit its Drive link."
                  : `Staff will check room ${m.room}. After the class, come back here and mark it done.`}
              </p>
            </>
          ) : online ? (
            <div className="space-y-3">
              <p className="text-lg font-bold text-warn">
                {m.drive_link
                  ? "Class time is over — confirm the Drive link"
                  : "Class time is over — submit the Drive link"}
              </p>
              <label className="block">
                <span className="mb-1.5 block text-base font-semibold">Drive link</span>
                <input
                  type="url"
                  inputMode="url"
                  className={bigInputClass}
                  placeholder="https://drive.google.com/…"
                  value={link}
                  onChange={(e) => setLink(e.target.value)}
                />
              </label>
              <Button size="xl" className="w-full" onClick={markDone} disabled={busy || !link.trim()}>
                {busy ? "Saving…" : "Submit link & mark done"}
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-lg font-bold text-warn">Class time is over — did you hold it?</p>
              <Button size="xl" className="w-full" onClick={markDone} disabled={busy}>
                {busy ? "Saving…" : "Yes, mark as done"}
              </Button>
            </div>
          )}
          {error ? (
            <p className="mt-3 rounded-xl bg-bad-soft px-4 py-3 text-base font-semibold text-bad">
              {error}
            </p>
          ) : null}
        </footer>
      </article>
    </li>
  );
}

/** A finished reschedule: done (with its Drive link, if online) or rejected. */
export function MakeupHistoryRow({ makeup: m }: { makeup: Makeup }) {
  const online = m.mode === "ONLINE";
  const done = m.status === "COMPLETED";
  return (
    <li
      id={`makeup-${m.id}`}
      className="flex scroll-mt-24 flex-wrap items-start gap-3 px-4 py-4 sm:px-5"
    >
      <div className="min-w-0 flex-1">
        <p className="text-lg font-semibold">
          {m.original_course_code ?? "—"} · {m.original_section ?? "—"}
        </p>
        <p className="text-base text-ink-soft">
          {formatDay(m.date)} · {m.time_slot} · {online ? "Online" : `Room ${m.room}`}
        </p>
        {m.original_date ? (
          <p className="text-sm text-ink-faint">
            Makes up the class missed on {formatDay(m.original_date)}
          </p>
        ) : null}
        {m.drive_link ? (
          <a
            href={m.drive_link}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 inline-flex min-h-11 items-center rounded-lg bg-brand-soft px-3 text-base font-semibold text-brand hover:bg-brand/10"
          >
            Open Drive link ↗
          </a>
        ) : null}
        {m.status === "REJECTED" && !online ? (
          <p className="mt-1 text-base font-medium text-bad">
            Request another slot from “Reschedule required” above.
          </p>
        ) : null}
        {m.decision_note ? (
          <p className="mt-1 text-base italic text-ink-soft">“{m.decision_note}”</p>
        ) : null}
      </div>
      <span
        className={`rounded-full px-3 py-1.5 text-sm font-bold ring-1 ring-inset ${
          done ? "bg-ok-soft text-ok ring-ok/20" : "bg-bad-soft text-bad ring-bad/20"
        }`}
      >
        {done ? "Done" : "Rejected"}
      </span>
    </li>
  );
}
