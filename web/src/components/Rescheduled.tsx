import type { SlotRef } from "@/lib/types";

/** "Sun 13 Sep" -- short enough to sit in a chip. */
export const shortDay = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString([], {
    weekday: "short",
    day: "numeric",
    month: "short",
  });

const where = (ref: SlotRef) => (ref.mode === "ONLINE" ? "online" : ref.room ?? "");

function Arrow() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M4 12a8 8 0 0 1 14-5.3M20 4v4h-4M20 12a8 8 0 0 1-14 5.3M4 20v-4h4" />
    </svg>
  );
}

/**
 * The mark of a rescheduled class, the same on every screen.
 *
 * A makeup sits in its new day's list beside the routine's own classes; this
 * says it is not one of them, and which missed class it makes up. The dashed
 * teal frame is what the eye finds first; the words say why.
 */
export function RescheduledTag({
  from,
  size = "md",
}: {
  from: SlotRef | null;
  size?: "md" | "lg";
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md border border-dashed border-info/60 bg-info-soft font-semibold text-info ${
        size === "lg" ? "px-2.5 py-1 text-sm" : "px-1.5 py-0.5 text-xs"
      }`}
      title={from ? `Makeup for the class of ${shortDay(from.date)}, ${from.time_slot}` : "Makeup class"}
    >
      <Arrow />
      {from ? `Makeup · from ${shortDay(from.date)} ${from.time_slot.split("-")[0]}` : "Makeup class"}
    </span>
  );
}

/**
 * The mark of an extra class: booked by the teacher on top of the routine.
 * Checked like any class, so it sits in the same lists; this says why it is
 * not on the routine.
 */
export function ExtraTag({ size = "md" }: { size?: "md" | "lg" }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md border border-dashed border-brand/50 bg-brand-soft font-semibold text-brand ${
        size === "lg" ? "px-2.5 py-1 text-sm" : "px-1.5 py-0.5 text-xs"
      }`}
      title="Booked by the teacher on top of the routine"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden>
        <path d="M12 5v14M5 12h14" />
      </svg>
      Extra class
    </span>
  );
}

/** On a missed class: where it went. */
export function MovedToTag({ to }: { to: SlotRef }) {
  const pending = to.status === "PENDING";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs font-semibold ${
        pending ? "bg-warn-soft text-warn" : "bg-canvas text-ink-soft"
      }`}
    >
      <Arrow />
      {pending ? "Reschedule requested" : "Moved"} → {shortDay(to.date)}{" "}
      {to.time_slot.split("-")[0]} {where(to)}
    </span>
  );
}

/** Row styling for a rescheduled class in a table: a teal bar down the left edge. */
export const rescheduledRowClass = "shadow-[inset_4px_0_0_var(--color-info)] bg-info-soft/40";
