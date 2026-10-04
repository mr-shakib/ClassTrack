"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ExtraTag, RescheduledTag, rescheduledRowClass } from "@/components/Rescheduled";
import StatusBadge from "@/components/StatusBadge";
import { Card, EmptyState, ErrorNote, Spinner, SummaryCard } from "@/components/ui";
import { api } from "@/lib/api";
import { mayDecide, mayReport, mayWatch, useRequireAccess } from "@/lib/auth";
import type { Dashboard } from "@/lib/types";

export default function DashboardPage() {
  const { user, permitted, loading: authLoading } = useRequireAccess(mayWatch);
  // The Coordination Officer sees the queue's size but cannot decide it.
  // The tiles link on only where the user may follow.
  const seesUnreported = user != null && mayReport(user);
  const decides = user != null && mayDecide(user);
  const [data, setData] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await api.dashboard());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the dashboard.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!permitted) return;
    void load();
    const timer = setInterval(load, 30_000);
    return () => clearInterval(timer);
  }, [permitted, load]);

  if (authLoading || !permitted || (loading && !data)) return <Spinner />;

  const s = data?.summary;
  const a = data?.attention;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold">Live monitoring</h1>
          <p className="mt-0.5 text-sm text-ink-soft">
            Slot {data?.current_slot ?? "—"} · refreshed{" "}
            {data ? new Date(data.as_of).toLocaleTimeString() : "—"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/today"
            className="rounded-lg px-3 py-1.5 text-sm font-semibold text-brand ring-1 ring-inset ring-brand/30 hover:bg-brand-soft"
          >
            Whole day ›
          </Link>
          <span className="flex items-center gap-1.5 text-xs text-ink-faint">
            <span className="size-2 animate-pulse rounded-full bg-ok" />
            auto-refreshing
          </span>
        </div>
      </div>

      {error ? <ErrorNote message={error} /> : null}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-7">
        <SummaryCard label="Scheduled now" value={s?.scheduled_now ?? 0} />
        <SummaryCard label="Running" value={s?.running ?? 0} tone="ok" />
        <SummaryCard label="Late" value={s?.late ?? 0} tone="warn" />
        <SummaryCard
          label="Missed"
          value={s?.missed ?? 0}
          tone="bad"
          hint="teacher absent"
        />
        <SummaryCard
          label="Not checked"
          value={s?.not_checked ?? 0}
          tone="gap"
          hint="staff did not check"
        />
        <SummaryCard label="Makeup" value={s?.makeup_physical ?? 0} tone="info" />
        <SummaryCard label="Online" value={s?.online_approved ?? 0} tone="info" />
      </div>

      {/* Needs attention. Missed and Not checked are shown separately on
          purpose -- they are different problems with different owners. */}
      <Card className="p-4">
        <h2 className="mb-3 text-sm font-semibold">Needs attention today</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          <Attention
            label="Missed"
            value={a?.missed_today ?? 0}
            tone="text-bad"
            note="teacher absent"
          />
          <Attention
            label="Not checked"
            value={a?.not_checked_today ?? 0}
            tone="text-gap"
            note={seesUnreported ? "see who" : undefined}
            href={seesUnreported ? "/unreported" : undefined}
          />
          <Attention
            label="Online requests"
            value={a?.pending_online ?? 0}
            tone="text-warn"
            note={decides ? "to decide" : undefined}
            href={decides ? "/approvals" : undefined}
          />
          <Attention
            label="Pending makeups"
            value={a?.pending_makeup ?? 0}
            tone="text-info"
          />
          <Attention label="Disputes" value={a?.disputes ?? 0} tone="text-bad" />
        </div>
      </Card>

      <Card>
        <div className="border-b border-line px-4 py-3">
          <h2 className="text-sm font-semibold">
            Current slot · {data?.current_slot ?? "—"}
          </h2>
        </div>
        {!data || data.rows.length === 0 ? (
          <EmptyState title="No classes in the current slot" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-faint">
                  <th className="px-4 py-2 font-medium">Room</th>
                  <th className="px-4 py-2 font-medium">Teacher</th>
                  <th className="px-4 py-2 font-medium">Course</th>
                  <th className="px-4 py-2 font-medium">Section</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium">Checked by</th>
                  <th className="px-4 py-2 font-medium">At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {data.rows.map((r) => (
                  <tr
                    key={r.instance_id}
                    className={
                      r.is_makeup
                        ? rescheduledRowClass
                        : r.status === "MISSED"
                        ? "bg-bad-soft/40"
                        : r.status === "NOT_CHECKED"
                          ? "bg-gap-soft/40"
                          : undefined
                    }
                  >
                    <td className="px-4 py-2 font-medium">
                      {r.room}
                      {r.is_makeup ? (
                        <div className="mt-1">
                          <RescheduledTag from={r.rescheduled_from} />
                        </div>
                      ) : r.is_extra ? (
                        <div className="mt-1">
                          <ExtraTag />
                        </div>
                      ) : null}
                    </td>
                    <td className="px-4 py-2 text-ink-soft">
                      {r.teacher_name ?? r.teacher_initial}
                    </td>
                    <td className="px-4 py-2 text-ink-soft">{r.course_code}</td>
                    <td className="px-4 py-2 text-ink-soft">{r.section}</td>
                    <td className="px-4 py-2">
                      <StatusBadge status={r.status} lateMinutes={r.late_minutes} />
                    </td>
                    <td className="px-4 py-2 text-ink-faint">{r.checked_by ?? "—"}</td>
                    <td className="px-4 py-2 tabular-nums text-ink-faint">
                      {r.checked_at ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function Attention({
  label,
  value,
  tone,
  note,
  href,
}: {
  label: string;
  value: number;
  tone: string;
  note?: string;
  href?: string;
}) {
  const body = (
    <div className="rounded-lg bg-canvas px-3 py-2.5">
      <div className={`text-2xl font-semibold tabular-nums ${value > 0 ? tone : "text-ink-faint"}`}>
        {value}
      </div>
      <div className="text-xs font-medium text-ink-soft">{label}</div>
      {note ? <div className="text-[11px] text-ink-faint">{note}</div> : null}
    </div>
  );
  return href && value > 0 ? (
    <Link href={href} className="block transition-opacity hover:opacity-80">
      {body}
    </Link>
  ) : (
    body
  );
}
