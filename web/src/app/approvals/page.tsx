"use client";

import { useCallback, useEffect, useState } from "react";
import { Button, Card, EmptyState, ErrorNote, Spinner, inputClass } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useRequireRole } from "@/lib/auth";
import type { Makeup } from "@/lib/types";

export default function ApprovalsPage() {
  const { permitted, loading: authLoading } = useRequireRole(["HOD", "SUPER_ADMIN"]);
  const [rows, setRows] = useState<Makeup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setRows(await api.pendingApprovals());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load requests.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (permitted) void load();
  }, [permitted, load]);

  if (authLoading || !permitted) return <Spinner />;

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Reschedule approvals</h1>
        <p className="mt-0.5 text-sm text-ink-soft">
          Approve an in-room request and it joins the staff checking list for that
          room and time. Reject it and the teacher must pick another slot. An
          approved online class is excluded from room checking.
        </p>
      </div>

      {error ? <ErrorNote message={error} /> : null}

      {loading ? (
        <Spinner />
      ) : rows.length === 0 ? (
        <Card>
          <EmptyState
            title="Nothing awaiting a decision"
            body="Reschedule requests from teachers will appear here."
          />
        </Card>
      ) : (
        <div className="space-y-3">
          {rows.map((m) => (
            <RequestCard key={m.id} makeup={m} onDone={load} />
          ))}
        </div>
      )}
    </div>
  );
}

function RequestCard({ makeup, onDone }: { makeup: Makeup; onDone: () => void }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const decide = async (decision: "APPROVE" | "REJECT") => {
    setBusy(true);
    setError(null);
    try {
      await api.decide(makeup.id, decision, note || undefined);
      onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not record the decision.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold">
            {makeup.original_course_code ?? "—"} · {makeup.original_section ?? "—"}
          </p>
          <p className="mt-0.5 text-xs text-ink-soft">
            {makeup.teacher_name ?? makeup.teacher_initial} ({makeup.teacher_initial})
          </p>
        </div>
        <span className="rounded-full bg-warn-soft px-2.5 py-1 text-xs font-semibold text-warn ring-1 ring-inset ring-warn/20">
          {makeup.mode === "ONLINE" ? "online" : "in room"} · pending
        </span>
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-xs text-ink-faint">New date</dt>
          <dd className="font-medium tabular-nums">{makeup.date}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-faint">Slot</dt>
          <dd className="font-medium tabular-nums">{makeup.time_slot}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-faint">Room</dt>
          <dd className="font-medium">{makeup.mode === "ONLINE" ? "Online" : makeup.room}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-faint">Missed class</dt>
          <dd className="font-medium tabular-nums">
            {makeup.original_date ?? "—"}
            {makeup.original_time_slot ? (
              <span className="block text-xs font-normal text-ink-soft">
                {makeup.original_time_slot} · {makeup.original_room}
              </span>
            ) : null}
          </dd>
        </div>
      </dl>

      {makeup.reason ? (
        <p className="mt-3 rounded-lg bg-canvas px-3 py-2 text-sm text-ink-soft">
          <span className="font-medium">Reason: </span>
          {makeup.reason}
        </p>
      ) : null}

      <input
        className={`${inputClass} mt-3`}
        placeholder="Note for the teacher (optional)"
        value={note}
        onChange={(e) => setNote(e.target.value)}
      />

      {error ? <p className="mt-2 text-xs text-bad">{error}</p> : null}

      <div className="mt-3 flex gap-2">
        <Button onClick={() => decide("APPROVE")} disabled={busy}>
          Approve
        </Button>
        <Button variant="danger" onClick={() => decide("REJECT")} disabled={busy}>
          Reject
        </Button>
      </div>
    </Card>
  );
}
