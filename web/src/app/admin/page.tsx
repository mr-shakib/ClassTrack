"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Button, Card, EmptyState, ErrorNote, Spinner, inputClass } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { adminTab, useRequireAccess } from "@/lib/auth";
import type { IngestionReport, Routine, RoutineReview, Semester } from "@/lib/types";

export default function RoutinePage() {
  const { permitted, loading: authLoading } = useRequireAccess(adminTab("/admin"));
  const fileRef = useRef<HTMLInputElement>(null);

  const [routines, setRoutines] = useState<Routine[]>([]);
  const [semesters, setSemesters] = useState<Semester[]>([]);
  /** The semester a routine is activated for. Defaults to the current one. */
  const [target, setTarget] = useState<number | null>(null);
  const [report, setReport] = useState<IngestionReport | null>(null);
  const [review, setReview] = useState<RoutineReview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [rs, ss] = await Promise.all([api.routines(), api.semesters()]);
      setRoutines(rs);
      setSemesters(ss);
      setTarget((t) => t ?? ss.find((x) => x.is_active)?.id ?? ss[0]?.id ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load routines.");
    }
  }, []);

  useEffect(() => {
    if (permitted) void load();
  }, [permitted, load]);

  const upload = async (e: React.FormEvent) => {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("department", "cse");
      const res = await api.ingestRoutine(form);
      setReport(res);
      if (res.routine_id) setReview(await api.routineReview(res.routine_id));
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not read the PDF.");
    } finally {
      setBusy(false);
    }
  };

  const openReview = async (id: number) => {
    setBusy(true);
    setError(null);
    try {
      setReview(await api.routineReview(id));
      setReport(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load the review.");
    } finally {
      setBusy(false);
    }
  };

  const activate = async (id: number) => {
    setBusy(true);
    setError(null);
    try {
      const res = await api.activateRoutine(id, target ?? undefined);
      const semester = semesters.find((x) => x.id === target);
      setNotice(
        `Attached to ${semester?.name ?? "the current semester"}. ` +
          `${res.instances_created ?? 0} class instances created; ` +
          `${res.skipped_holidays ?? 0} days skipped for holidays and ` +
          `${res.skipped_exam_days ?? 0} for exams.` +
          (res.is_active ? "" : " It goes live when that semester is made current."),
      );
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not activate.");
    } finally {
      setBusy(false);
    }
  };

  if (authLoading || !permitted) return <Spinner />;

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <h2 className="text-sm font-semibold">Upload a routine PDF</h2>
        <p className="mt-1 text-sm text-ink-soft">
          Uploading only parses the document. Review what was extracted, then
          activate it — that review step is deliberate.
        </p>
        <form onSubmit={upload} className="mt-3 flex flex-wrap items-center gap-2">
          <input
            ref={fileRef}
            type="file"
            accept="application/pdf"
            className="text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-brand-soft file:px-3 file:py-2 file:text-sm file:font-medium file:text-brand"
          />
          <Button type="submit" disabled={busy}>
            {busy ? "Reading…" : "Parse"}
          </Button>
        </form>
      </Card>

      {error ? <ErrorNote message={error} /> : null}
      {notice ? (
        <div className="rounded-lg border border-ok/20 bg-ok-soft px-3 py-2 text-sm text-ok">
          {notice}
        </div>
      ) : null}

      {report ? (
        <Card className="p-4">
          <h2 className="text-sm font-semibold">Extraction report</h2>
          <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Cells read" value={report.cells_read} />
            <Stat label="Classes created" value={report.sessions_created} />
            <Stat label="Reserved" value={report.reserved} />
            <Stat
              label="Skipped"
              value={report.skipped}
              tone={report.skipped > 0 ? "text-warn" : undefined}
            />
          </div>
          {report.skipped_sample.length > 0 ? (
            <div className="mt-3 rounded-lg border border-warn/20 bg-warn-soft p-3">
              <p className="text-sm font-semibold text-warn">
                These cells could not be parsed and need a human look
              </p>
              <ul className="mt-1.5 space-y-1">
                {report.skipped_sample.map((s, i) => (
                  <li key={i} className="text-xs text-warn">
                    p{s.page} · {s.day} {s.time_slot} · {s.room} —{" "}
                    <code>{s.text}</code>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </Card>
      ) : null}

      {review ? (
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3">
            <div>
              <h2 className="text-sm font-semibold">
                Review · {review.routine.version}
                {review.routine.is_active ? (
                  <span className="ml-2 rounded-full bg-ok-soft px-2 py-0.5 text-xs font-semibold text-ok">
                    active
                  </span>
                ) : null}
              </h2>
              <p className="text-xs text-ink-faint">
                {review.total_sessions} classes · {review.conflicts.length} issues
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {semesters.length ? (
                <label className="flex items-center gap-2 text-sm text-ink-soft">
                  For
                  <select
                    className={inputClass}
                    value={target ?? ""}
                    onChange={(e) => setTarget(Number(e.target.value))}
                  >
                    {semesters.map((x) => (
                      <option key={x.id} value={x.id}>
                        {x.name}
                        {x.is_active ? " (current)" : ""}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
              <Button onClick={() => activate(review.routine.id)} disabled={busy}>
                {semesters.some((x) => x.id === target && x.routine_id === review.routine.id)
                  ? "Re-activate & regenerate"
                  : "Activate & generate instances"}
              </Button>
            </div>
          </div>

          {review.conflicts.length > 0 ? (
            <div className="border-b border-line bg-bad-soft/50 px-4 py-3">
              <p className="text-sm font-semibold text-bad">
                {review.conflicts.length} issue
                {review.conflicts.length === 1 ? "" : "s"} detected
              </p>
              <ul className="mt-1.5 max-h-40 space-y-0.5 overflow-y-auto">
                {review.conflicts.slice(0, 40).map((c, i) => (
                  <li key={i} className="text-xs text-bad">
                    <span className="font-semibold">{c.type}:</span> {c.message}
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <div className="border-b border-line bg-ok-soft/50 px-4 py-2.5 text-sm text-ok">
              No duplicate rooms, teacher clashes, or missing fields detected.
            </div>
          )}

          <div className="max-h-96 overflow-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-surface">
                <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-faint">
                  <th className="px-4 py-2 font-medium">Day</th>
                  <th className="px-4 py-2 font-medium">Slot</th>
                  <th className="px-4 py-2 font-medium">Room</th>
                  <th className="px-4 py-2 font-medium">Course</th>
                  <th className="px-4 py-2 font-medium">Section</th>
                  <th className="px-4 py-2 font-medium">Teacher</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {review.sessions.map((s, i) => (
                  <tr key={i}>
                    <td className="px-4 py-1.5">{s.day}</td>
                    <td className="px-4 py-1.5 tabular-nums">{s.time_slot}</td>
                    <td className="px-4 py-1.5">{s.room}</td>
                    <td className="px-4 py-1.5">{s.course_code}</td>
                    <td className="px-4 py-1.5">{s.section}</td>
                    <td className="px-4 py-1.5">{s.teacher}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}

      <Card>
        <div className="border-b border-line px-4 py-3">
          <h2 className="text-sm font-semibold">Routine revisions</h2>
        </div>
        {routines.length === 0 ? (
          <EmptyState title="No routines yet" body="Upload a PDF to get started." />
        ) : (
          <ul className="divide-y divide-line">
            {routines.map((r) => (
              <li key={r.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">
                    {r.version}
                    {r.is_active ? (
                      <span className="ml-2 rounded-full bg-ok-soft px-2 py-0.5 text-xs font-semibold text-ok">
                        active
                      </span>
                    ) : null}
                  </p>
                  <p className="text-xs text-ink-faint">
                    {r.session_count} classes · {r.source_filename ?? "—"}
                    {semesters
                      .filter((x) => x.routine_id === r.id)
                      .map((x) => ` · ${x.name}`)
                      .join("")}
                  </p>
                </div>
                <Button variant="secondary" onClick={() => openReview(r.id)}>
                  Review
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: string;
}) {
  return (
    <div className="rounded-lg bg-canvas px-3 py-2">
      <div className="text-xs text-ink-faint">{label}</div>
      <div className={`text-xl font-semibold tabular-nums ${tone ?? ""}`}>{value}</div>
    </div>
  );
}
