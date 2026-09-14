"use client";

import { useCallback, useEffect, useState } from "react";
import { MakeupTimes, ModeBadge } from "@/components/MakeupTracker";
import { Button, Card, EmptyState, ErrorNote, Spinner, bigInputClass } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { ADMIN_ROLES, useRequireRole } from "@/lib/auth";
import type { Makeup } from "@/lib/types";

export default function ApprovalsPage() {
  const { permitted, loading: authLoading } = useRequireRole(ADMIN_ROLES);
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
    <div className="mx-auto max-w-3xl space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          Reschedule approvals{rows.length > 0 ? ` (${rows.length})` : ""}
        </h1>
        <p className="mt-1 text-base text-ink-soft">
          Approve an in-room request and it joins the staff checking list for that room
          and time. Reject it and the teacher must pick another slot. An approved online
          class is excluded from room checking. Open the teacher&apos;s Drive link here if
          they attached one; otherwise they add it after the class.
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
        <div className="space-y-4">
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
    <article className="overflow-hidden rounded-2xl border-2 border-line bg-surface">
      <header className="flex flex-wrap items-start justify-between gap-3 p-4 sm:p-5">
        <div className="min-w-0">
          <p className="text-2xl font-bold tracking-tight">
            {makeup.original_course_code ?? "—"}
          </p>
          <p className="text-lg text-ink-soft">
            Section {makeup.original_section ?? "—"} ·{" "}
            {makeup.teacher_name ?? makeup.teacher_initial} ({makeup.teacher_initial})
          </p>
        </div>
        <ModeBadge makeup={makeup} />
      </header>

      <div className="space-y-4 px-4 pb-5 sm:px-5">
        <MakeupTimes makeup={makeup} newLabel="Requested new time" />
        {makeup.reason ? (
          <p className="rounded-xl border-2 border-line px-4 py-3 text-base">
            <span className="font-semibold">Reason: </span>
            {makeup.reason}
          </p>
        ) : null}
        {makeup.mode === "ONLINE" ? (
          makeup.drive_link ? (
            <a
              href={makeup.drive_link}
              target="_blank"
              rel="noopener noreferrer"
              className="flex min-h-14 items-center justify-between gap-3 rounded-xl bg-info-soft px-4 py-3 text-lg font-bold text-info ring-2 ring-inset ring-info/25 hover:bg-info/10"
            >
              <span>Drive link from the teacher</span>
              <span aria-hidden className="shrink-0 whitespace-nowrap">
                Open ↗
              </span>
            </a>
          ) : (
            <p className="rounded-xl bg-canvas px-4 py-3 text-base text-ink-soft">
              No Drive link attached to this request.
            </p>
          )
        ) : null}
      </div>

      <footer className="space-y-3 border-t-2 border-line bg-canvas p-4 sm:p-5">
        <input
          className={bigInputClass}
          placeholder="Note for the teacher (optional)"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />

        {error ? (
          <p className="rounded-xl bg-bad-soft px-4 py-3 text-base font-semibold text-bad">
            {error}
          </p>
        ) : null}

        <div className="grid grid-cols-2 gap-3">
          <Button size="xl" onClick={() => decide("APPROVE")} disabled={busy}>
            Approve
          </Button>
          <Button size="xl" variant="danger" onClick={() => decide("REJECT")} disabled={busy}>
            Reject
          </Button>
        </div>
      </footer>
    </article>
  );
}
