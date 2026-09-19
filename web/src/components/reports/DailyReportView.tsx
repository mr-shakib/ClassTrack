"use client";

import { useEffect, useState } from "react";
import { OutcomeBars, OutcomeShare } from "@/components/charts";
import { Card, EmptyState, ErrorNote, Field, Spinner, SummaryCard, inputClass } from "@/components/ui";
import { api, todayISO } from "@/lib/api";
import type { DailyReport } from "@/lib/types";
import ClassTable from "./ClassTable";

/** One day: every class on it, floor by floor, including makeups moved onto it. */
export default function DailyReportView() {
  const [date, setDate] = useState(todayISO());
  const [data, setData] = useState<DailyReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setError(null);
    api
      .dailyReport(date)
      .then((d) => alive && setData(d))
      .catch((err) => alive && setError(err instanceof Error ? err.message : "Could not load."));
    return () => {
      alive = false;
    };
  }, [date]);

  const t = data?.totals;

  return (
    <div className="space-y-4">
      <Card className="p-3">
        <div className="max-w-xs">
        <Field label="Date">
          <input
            type="date"
            className={inputClass}
            value={date}
            onChange={(e) => e.target.value && setDate(e.target.value)}
          />
        </Field>
        </div>
      </Card>

      {error ? <ErrorNote message={error} /> : null}
      {!data || !t ? (
        <Spinner />
      ) : data.total_scheduled === 0 ? (
        <Card>
          <EmptyState title="No classes on this day" body="A holiday, the weekend, or before the routine." />
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-8">
            <SummaryCard label="Classes today" value={data.total_scheduled} hint={`${data.makeup} makeup`} />
            <SummaryCard label="Checked" value={data.total_checked} />
            <SummaryCard label="Held" value={t.held} tone="ok" />
            <SummaryCard label="Late" value={t.late} tone="warn" />
            <SummaryCard label="Missed" value={t.missed} tone="bad" />
            <SummaryCard label="Not checked" value={t.not_checked} tone="gap" />
            <SummaryCard label="Rescheduled" value={t.rescheduled} tone="info" />
            <SummaryCard label="Pending" value={t.pending} hint="not settled yet" />
          </div>

          <Card className="p-4">
            <h2 className="mb-3 text-sm font-semibold">Where every class stands</h2>
            <OutcomeShare tally={t} />
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card className="p-4">
              <h2 className="mb-3 text-sm font-semibold">By floor</h2>
              <OutcomeBars data={data.by_floor} category="key" label={(f) => f.short_label} horizontal />
            </Card>
            <Card className="p-4">
              <h2 className="mb-3 text-sm font-semibold">By time of day</h2>
              <OutcomeBars data={data.by_slot} category="time_slot" label={(s) => s.time_slot.split("-")[0]} />
            </Card>
          </div>

          <Card>
            <div className="border-b border-line px-4 py-3">
              <h2 className="text-sm font-semibold">Floor-wise total</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-faint">
                    <th className="px-4 py-2 font-medium">Floor</th>
                    <th className="px-4 py-2 font-medium">Classes</th>
                    <th className="px-4 py-2 font-medium">Held</th>
                    <th className="px-4 py-2 font-medium">Late</th>
                    <th className="px-4 py-2 font-medium">Missed</th>
                    <th className="px-4 py-2 font-medium">Not checked</th>
                    <th className="px-4 py-2 font-medium">Rescheduled</th>
                    <th className="px-4 py-2 font-medium">Pending</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {data.by_floor.map((f) => (
                    <tr key={f.key}>
                      <td className="px-4 py-2 font-medium">{f.label}</td>
                      <td className="px-4 py-2 font-semibold tabular-nums">{f.total}</td>
                      <td className="px-4 py-2 tabular-nums text-ok">{f.held}</td>
                      <td className="px-4 py-2 tabular-nums text-warn">{f.late}</td>
                      <td className="px-4 py-2 tabular-nums text-bad">{f.missed}</td>
                      <td className="px-4 py-2 tabular-nums text-gap">{f.not_checked}</td>
                      <td className="px-4 py-2 tabular-nums text-info">{f.rescheduled}</td>
                      <td className="px-4 py-2 tabular-nums text-ink-faint">{f.pending}</td>
                    </tr>
                  ))}
                  <tr className="bg-canvas font-semibold">
                    <td className="px-4 py-2">All floors</td>
                    <td className="px-4 py-2 tabular-nums">{t.total}</td>
                    <td className="px-4 py-2 tabular-nums">{t.held}</td>
                    <td className="px-4 py-2 tabular-nums">{t.late}</td>
                    <td className="px-4 py-2 tabular-nums">{t.missed}</td>
                    <td className="px-4 py-2 tabular-nums">{t.not_checked}</td>
                    <td className="px-4 py-2 tabular-nums">{t.rescheduled}</td>
                    <td className="px-4 py-2 tabular-nums">{t.pending}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </Card>

          {data.rescheduled_in.length ? (
            <Card>
              <div className="border-b border-line px-4 py-3">
                <h2 className="text-sm font-semibold">
                  Rescheduled onto this day ({data.rescheduled_in.length})
                </h2>
                <p className="text-xs text-ink-faint">
                  Makeups for classes missed on another day. They count on this day.
                </p>
              </div>
              <ClassTable rows={data.rescheduled_in} showTeacher />
            </Card>
          ) : null}

          <Card className="p-4">
            <p className="text-sm text-ink-soft">
              <strong className="text-bad">Missed</strong> means the teacher was absent and it
              was confirmed by a check. <strong className="text-gap">Not checked</strong> means
              no staff member submitted a result — a monitoring gap, not a teacher absence.
            </p>
          </Card>
        </>
      )}
    </div>
  );
}
