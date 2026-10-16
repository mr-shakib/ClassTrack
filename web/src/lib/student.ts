/**
 * The student side, which needs no account: a student names their groups, the
 * browser remembers them, and every read is public. Group tokens are the
 * backend's (services/student_service.py): "63_A", "63_A1", "CSE447:RE_A".
 */

import { SLOTS } from "./api";
import type { StudentClass } from "./types";

const GROUPS_KEY = "classtrack.student-groups";

/** The groups this browser picked last, or none. Storage may be off. */
export function loadGroups(): string[] {
  try {
    const raw = JSON.parse(localStorage.getItem(GROUPS_KEY) ?? "[]");
    return Array.isArray(raw) ? raw.filter((g): g is string => typeof g === "string") : [];
  } catch {
    return [];
  }
}

export function saveGroups(groups: string[]) {
  try {
    localStorage.setItem(GROUPS_KEY, JSON.stringify(groups));
  } catch {
    /* a private window: the link in the address bar still has them */
  }
}

/** "63_A,63_A1" from the address bar, upper-cased, without blanks or repeats. */
export function parseGroups(raw: string | null): string[] {
  if (!raw) return [];
  return [...new Set(raw.split(",").map((g) => g.trim().toUpperCase()).filter(Boolean))];
}

/** A lab group's section: "63_A1" -> "63_A"; "CSE447:RE_A1" -> "CSE447:RE_A". */
export function parentOf(token: string): string | null {
  const m = /^(.*?)(\d+)$/.exec(token);
  if (!m || !/_[A-Z]$/.test(m[1])) return null;
  return m[1];
}

/** How a group reads to a person. */
export function groupLabel(token: string): string {
  const [course, section] = token.includes(":") ? token.split(":") : [null, token];
  const lab = parentOf(section) !== null;
  if (course) return `${course} retake ${section}`;
  return lab ? `Lab group ${section}` : `Section ${section}`;
}

/** "13:00" from minutes past midnight. */
export const clock = (minutes: number) =>
  `${String(Math.floor(minutes / 60) % 24).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`;

/** "13:00–14:30": the 24-hour clock, which nobody misreads. */
export const period = (c: { start_min: number; end_min: number }) =>
  `${clock(c.start_min)}–${clock(c.end_min)}`;

const ROUTINE_SLOTS = new Set(SLOTS as readonly string[]);

/** A time label's start and end in minutes past midnight. The routine writes
 *  the afternoon on a 12-hour clock ("01:00" is 13:00) and no class starts
 *  before 08:00; an online class keeps its own 24-hour label ("07:00-08:30"). */
export function slotMinutes(slot: string): [number, number] | null {
  const [a, b] = slot.split("-");
  if (!a || !b) return null;
  const routine = ROUTINE_SLOTS.has(slot);
  const toMin = (hhmm: string) => {
    const [h, m] = hhmm.split(":").map(Number);
    return (routine && h < 8 ? h + 12 : h) * 60 + m;
  };
  return [toMin(a), toMin(b)];
}

/** A slot label on the 24-hour clock: "01:00-02:30" -> "13:00–14:30". */
export function slot24(slot: string): string {
  const m = slotMinutes(slot);
  return m ? `${clock(m[0])}–${clock(m[1])}` : slot;
}

/** Minutes past midnight on Dhaka's clock, whatever the browser's zone. */
export function dhakaMinutes(): number {
  const now = new Date();
  const dhaka = new Date(now.getTime() + (6 * 60 + now.getTimezoneOffset()) * 60_000);
  return dhaka.getHours() * 60 + dhaka.getMinutes();
}

const asDate = (iso: string) => new Date(`${iso}T00:00:00`);

export function addDays(iso: string, days: number): string {
  const d = asDate(iso);
  d.setDate(d.getDate() + days);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** The Saturday a week starts on: the department's week runs Saturday to Thursday. */
export function weekStart(iso: string): string {
  return addDays(iso, -((asDate(iso).getDay() + 1) % 7));
}

export const longDay = (iso: string) =>
  asDate(iso).toLocaleDateString([], { weekday: "long", day: "numeric", month: "long" });

export const shortDay = (iso: string) =>
  asDate(iso).toLocaleDateString([], { weekday: "short", day: "numeric", month: "short" });

export const weekday = (iso: string) => asDate(iso).toLocaleDateString([], { weekday: "short" });

export const dayOfMonth = (iso: string) => asDate(iso).getDate();

/** "Today", "Tomorrow", or "Tuesday 14 October". */
export function relativeDay(iso: string, today: string): string {
  if (iso === today) return "Today";
  if (iso === addDays(today, 1)) return "Tomorrow";
  return longDay(iso);
}

/** The API sends naive UTC; "3 h ago", "Yesterday", "4 Oct". */
export function ago(iso: string): string {
  const t = new Date(/(Z|[+-]\d\d:?\d\d)$/.test(iso) ? iso : `${iso}Z`).getTime();
  const minutes = Math.round((Date.now() - t) / 60_000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes} min ago`;
  if (minutes < 24 * 60) return `${Math.round(minutes / 60)} h ago`;
  if (minutes < 48 * 60) return "Yesterday";
  return new Date(t).toLocaleDateString([], { day: "numeric", month: "short" });
}

/** The class on now, or the next one still to come; a moved or cancelled one never. */
export function nowOrNext(
  classes: StudentClass[],
  today: string,
  minutes: number,
): { c: StudentClass; now: boolean } | null {
  const on = classes.filter((c) => c.state === "SCHEDULED");
  const current = on.find((c) => c.date === today && c.start_min <= minutes && minutes < c.end_min);
  if (current) return { c: current, now: true };
  const next = on.find((c) => c.date > today || (c.date === today && c.start_min > minutes));
  return next ? { c: next, now: false } : null;
}
