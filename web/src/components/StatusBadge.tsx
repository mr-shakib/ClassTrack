import type { ClassStatus } from "@/lib/types";

/**
 * One colour map for all twelve statuses, used everywhere.
 *
 * MISSED and NOT_CHECKED get visibly different hues on purpose: one is a
 * teacher-side problem, the other a staff-side one, and the whole system exists
 * to keep them apart. Never collapse them into a single "problem" colour.
 */
const STYLES: Record<ClassStatus | "UNKNOWN", { label: string; className: string }> = {
  UPCOMING: { label: "Upcoming", className: "bg-canvas text-ink-soft ring-line" },
  ONGOING: { label: "Ongoing", className: "bg-brand-soft text-brand ring-brand/20" },
  RUNNING: { label: "Running", className: "bg-ok-soft text-ok ring-ok/20" },
  LATE: { label: "Late", className: "bg-warn-soft text-warn ring-warn/20" },
  MISSED: { label: "Missed", className: "bg-bad-soft text-bad ring-bad/20" },
  NOT_CHECKED: { label: "Not checked", className: "bg-gap-soft text-gap ring-gap/20" },
  MAKEUP_SCHEDULED: {
    label: "Makeup scheduled",
    className: "bg-info-soft text-info ring-info/20",
  },
  MAKEUP_COMPLETED: {
    label: "Makeup completed",
    className: "bg-ok-soft text-ok ring-ok/20",
  },
  ONLINE_PENDING: {
    label: "Online pending",
    className: "bg-warn-soft text-warn ring-warn/20",
  },
  ONLINE_APPROVED: {
    label: "Online approved",
    className: "bg-info-soft text-info ring-info/20",
  },
  ONLINE_REJECTED: { label: "Online rejected", className: "bg-bad-soft text-bad ring-bad/20" },
  CANCELLED: { label: "Cancelled", className: "bg-canvas text-ink-faint ring-line" },
  UNKNOWN: { label: "—", className: "bg-canvas text-ink-faint ring-line" },
};

export function statusLabel(status: ClassStatus | null | undefined): string {
  return STYLES[status ?? "UNKNOWN"]?.label ?? String(status);
}

export default function StatusBadge({
  status,
  lateMinutes,
  className = "",
}: {
  status: ClassStatus | null | undefined;
  lateMinutes?: number | null;
  className?: string;
}) {
  const style = STYLES[status ?? "UNKNOWN"] ?? STYLES.UNKNOWN;
  const label =
    status === "LATE" && lateMinutes != null
      ? `Late · ${lateMinutes} min`
      : style.label;

  return (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${style.className} ${className}`}
    >
      {label}
    </span>
  );
}
