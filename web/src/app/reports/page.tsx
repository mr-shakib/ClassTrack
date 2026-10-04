"use client";

import { useEffect, useState } from "react";
import DailyReportView from "@/components/reports/DailyReportView";
import OverviewReport from "@/components/reports/OverviewReport";
import { type Period, currentMonthPeriod } from "@/components/reports/PeriodPicker";
import StaffReportView from "@/components/reports/StaffReportView";
import TeacherReportView from "@/components/reports/TeacherReportView";
import { Spinner } from "@/components/ui";
import { mayReadReports, mayReport, useAuth, useRequireAccess } from "@/lib/auth";


type Tab = "overview" | "daily" | "teacher" | "staff";

const TABS: { key: Tab; label: string; admin: boolean }[] = [
  { key: "overview", label: "Monthly & semester", admin: true },
  { key: "daily", label: "Daily", admin: true },
  { key: "teacher", label: "Teacher-wise", admin: false },
  { key: "staff", label: "Staff monitoring", admin: true },
];

export default function ReportsPage() {
  const { user } = useAuth();
  const { permitted, loading } = useRequireAccess(mayReadReports);
  // Department reports: every tab, and any teacher's report.
  const isAdmin = user != null && mayReport(user);

  const [tab, setTab] = useState<Tab>("teacher");
  const [teacher, setTeacher] = useState({ initial: "", period: currentMonthPeriod() });

  useEffect(() => {
    if (isAdmin) setTab("overview");
    else if (user?.teacher_initial)
      setTeacher((t) => ({ ...t, initial: user.teacher_initial ?? "" }));
  }, [isAdmin, user?.teacher_initial]);

  if (loading || !permitted) return <Spinner />;

  const openTeacher = (initial: string, period: Period) => {
    setTeacher({ initial, period });
    setTab("teacher");
    window.scrollTo({ top: 0 });
  };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Reports</h1>

      <div className="flex gap-1 overflow-x-auto border-b border-line">
        {TABS.filter((t) => isAdmin || !t.admin).map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
              tab === t.key
                ? "border-brand text-brand"
                : "border-transparent text-ink-soft hover:text-ink"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "overview" && isAdmin ? <OverviewReport onOpenTeacher={openTeacher} /> : null}
      {tab === "daily" && isAdmin ? <DailyReportView /> : null}
      {tab === "teacher" ? (
        <TeacherReportView isAdmin={isAdmin} initial={teacher.initial} period={teacher.period} />
      ) : null}
      {tab === "staff" && isAdmin ? <StaffReportView /> : null}
    </div>
  );
}
