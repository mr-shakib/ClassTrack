import type { Outcome } from "@/lib/types";

/**
 * The report bucket a class falls in. Same hues as StatusBadge: Missed (the
 * teacher's absence) and Not checked (a staff gap) are never one colour.
 */
export const OUTCOME: Record<Outcome, { label: string; className: string }> = {
  CONDUCTED: { label: "Conducted", className: "bg-ok-soft text-ok ring-ok/20" },
  LATE: { label: "Late", className: "bg-warn-soft text-warn ring-warn/20" },
  MISSED: { label: "Missed", className: "bg-bad-soft text-bad ring-bad/20" },
  NOT_CHECKED: { label: "Not checked", className: "bg-gap-soft text-gap ring-gap/20" },
  RESCHEDULED: { label: "Rescheduled", className: "bg-info-soft text-info ring-info/20" },
  CANCELLED: { label: "Cancelled", className: "bg-canvas text-ink-faint ring-line" },
  PENDING: { label: "Pending", className: "bg-canvas text-ink-soft ring-line" },
};

export const OUTCOME_ORDER: Outcome[] = [
  "CONDUCTED",
  "LATE",
  "MISSED",
  "NOT_CHECKED",
  "RESCHEDULED",
  "PENDING",
  "CANCELLED",
];

export default function OutcomeBadge({
  outcome,
  lateMinutes,
}: {
  outcome: Outcome;
  lateMinutes?: number | null;
}) {
  const style = OUTCOME[outcome];
  return (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${style.className}`}
    >
      {outcome === "LATE" && lateMinutes != null ? `Late · ${lateMinutes} min` : style.label}
    </span>
  );
}
