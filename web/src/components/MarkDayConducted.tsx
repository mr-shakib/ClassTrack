"use client";

import { useState } from "react";
import { Button, ErrorNote, Field, bigInputClass } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import type { MarkDay } from "@/lib/types";

const longDate = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString([], {
    weekday: "long",
    day: "numeric",
    month: "long",
  });

const classes = (n: number) => `${n} class${n === 1 ? "" : "es"}`;

/**
 * For a day monitoring was off: record every class nobody reported as held.
 *
 * It shows what it will touch and what it leaves alone before anything
 * changes, because one press reaches every class of the day. Give it a `key`
 * of the date, so picking another day starts over.
 */
export function MarkDayConducted({ date, onMarked }: { date: string; onMarked: () => void }) {
  const [open, setOpen] = useState(false);
  const [preview, setPreview] = useState<MarkDay | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const start = async () => {
    setOpen(true);
    setPreview(null);
    setError(null);
    setNotice(null);
    try {
      setPreview(await api.dayToMark(date));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not count the day's classes.");
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const done = await api.markDayConducted(date, reason.trim() || null);
      setOpen(false);
      setReason("");
      setNotice(`${classes(done.marked)} recorded as held.`);
      onMarked();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not mark the day.");
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <div className="space-y-2">
        <Button variant="secondary" size="lg" className="w-full" onClick={() => void start()}>
          Monitoring was off? Mark the day conducted
        </Button>
        {notice ? (
          <p className="rounded-xl bg-ok-soft px-4 py-3 text-base font-semibold text-ok">
            {notice}
          </p>
        ) : null}
      </div>
    );
  }

  const nothing = preview != null && preview.unreported === 0;

  return (
    <form onSubmit={submit} className="space-y-4 rounded-2xl border-2 border-line bg-surface p-4">
      <div>
        <h2 className="text-xl font-bold">Mark {longDate(date)} conducted</h2>
        <p className="mt-1 text-base text-ink-soft">
          For a day monitoring was off. Every class nobody reported is recorded as held.
        </p>
      </div>

      {preview ? (
        <ul className="space-y-1.5 text-base">
          <li>
            <span className="font-bold text-ok">{classes(preview.unreported)}</span> nobody
            reported: recorded as held
          </li>
          <li className="text-ink-soft">
            {classes(preview.reported)} already reported: keep their report
          </li>
          {preview.other > 0 ? (
            <li className="text-ink-soft">
              {classes(preview.other)} cancelled or rescheduled: left as they are
            </li>
          ) : null}
        </ul>
      ) : error ? null : (
        <p className="text-base text-ink-faint">Counting the day&apos;s classes…</p>
      )}

      {nothing ? null : (
        <Field label="Why was monitoring off?" size="lg" hint="Optional. Kept with each class in the audit log.">
          <input
            className={bigInputClass}
            placeholder="e.g. Office staff on leave"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </Field>
      )}

      {error ? <ErrorNote message={error} /> : null}

      <div className="flex flex-wrap gap-2">
        <Button type="submit" size="xl" disabled={busy || preview == null || nothing}>
          {busy
            ? "Marking…"
            : preview == null
              ? "Mark the day conducted"
              : nothing
                ? "Nothing to mark"
                : `Mark ${classes(preview.unreported)} conducted`}
        </Button>
        <Button type="button" variant="ghost" size="xl" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
