"use client";

import { useEffect, useState } from "react";
import { Card, EmptyState, ErrorNote, Spinner, SummaryCard } from "@/components/ui";
import { api } from "@/lib/api";
import type { StaffReport } from "@/lib/types";
import PeriodPicker, { type Period, currentMonthPeriod, periodQuery } from "./PeriodPicker";

export default function StaffReportView() {
  const [period, setPeriod] = useState<Period>(currentMonthPeriod);
  const [staff, setStaff] = useState<StaffReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setError(null);
    api
      .staffReport(periodQuery(period))
      .then((d) => alive && setStaff(d))
      .catch((err) => alive && setError(err instanceof Error ? err.message : "Could not load."));
    return () => {
      alive = false;
    };
  }, [period]);

  return (
    <div className="space-y-4">
      <Card className="p-3">
        <PeriodPicker value={period} onChange={setPeriod} />
      </Card>
      {error ? <ErrorNote message={error} /> : null}
      {!staff ? (
        <Spinner />
      ) : (
        <>
          <p className="text-sm text-ink-soft">
            <span className="font-semibold text-ink">{period.label}</span> · {staff.range.from} to{" "}
            {staff.range.to}
          </p>
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
                      <td className="px-4 py-2 tabular-nums text-ink-faint">{r.assigned}</td>
                      <td className="px-4 py-2 tabular-nums">{r.completion_rate}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
          <p className="text-xs text-ink-faint">
            Monitoring completion rate = checked ÷ assigned × 100. Every staff member may check
            every room, so &ldquo;assigned&rdquo; is the department total.
          </p>
        </>
      )}
    </div>
  );
}
