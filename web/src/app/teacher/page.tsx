"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import StatusBadge from "@/components/StatusBadge";
import {
  Button,
  Card,
  EmptyState,
  ErrorNote,
  Spinner,
  SummaryCard,
  inputClass,
} from "@/components/ui";
import { ApiError, api, todayISO } from "@/lib/api";
import { useRequireRole } from "@/lib/auth";
import type { ClassInstance, Makeup, MakeupStatus, TeacherReport } from "@/lib/types";

const MAKEUP_LABEL: Record<MakeupStatus, string> = {
  PENDING: "awaiting approval",
  SCHEDULED: "approved",
  APPROVED: "approved",
  REJECTED: "rejected",
  COMPLETED: "completed",
};

export default function TeacherPage() {
  const { user, permitted, loading: authLoading } = useRequireRole([
    "TEACHER",
    "HOD",
    "SUPER_ADMIN",
  ]);

  const [today, setToday] = useState<ClassInstance[]>([]);
  const [needsAction, setNeedsAction] = useState<ClassInstance[]>([]);
  const [makeups, setMakeups] = useState<Makeup[]>([]);
  const [stats, setStats] = useState<TeacherReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Pulled out of the callback so the dependency is the string the callback
  // actually reads, not the whole user object.
  const initial = user?.teacher_initial ?? null;

  const load = useCallback(async () => {
    if (!initial) {
      setLoading(false);
      return;
    }
    try {
      const [todays, missed, mk, report] = await Promise.all([
        api.instances({ date: todayISO() }),
        api.instances({ needs_reschedule: true, limit: 50 }),
        api.makeups(),
        api.teacherReport(initial, "2026-09-01", "2026-12-31").catch(() => null),
      ]);
      setToday(todays);
      setNeedsAction(missed);
      setMakeups(mk);
      setStats(report);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load your classes.");
    } finally {
      setLoading(false);
    }
  }, [initial]);

  useEffect(() => {
    if (!permitted) return;
    void load();
    // A staff report can land while the page is open; pick it up without a reload.
    const timer = setInterval(() => void load(), 60_000);
    return () => clearInterval(timer);
  }, [permitted, load]);

  if (authLoading || !permitted) return <Spinner />;

  if (!initial) {
    return (
      <Card className="p-6">
        <EmptyState
          title="This account is not linked to a faculty initial"
          body="An administrator needs to set your teacher initial before your schedule can be shown."
        />
      </Card>
    );
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold">My classes</h1>
        <p className="mt-0.5 text-sm text-ink-soft">
          {user?.full_name} · {initial}
        </p>
      </div>

      {error ? <ErrorNote message={error} /> : null}

      {stats ? (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          <SummaryCard label="Scheduled" value={stats.total_scheduled} />
          <SummaryCard label="Conducted" value={stats.conducted} tone="ok" />
          <SummaryCard label="Late" value={stats.late} tone="warn" />
          <SummaryCard label="Missed" value={stats.missed} tone="bad" />
          <SummaryCard
            label="Makeups done"
            value={stats.makeup_completed}
            tone="info"
            hint={`${stats.makeup_pending} pending`}
          />
        </div>
      ) : null}

      {/* Missed classes needing a response come first: they are the only thing
          on this page that requires the teacher to act. */}
      {needsAction.length > 0 ? (
        <Card className="border-bad/30">
          <div className="border-b border-line px-4 py-3">
            <h2 className="text-sm font-semibold text-bad">
              Reschedule required ({needsAction.length})
            </h2>
            <p className="mt-0.5 text-xs text-ink-soft">
              Staff reported these classes as not held. Request a new time in an
              empty room — once the Head of Department approves, it is checked
              like any other class. Dispute the record if it is wrong.
            </p>
          </div>
          <ul className="divide-y divide-line">
            {needsAction.map((inst) => (
              <MissedRow key={inst.id} instance={inst} onDone={load} />
            ))}
          </ul>
        </Card>
      ) : null}

      <Card>
        <div className="border-b border-line px-4 py-3">
          <h2 className="text-sm font-semibold">Today ({today.length})</h2>
        </div>
        {loading ? (
          <Spinner />
        ) : today.length === 0 ? (
          <EmptyState title="No classes scheduled today" />
        ) : (
          <ul className="divide-y divide-line">
            {today.map((inst) => (
              <li key={inst.id} className="flex items-center gap-3 px-4 py-3">
                <div className="w-24 shrink-0 text-sm tabular-nums text-ink-soft">
                  {inst.time_slot}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">
                    {inst.course_code} · {inst.section}
                  </p>
                  <p className="text-xs text-ink-faint">
                    {inst.room}
                    {inst.is_makeup ? " · makeup" : ""}
                  </p>
                </div>
                <StatusBadge
                  status={inst.status}
                  lateMinutes={inst.check?.late_minutes}
                />
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card>
        <div className="border-b border-line px-4 py-3">
          <h2 className="text-sm font-semibold">My makeup classes ({makeups.length})</h2>
        </div>
        {makeups.length === 0 ? (
          <EmptyState title="No makeup classes yet" />
        ) : (
          <ul className="divide-y divide-line">
            {makeups.map((m) => (
              <li key={m.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">
                    {m.original_course_code ?? "—"} · {m.original_section ?? "—"}
                  </p>
                  <p className="text-xs text-ink-faint">
                    {m.date} · {m.time_slot} · {m.mode === "ONLINE" ? "Online" : m.room}
                    {m.original_date ? ` · recovers ${m.original_date}` : ""}
                  </p>
                  {m.status === "REJECTED" ? (
                    <p className="mt-1 text-xs text-bad">
                      Request another slot from the list above.
                    </p>
                  ) : null}
                  {m.decision_note ? (
                    <p className="mt-1 text-xs italic text-ink-soft">
                      “{m.decision_note}”
                    </p>
                  ) : null}
                </div>
                <span
                  className={`rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${
                    m.status === "REJECTED"
                      ? "bg-bad-soft text-bad ring-bad/20"
                      : m.status === "PENDING"
                        ? "bg-warn-soft text-warn ring-warn/20"
                        : "bg-ok-soft text-ok ring-ok/20"
                  }`}
                >
                  {MAKEUP_LABEL[m.status]}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

function MissedRow({
  instance,
  onDone,
}: {
  instance: ClassInstance;
  onDone: () => void;
}) {
  const [mode, setMode] = useState<"idle" | "dispute">("idle");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const act = async (response: "CONFIRMED" | "DISPUTED") => {
    setBusy(true);
    setError(null);
    try {
      await api.respond(instance.id, response, note || undefined);
      onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save your response.");
    } finally {
      setBusy(false);
    }
  };

  const responded = instance.teacher_response != null;
  const reported = instance.status !== "MISSED";

  return (
    <li className="px-4 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">
            {instance.course_code} · {instance.section}
          </p>
          <p className="text-xs text-ink-faint">
            {instance.date} · {instance.time_slot} · {instance.room}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {reported ? (
            // Confirm and dispute answer a settled MISSED record; this one is
            // not settled yet, and staff may still record a late arrival.
            <span className="text-xs font-medium text-warn">Reported absent · not final yet</span>
          ) : responded ? (
            <span className="text-xs font-medium text-ink-soft">
              You marked this {instance.teacher_response?.toLowerCase()}
            </span>
          ) : (
            <>
              <Button variant="ghost" onClick={() => act("CONFIRMED")} disabled={busy}>
                Confirm
              </Button>
              <Button variant="ghost" onClick={() => setMode("dispute")} disabled={busy}>
                Dispute
              </Button>
            </>
          )}
          {/* Offered after a response too: the class is still owed either way. */}
          <Link href={`/teacher/makeup?instance=${instance.id}`}>
            <Button>Request reschedule</Button>
          </Link>
        </div>
      </div>

      {mode === "dispute" && !responded ? (
        <div className="mt-2.5 space-y-2 rounded-lg bg-canvas p-2.5">
          <input
            className={inputClass}
            placeholder="Why should this record be reviewed?"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          <div className="flex gap-2">
            <Button onClick={() => act("DISPUTED")} disabled={busy || !note.trim()}>
              Send to HoD
            </Button>
            <Button variant="ghost" onClick={() => setMode("idle")}>
              Cancel
            </Button>
          </div>
          <p className="text-xs text-ink-faint">
            The original monitoring record is kept either way — a dispute flags it
            for review, it does not erase it.
          </p>
        </div>
      ) : null}

      {error ? <p className="mt-2 text-xs text-bad">{error}</p> : null}
    </li>
  );
}
