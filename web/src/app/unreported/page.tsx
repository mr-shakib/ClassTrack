"use client";

import { useCallback, useEffect, useState } from "react";
import { Card, EmptyState, ErrorNote, Spinner } from "@/components/ui";
import { api, todayISO } from "@/lib/api";
import { ADMIN_ROLES, useRequireRole } from "@/lib/auth";
import type { StaffMisses, UnreportedClass, UnreportedReport, Urgency } from "@/lib/types";

const URGENCY: Record<Urgency, { label: string; chip: string; bar: string }> = {
  CRITICAL: {
    label: "Needs attention now",
    chip: "bg-bad text-white",
    bar: "border-l-bad",
  },
  HIGH: { label: "Missed today", chip: "bg-warn text-white", bar: "border-l-warn" },
  MEDIUM: {
    label: "Missed this week",
    chip: "bg-gap text-white",
    bar: "border-l-gap",
  },
  LOW: { label: "Up to date", chip: "bg-ok-soft text-ok", bar: "border-l-ok" },
};

export default function UnreportedPage() {
  const { permitted, loading: authLoading } = useRequireRole(ADMIN_ROLES);
  const [data, setData] = useState<UnreportedReport | null>(null);
  const [days, setDays] = useState(7);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const to = todayISO();
      const from = new Date(Date.now() - days * 86_400_000).toISOString().slice(0, 10);
      setData(await api.unreported(from, to));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the report.");
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    if (permitted) void load();
    const timer = setInterval(() => permitted && void load(), 60_000);
    return () => clearInterval(timer);
  }, [permitted, load]);

  if (authLoading || !permitted || (loading && !data)) return <Spinner />;

  const s = data?.summary;
  const withMisses = (data?.by_staff ?? []).filter((m) => m.total > 0);
  const clean = (data?.by_staff ?? []).filter((m) => m.total === 0);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Unreported classes</h1>
          <p className="mt-0.5 text-sm text-ink-soft">
            Classes nobody submitted a result for, and who was responsible.
          </p>
        </div>
        <div className="flex gap-1">
          {[1, 7, 30].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`min-h-10 rounded-lg px-3 text-sm font-semibold transition-colors ${
                days === d
                  ? "bg-brand text-white"
                  : "bg-surface text-ink-soft ring-1 ring-inset ring-line"
              }`}
            >
              {d === 1 ? "Today" : `${d} days`}
            </button>
          ))}
        </div>
      </div>

      {error ? <ErrorNote message={error} /> : null}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Big label="Missed today" value={s?.today ?? 0} tone={s?.today ? "bad" : "ok"} />
        <Big label={`Last ${days} days`} value={s?.total ?? 0} tone="gap" />
        <Big
          label="Staff involved"
          value={s?.staff_with_misses ?? 0}
          tone={s?.staff_with_misses ? "warn" : "ok"}
        />
        <Big
          label="No floor assigned"
          value={s?.unassigned ?? 0}
          tone={s?.unassigned ? "warn" : "ok"}
          hint={s?.unassigned ? "fix in Staff coverage" : undefined}
        />
      </div>

      {withMisses.length === 0 ? (
        <Card>
          <EmptyState
            title="Nothing unreported"
            body="Every scheduled class in this period was checked."
          />
        </Card>
      ) : (
        <div className="space-y-3">
          {withMisses.map((m) => (
            <StaffBlock key={m.user_id} member={m} />
          ))}
        </div>
      )}

      {data && data.unassigned.length > 0 ? (
        <Card className="border-warn/30">
          <div className="border-b border-line bg-warn-soft px-4 py-3">
            <h2 className="text-base font-bold text-warn">
              {data.unassigned.length} classes on floors nobody covers
            </h2>
            <p className="mt-0.5 text-sm text-warn">
              Nobody was responsible for these. Assign the floor in{" "}
              <a className="underline" href="/admin/staff">
                Staff coverage
              </a>
              .
            </p>
          </div>
          <ClassTable rows={data.unassigned} />
        </Card>
      ) : null}

      {clean.length > 0 ? (
        <Card className="p-4">
          <h2 className="text-sm font-semibold text-ink-soft">
            Up to date ({clean.length})
          </h2>
          <p className="mt-1 text-sm text-ink-faint">
            {clean.map((m) => m.name).join(" · ")}
          </p>
        </Card>
      ) : null}
    </div>
  );
}

