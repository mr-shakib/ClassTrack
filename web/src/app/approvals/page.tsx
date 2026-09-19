"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { shortDay } from "@/components/Rescheduled";
import { Button, Card, EmptyState, ErrorNote, Spinner, inputClass } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { ADMIN_ROLES, useRequireRole } from "@/lib/auth";
import type { Makeup, MakeupMode } from "@/lib/types";

export default function ApprovalsPage() {
  const { permitted, loading: authLoading } = useRequireRole(ADMIN_ROLES);
  const [rows, setRows] = useState<Makeup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<MakeupMode | "">("");

  const shown = useMemo(() => {
    const q = query.trim().toUpperCase();
    return rows.filter(
      (m) =>
        (!mode || m.mode === mode) &&
        (!q ||
          m.teacher_initial.toUpperCase().startsWith(q) ||
          (m.teacher_name ?? "").toUpperCase().includes(q) ||
          (m.original_course_code ?? "").toUpperCase().includes(q)),
    );
  }, [rows, query, mode]);
  const teachers = new Set(rows.map((m) => m.teacher_initial)).size;

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
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="max-w-3xl">
          <h1 className="text-2xl font-bold tracking-tight">
            Reschedule approvals{rows.length > 0 ? ` (${rows.length})` : ""}
          </h1>
          <p className="mt-1 text-base text-ink-soft">
            {rows.length > 0
              ? `${rows.length} request${rows.length === 1 ? "" : "s"} from ${teachers} teacher${teachers === 1 ? "" : "s"}, oldest first. `
              : ""}
            An approved in-room class joins staff checking for that room and time; an approved
            online class is left out of it. A rejected teacher must pick another slot.
          </p>
        </div>
        {rows.length > 1 ? (
          <div className="flex flex-wrap items-center gap-2">
            <input
              className={`${inputClass} w-52`}
              placeholder="Teacher initial or course"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <select
              className={`${inputClass} w-auto`}
              value={mode}
              onChange={(e) => setMode(e.target.value as MakeupMode | "")}
            >
              <option value="">In room and online</option>
              <option value="PHYSICAL">In room only</option>
              <option value="ONLINE">Online only</option>
            </select>
          </div>
        ) : null}
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
      ) : shown.length === 0 ? (
        <Card>
          <EmptyState title="No request matches" body="Clear the search to see them all." />
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {shown.map((m) => (
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

  const online = makeup.mode === "ONLINE";

  return (
    <article className="flex flex-col overflow-hidden rounded-2xl border-2 border-line bg-surface">
      <header className="space-y-2 p-4">
        <div className="flex items-start justify-between gap-2">
          <p className="min-w-0 truncate text-xl font-bold tracking-tight">
            {makeup.original_course_code ?? "—"}
          </p>
          <span
            className={`shrink-0 rounded-lg px-2 py-1 text-xs font-bold uppercase tracking-wide ${
              online ? "bg-info-soft text-info" : "bg-brand-soft text-brand"
            }`}
          >
            {online ? "Online" : "In room"}
          </span>
        </div>
        <p className="text-sm text-ink-soft">
          <span className="font-semibold text-ink">{makeup.teacher_initial}</span>
          {makeup.teacher_name ? ` · ${makeup.teacher_name}` : ""}
          <br />
          Section {makeup.original_section ?? "—"}
        </p>
      </header>

      <div className="flex-1 space-y-2.5 px-4 pb-4">
        <div className="rounded-xl bg-canvas px-3 py-2">
          <p className="text-xs font-bold uppercase tracking-wide text-ink-faint">Missed</p>
          <p className="text-sm font-semibold">
            {makeup.original_date ? shortDay(makeup.original_date) : "—"}
            <span className="font-normal text-ink-soft">
              {" "}
              · {[makeup.original_time_slot, makeup.original_room].filter(Boolean).join(" · ")}
            </span>
          </p>
        </div>
        <div className="rounded-xl bg-brand-soft px-3 py-2 ring-2 ring-inset ring-brand/20">
          <p className="text-xs font-bold uppercase tracking-wide text-brand">Requested</p>
          <p className="text-base font-bold">{shortDay(makeup.date)}</p>
          <p className="text-sm font-semibold tabular-nums">
            {makeup.time_slot} · {online ? "Online" : `Room ${makeup.room}`}
          </p>
        </div>
        {makeup.reason ? (
          <p className="line-clamp-3 text-sm text-ink-soft" title={makeup.reason}>
            <span className="font-semibold text-ink">Reason: </span>
            {makeup.reason}
          </p>
        ) : null}
        {online ? (
          makeup.drive_link ? (
            <a
              href={makeup.drive_link}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-between gap-2 rounded-xl bg-info-soft px-3 py-2 text-sm font-bold text-info ring-1 ring-inset ring-info/25 hover:bg-info/10"
            >
              <span>Drive link</span>
              <span aria-hidden>Open ↗</span>
            </a>
          ) : (
            <p className="text-xs text-ink-faint">No Drive link attached.</p>
          )
        ) : null}
      </div>

      <footer className="space-y-2 border-t-2 border-line bg-canvas p-3">
        <input
          className={inputClass}
          placeholder="Note for the teacher (optional)"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />

        {error ? (
          <p className="rounded-lg bg-bad-soft px-3 py-2 text-sm font-semibold text-bad">{error}</p>
        ) : null}

        <div className="grid grid-cols-2 gap-2">
          <Button size="lg" onClick={() => decide("APPROVE")} disabled={busy}>
            Approve
          </Button>
          <Button size="lg" variant="danger" onClick={() => decide("REJECT")} disabled={busy}>
            Reject
          </Button>
        </div>
      </footer>
    </article>
  );
}
