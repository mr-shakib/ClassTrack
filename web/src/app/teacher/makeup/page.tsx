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
import { ApiError, SLOTS, api } from "@/lib/api";
import { useRequireRole } from "@/lib/auth";
import type { ClassInstance, ConflictReport, MakeupMode } from "@/lib/types";

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

  // Validate as the teacher types, so a conflict is visible before they submit
  // rather than as a rejection afterwards.
  const validate = useCallback(async () => {
    if (!date || !slot || !original) {
      setReport(null);
      return;
    }
    if (mode === "PHYSICAL" && !room.trim()) {
      setReport(null);
      return;
    }
    setChecking(true);
    try {
      setReport(
        await api.checkConflict({
          date,
          time_slot: slot,
          room: mode === "PHYSICAL" ? room.trim().toUpperCase() : null,
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
        room: mode === "PHYSICAL" ? room.trim().toUpperCase() : null,
        reason: reason || null,
      });
      setDone(true);
      setTimeout(() => router.push("/teacher"), 1400);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not schedule the makeup class.",
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
          to schedule its makeup.
        </p>
      </Card>
    );
  }

  if (done) {
    return (
      <Card className="p-6 text-center">
        <p className="text-lg font-semibold text-ok">Makeup class submitted</p>
        <p className="mt-1 text-sm text-ink-soft">
          {mode === "ONLINE"
            ? "Sent to the Head of Department for approval."
            : "Added to the room-wise checking schedule."}
        </p>
      </Card>
    );
  }

  const blocked = report != null && !report.ok;

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Schedule a makeup class</h1>
        <p className="mt-0.5 text-sm text-ink-soft">
          The makeup stays linked to the class it recovers.
        </p>
      </div>

      {original ? (
        <Card className="p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-faint">
            Recovering
          </p>
          <p className="mt-1 text-sm font-medium">
            {original.course_code} · {original.section}
          </p>
          <p className="text-xs text-ink-soft">
            Missed on {original.date} · {original.time_slot} · {original.room}
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
                  {m === "PHYSICAL" ? "Physical" : "Online"}
                </button>
              ))}
            </div>
            <p className="mt-1.5 text-xs text-ink-faint">
              {mode === "PHYSICAL"
                ? "Enters the normal room-wise checking list."
                : "Needs Head of Department approval, and is excluded from physical checking."}
            </p>
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Date">
              <input
                type="date"
                className={inputClass}
                value={date}
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
            <Field label="Room">
              <input
                className={inputClass}
                placeholder="e.g. KT-305"
                value={room}
                onChange={(e) => setRoom(e.target.value)}
                required
              />
            </Field>
          ) : null}

          <Field label="Reason">
            <input
              className={inputClass}
              placeholder="Why was the class missed?"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </Field>

          {/* Live conflict feedback (BR-14). */}
          {checking ? (
            <p className="text-xs text-ink-faint">Checking availability…</p>
          ) : report ? (
            report.ok ? (
              <div className="rounded-lg border border-ok/20 bg-ok-soft px-3 py-2 text-sm text-ok">
                No conflicts — this slot is free.
              </div>
            ) : (
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
            )
          ) : null}

          {error ? <ErrorNote message={error} /> : null}

          <Button
            type="submit"
            size="lg"
            className="w-full"
            disabled={busy || blocked || !date || !original}
          >
            {busy
              ? "Submitting…"
              : blocked
                ? "Resolve the conflict first"
                : mode === "ONLINE"
                  ? "Request approval"
                  : "Schedule makeup"}
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
