"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  MakeupCard,
  MakeupHistoryRow,
  formatDay,
  isOpenMakeup,
} from "@/components/MakeupTracker";
import { ExtraTag, RescheduledTag } from "@/components/Rescheduled";
import StatusBadge from "@/components/StatusBadge";
import {
  Button,
  Card,
  EmptyState,
  ErrorNote,
  Spinner,
  SummaryCard,
  bigInputClass,
} from "@/components/ui";
import { ApiError, api, todayISO } from "@/lib/api";
import { ADMIN_ROLES, useRequireRole } from "@/lib/auth";
import type { ClassInstance, Makeup, Role, TeacherReport } from "@/lib/types";

const TEACHER_PAGE_ROLES: Role[] = ["TEACHER", ...ADMIN_ROLES];

export default function TeacherPage() {
  const { user, permitted, loading: authLoading } = useRequireRole(TEACHER_PAGE_ROLES);

  const [today, setToday] = useState<ClassInstance[]>([]);
  const [needsAction, setNeedsAction] = useState<ClassInstance[]>([]);
  const [makeups, setMakeups] = useState<Makeup[]>([]);
  const [stats, setStats] = useState<TeacherReport | null>(null);
  // Refreshed with the data, so "has this makeup ended yet" moves on its own.
  const [now, setNow] = useState(0);
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
        // The current semester so far. None yet, or not begun: no figures.
        api.teacherReport(initial, { term: "FULL" }).catch(() => null),
      ]);
      setToday(todays);
      setNeedsAction(missed);
      setNow(Date.now());
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

  // A notification links to /teacher#makeup-<id>; the card only exists once the
  // data has loaded, so scroll to it then.
  useEffect(() => {
    if (loading) return;
    const id = window.location.hash.slice(1);
    if (id.startsWith("makeup-")) {
      document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [loading]);

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

  // Soonest first, so the next class to hold is at the top.
  const openMakeups = makeups.filter(isOpenMakeup).sort((a, b) => a.date.localeCompare(b.date));
  const pastMakeups = makeups.filter((m) => !isOpenMakeup(m));

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">My classes</h1>
          <p className="mt-1 text-base text-ink-soft">
            {user?.full_name} · {initial}
          </p>
        </div>
        {/* Admins see this page too, but have no sections to book for. */}
        {user?.role === "TEACHER" ? (
          <Link
            href="/teacher/extra"
            className="inline-flex min-h-12 items-center justify-center rounded-lg bg-brand px-4 py-3 text-base font-semibold text-white hover:bg-brand/90"
          >
            Book an extra class
          </Link>
        ) : null}
      </div>

      {error ? <ErrorNote message={error} /> : null}

      {stats ? (
        <section className="space-y-2">
          <p className="text-sm text-ink-faint">
            {stats.label} · {stats.range.from} to {stats.range.to}
          </p>
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
        </section>
      ) : null}

      {/* Missed classes needing a response come first: they are the only thing
          on this page that requires the teacher to act. */}
      {needsAction.length > 0 ? (
        <section className="overflow-hidden rounded-2xl border-2 border-bad/30 bg-surface">
          <div className="border-b-2 border-bad/20 bg-bad-soft px-4 py-4 sm:px-5">
            <h2 className="text-xl font-bold text-bad">
              Reschedule required ({needsAction.length})
            </h2>
            <p className="mt-1 text-base text-ink-soft">
              Staff reported these classes as not held. Pick a new time and an empty
              room — it is booked straight away, with no approval, and checked like any
              other class. Dispute the record if it is wrong.
            </p>
          </div>
          <ul className="divide-y-2 divide-line">
            {needsAction.map((inst) => (
              <MissedRow key={inst.id} instance={inst} onDone={load} />
            ))}
          </ul>
        </section>
      ) : null}

      {openMakeups.length > 0 ? (
        <section className="space-y-3">
          <div>
            <h2 className="text-xl font-bold">Rescheduled classes ({openMakeups.length})</h2>
            <p className="mt-1 text-base text-ink-soft">
              Each one stays here until you mark it done after the class. An online class
              needs its Drive link.
            </p>
          </div>
          <ul className="space-y-4">
            {openMakeups.map((m) => (
              <MakeupCard key={m.id} makeup={m} now={now} onChanged={load} />
            ))}
          </ul>
        </section>
      ) : null}

      <Card>
        <div className="border-b border-line px-4 py-4 sm:px-5">
          <h2 className="text-xl font-bold">Today ({today.length})</h2>
        </div>
        {loading ? (
          <Spinner />
        ) : today.length === 0 ? (
          <EmptyState title="No classes scheduled today" />
        ) : (
          <ul className="divide-y divide-line">
            {today.map((inst) => (
              <li
                key={inst.id}
                className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-4 sm:px-5"
              >
                <div className="w-32 shrink-0 text-lg font-semibold tabular-nums">
                  {inst.time_slot}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-lg font-semibold">
                    {inst.course_code} · {inst.section}
                  </p>
                  <p className="text-base text-ink-soft">{inst.room}</p>
                  {inst.is_makeup ? (
                    <div className="mt-1">
                      <RescheduledTag from={inst.rescheduled_from} />
                    </div>
                  ) : inst.is_extra ? (
                    <div className="mt-1">
                      <ExtraTag />
                    </div>
                  ) : null}
                </div>
                <StatusBadge
                  status={inst.status}
                  lateMinutes={inst.check?.late_minutes}
                  size="lg"
                />
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card>
        <div className="border-b border-line px-4 py-4 sm:px-5">
          <h2 className="text-xl font-bold">Past reschedules ({pastMakeups.length})</h2>
        </div>
        {pastMakeups.length === 0 ? (
          <EmptyState title="No finished reschedules yet" />
        ) : (
          <ul className="divide-y divide-line">
            {pastMakeups.map((m) => (
              <MakeupHistoryRow key={m.id} makeup={m} />
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
    <li className="px-4 py-4 sm:px-5">
      <p className="text-2xl font-bold tracking-tight">{instance.course_code}</p>
      <p className="text-lg text-ink-soft">Section {instance.section}</p>
      <p className="mt-1 text-base tabular-nums">
        {formatDay(instance.date)} · {instance.time_slot} · {instance.room}
      </p>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {reported ? (
          // Confirm and dispute answer a settled MISSED record; this one is
          // not settled yet, and staff may still record a late arrival.
          <span className="rounded-lg bg-warn-soft px-3 py-2 text-base font-semibold text-warn">
            Reported absent · not final yet
          </span>
        ) : responded ? (
          <span className="text-base font-medium text-ink-soft">
            You marked this {instance.teacher_response?.toLowerCase()}
          </span>
        ) : (
          <>
            <Button variant="secondary" size="lg" onClick={() => act("CONFIRMED")} disabled={busy}>
              Confirm
            </Button>
            <Button variant="secondary" size="lg" onClick={() => setMode("dispute")} disabled={busy}>
              Dispute
            </Button>
          </>
        )}
      </div>

      {/* Offered after a response too: the class is still owed either way. */}
      <Link href={`/teacher/makeup?instance=${instance.id}`} className="mt-3 block">
        <Button size="xl" className="w-full">
          Request reschedule
        </Button>
      </Link>

      {mode === "dispute" && !responded ? (
        <div className="mt-3 space-y-3 rounded-xl bg-canvas p-3 sm:p-4">
          <input
            className={bigInputClass}
            placeholder="Why should this record be reviewed?"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          <div className="flex flex-wrap gap-2">
            <Button size="lg" onClick={() => act("DISPUTED")} disabled={busy || !note.trim()}>
              Send to HoD
            </Button>
            <Button variant="ghost" size="lg" onClick={() => setMode("idle")}>
              Cancel
            </Button>
          </div>
          <p className="text-sm text-ink-soft">
            The original monitoring record is kept either way — a dispute flags it for
            review, it does not erase it.
          </p>
        </div>
      ) : null}

      {error ? (
        <p className="mt-3 rounded-xl bg-bad-soft px-4 py-3 text-base font-semibold text-bad">
          {error}
        </p>
      ) : null}
    </li>
  );
}
