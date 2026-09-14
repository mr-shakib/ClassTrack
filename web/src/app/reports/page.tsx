"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Button,
  Card,
  EmptyState,
  ErrorNote,
  Field,
  Spinner,
  SummaryCard,
  inputClass,
} from "@/components/ui";
import { api, todayISO } from "@/lib/api";
import { ADMIN_ROLES, useAuth, useRequireRole } from "@/lib/auth";
import type { DailyReport, Role, StaffReport, TeacherReport } from "@/lib/types";

const REPORT_ROLES: Role[] = ["TEACHER", ...ADMIN_ROLES];

type Tab = "daily" | "teacher" | "staff";

/** Client-side CSV, so no extra endpoint is needed for export. */
function downloadCsv(filename: string, rows: (string | number)[][]) {
  const csv = rows
    .map((r) =>
      r
        .map((cell) => {
          const s = String(cell ?? "");
          return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
        })
        .join(","),
    )
    .join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function ReportsPage() {
  const { user } = useAuth();
  const { permitted, loading: authLoading } = useRequireRole(REPORT_ROLES);

  const isAdmin = user != null && ADMIN_ROLES.includes(user.role);
  const [tab, setTab] = useState<Tab>("teacher");
  const [date, setDate] = useState(todayISO());
  const [from, setFrom] = useState("2026-09-01");
  const [to, setTo] = useState("2026-12-31");
  const [initial, setInitial] = useState("");
  const [daily, setDaily] = useState<DailyReport | null>(null);
  const [teacher, setTeacher] = useState<TeacherReport | null>(null);
  const [staff, setStaff] = useState<StaffReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isAdmin) setTab("daily");
    if (user?.teacher_initial) setInitial(user.teacher_initial);
  }, [isAdmin, user?.teacher_initial]);

  const run = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (tab === "daily") setDaily(await api.dailyReport(date));
      else if (tab === "teacher")
        setTeacher(await api.teacherReport(initial || undefined, from, to));
      else setStaff(await api.staffReport(from, to));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not build the report.");
    } finally {
      setLoading(false);
    }
  }, [tab, date, from, to, initial]);

  useEffect(() => {
    if (permitted) void run();
  }, [permitted, run]);

  if (authLoading || !permitted) return <Spinner />;

  const tabs: { key: Tab; label: string; admin: boolean }[] = [
    { key: "daily", label: "Daily", admin: true },
    { key: "teacher", label: "Teacher-wise", admin: false },
    { key: "staff", label: "Staff monitoring", admin: true },
  ];

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Reports</h1>

      <div className="flex gap-1 border-b border-line">
        {tabs
          .filter((t) => isAdmin || !t.admin)
          .map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
                tab === t.key
                  ? "border-brand text-brand"
                  : "border-transparent text-ink-soft hover:text-ink"
              }`}
            >
              {t.label}
            </button>
          ))}
      </div>

      <Card className="p-3">
        <div className="flex flex-wrap items-end gap-3">
          {tab === "daily" ? (
            <Field label="Date">
              <input
                type="date"
                className={inputClass}
                value={date}
                onChange={(e) => setDate(e.target.value)}
              />
            </Field>
          ) : (
            <>
              <Field label="From">
                <input
                  type="date"
                  className={inputClass}
                  value={from}
                  onChange={(e) => setFrom(e.target.value)}
                />
              </Field>
              <Field label="To">
                <input
                  type="date"
                  className={inputClass}
                  value={to}
                  onChange={(e) => setTo(e.target.value)}
                />
              </Field>
            </>
          )}
          {tab === "teacher" && isAdmin ? (
            <Field label="Teacher initial">
              <input
                className={inputClass}
                placeholder="e.g. SRH"
                value={initial}
                onChange={(e) => setInitial(e.target.value.toUpperCase())}
              />
            </Field>
          ) : null}
          <Button onClick={run} disabled={loading}>
            {loading ? "Building…" : "Run"}
          </Button>
        </div>
      </Card>

      {error ? <ErrorNote message={error} /> : null}

      {tab === "daily" && daily ? (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-7">
            <SummaryCard label="Scheduled" value={daily.total_scheduled} />
            <SummaryCard label="Checked" value={daily.total_checked} />
            <SummaryCard label="Running" value={daily.running} tone="ok" />
            <SummaryCard label="Late" value={daily.late} tone="warn" />
            <SummaryCard label="Missed" value={daily.missed} tone="bad" />
            <SummaryCard label="Not checked" value={daily.not_checked} tone="gap" />
            <SummaryCard label="Makeup" value={daily.makeup} tone="info" />
          </div>
          <Card className="p-4">
            <p className="text-sm text-ink-soft">
              <strong className="text-bad">Missed</strong> means the teacher was
              absent and it was confirmed by a check.{" "}
              <strong className="text-gap">Not checked</strong> means no staff
              member submitted a result in time — a monitoring gap, not a teacher
              absence.
            </p>
          </Card>
        </>
      ) : null}

      {tab === "teacher" && teacher ? (
        <>
          <Card className="p-4">
            <p className="text-sm font-semibold">
              {teacher.teacher_name ?? teacher.teacher_initial}{" "}
              <span className="font-normal text-ink-faint">
                ({teacher.teacher_initial})
              </span>
            </p>
            <p className="text-xs text-ink-faint">
              {teacher.range.from} to {teacher.range.to}
            </p>
          </Card>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <SummaryCard label="Total scheduled" value={teacher.total_scheduled} />
            <SummaryCard label="Conducted" value={teacher.conducted} tone="ok" />
            <SummaryCard label="Late" value={teacher.late} tone="warn" />
            <SummaryCard label="Missed" value={teacher.missed} tone="bad" />
            <SummaryCard label="Makeup scheduled" value={teacher.makeup_scheduled} tone="info" />
            <SummaryCard label="Makeup completed" value={teacher.makeup_completed} tone="ok" />
            <SummaryCard label="Makeup pending" value={teacher.makeup_pending} tone="warn" />
            <SummaryCard label="Online approved" value={teacher.online_approved} tone="info" />
          </div>
          <Button
            variant="secondary"
            onClick={() =>
              downloadCsv(`teacher-${teacher.teacher_initial}-${teacher.range.from}.csv`, [
                ["Indicator", "Value"],
                ["Teacher", teacher.teacher_name ?? teacher.teacher_initial],
                ["Initial", teacher.teacher_initial],
                ["From", teacher.range.from],
                ["To", teacher.range.to],
                ["Total scheduled", teacher.total_scheduled],
                ["Conducted", teacher.conducted],
                ["Late", teacher.late],
                ["Missed", teacher.missed],
                ["Not checked", teacher.not_checked],
                ["Makeup scheduled", teacher.makeup_scheduled],
                ["Makeup completed", teacher.makeup_completed],
                ["Makeup pending", teacher.makeup_pending],
                ["Online approved", teacher.online_approved],
              ])
            }
          >
            Export CSV
          </Button>
        </>
      ) : null}

      {tab === "staff" && staff ? (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <SummaryCard label="Assigned" value={staff.assigned} />
            <SummaryCard label="Checked" value={staff.checked} tone="ok" />
            <SummaryCard label="Not checked" value={staff.not_checked} tone="gap" />
            <SummaryCard
              label="Completion"
              value={`${staff.completion_rate}%`}
              tone={staff.completion_rate >= 90 ? "ok" : "warn"}
            />
          </div>
          <Card>
            {staff.rows.length === 0 ? (
              <EmptyState title="No office staff accounts" />
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-faint">
                    <th className="px-4 py-2 font-medium">Staff</th>
                    <th className="px-4 py-2 font-medium">Checked</th>
                    <th className="px-4 py-2 font-medium">Assigned</th>
                    <th className="px-4 py-2 font-medium">Completion</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {staff.rows.map((r) => (
                    <tr key={r.user_id}>
                      <td className="px-4 py-2 font-medium">{r.name}</td>
                      <td className="px-4 py-2 tabular-nums">{r.checked}</td>
                      <td className="px-4 py-2 tabular-nums text-ink-faint">
                        {r.assigned}
                      </td>
                      <td className="px-4 py-2 tabular-nums">{r.completion_rate}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
          <p className="text-xs text-ink-faint">
            Monitoring completion rate = checked ÷ assigned × 100. Every staff
            member currently sees every room, so &ldquo;assigned&rdquo; is the
            department total.
          </p>
        </>
      ) : null}
    </div>
  );
}