function Big({
  label,
  value,
  tone,
  hint,
}: {
  label: string;
  value: number;
  tone: "ok" | "warn" | "bad" | "gap";
  hint?: string;
}) {
  const tones = {
    ok: "text-ok",
    warn: "text-warn",
    bad: "text-bad",
    gap: "text-gap",
  };
  return (
    <Card className="p-4">
      <div className="text-xs font-semibold uppercase tracking-wide text-ink-faint">
        {label}
      </div>
      <div className={`mt-1 text-4xl font-bold tabular-nums ${tones[tone]}`}>
        {value}
      </div>
      {hint ? <div className="mt-0.5 text-xs text-ink-faint">{hint}</div> : null}
    </Card>
  );
}

function StaffBlock({ member }: { member: StaffMisses }) {
  const [open, setOpen] = useState(member.today > 0);
  const u = URGENCY[member.urgency];

  return (
    <Card className={`overflow-hidden border-l-4 ${u.bar}`}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full flex-wrap items-center justify-between gap-3 px-4 py-3 text-left hover:bg-canvas"
      >
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-lg font-bold">{member.name}</span>
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-bold uppercase tracking-wide ${u.chip}`}
            >
              {u.label}
            </span>
          </div>
          <p className="mt-0.5 text-sm text-ink-faint">
            {member.zones.length > 0
              ? `Floors: ${member.zones.join(", ")}`
              : "No floor assigned"}
          </p>
        </div>

        <div className="flex items-center gap-5">
          <Stat n={member.today} label="today" tone="text-bad" />
          <Stat n={member.this_week} label="this week" tone="text-gap" />
          <Stat n={member.total} label="total" tone="text-ink" />
          <span className="text-ink-faint">{open ? "▲" : "▼"}</span>
        </div>
      </button>

      {open ? <ClassTable rows={member.classes} /> : null}
    </Card>
  );
}

function Stat({ n, label, tone }: { n: number; label: string; tone: string }) {
  return (
    <div className="text-center">
      <div className={`text-2xl font-bold tabular-nums ${n > 0 ? tone : "text-ink-faint"}`}>
        {n}
      </div>
      <div className="text-[11px] font-medium text-ink-faint">{label}</div>
    </div>
  );
}

function ClassTable({ rows }: { rows: UnreportedClass[] }) {
  return (
    <div className="overflow-x-auto border-t border-line">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-faint">
            <th className="px-4 py-2 font-medium">Date</th>
            <th className="px-4 py-2 font-medium">Time</th>
            <th className="px-4 py-2 font-medium">Room</th>
            <th className="px-4 py-2 font-medium">Course</th>
            <th className="px-4 py-2 font-medium">Section</th>
            <th className="px-4 py-2 font-medium">Teacher</th>
            <th className="px-4 py-2 font-medium">Ago</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((c) => (
            <tr key={c.instance_id}>
              <td className="whitespace-nowrap px-4 py-2 tabular-nums">{c.date}</td>
              <td className="whitespace-nowrap px-4 py-2 tabular-nums text-ink-soft">
                {c.time_slot}
              </td>
              <td className="px-4 py-2 font-medium">{c.room}</td>
              <td className="px-4 py-2 text-ink-soft">{c.course_code}</td>
              <td className="px-4 py-2 text-ink-soft">{c.section}</td>
              <td className="px-4 py-2 text-ink-soft">{c.teacher_initial}</td>
              <td className="whitespace-nowrap px-4 py-2 tabular-nums text-ink-faint">
                {c.hours_since < 24
                  ? `${Math.round(c.hours_since)}h`
                  : `${Math.round(c.hours_since / 24)}d`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
