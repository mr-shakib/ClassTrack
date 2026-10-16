"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { mayCheck } from "@/lib/auth";
import type { User } from "@/lib/types";
import {
  ArrowRightIcon,
  BellIcon,
  CalendarIcon,
  ChartIcon,
  CheckIcon,
  ClockIcon,
  CloseIcon,
  DoorIcon,
  FlagIcon,
  MegaphoneIcon,
  MessageIcon,
  PhoneIcon,
  RepeatIcon,
  UserIcon,
} from "./icons";

type Icon = (p: { className?: string }) => React.ReactNode;

/** What the app does, by the names the website sells it under. */
export const APP_FEATURES = {
  alarm: {
    icon: ClockIcon,
    name: "Class Alarm",
    body: "A buzz on your phone minutes before every class, makeups and extra classes included.",
  },
  alerts: {
    icon: BellIcon,
    name: "Live Alerts",
    body: "Missed classes, reschedules and notices from the department, on your phone as they happen.",
  },
  timetable: {
    icon: CalendarIcon,
    name: "Pocket Timetable",
    body: "The class on now at the top, today as a timeline, and any week at a glance.",
  },
  reschedule: {
    icon: RepeatIcon,
    name: "Reschedule Anywhere",
    body: "Find an empty room for a missed class from your phone, and mark the makeup done after it.",
  },
  scorecard: {
    icon: ChartIcon,
    name: "Semester Scorecard",
    body: "Your held, late and missed classes, and every course against its minimum, in one card.",
  },
  headsUp: {
    icon: MessageIcon,
    name: "Heads-up",
    body: "Tell a section about one class, a quiz or laptops, and it shows on the class for them.",
  },
  checking: {
    icon: CheckIcon,
    name: "Tap-to-Check",
    body: "Walk the floor with your phone and report each room in a single tap.",
  },
} satisfies Record<string, { icon: Icon; name: string; body: string }>;

/** What the app does for students, who need no account: they pick their section. */
export const STUDENT_FEATURES = [
  {
    icon: CalendarIcon,
    name: "My Routine",
    body: "Your section's week, today's classes, and the next one with its room and teacher.",
  },
  {
    icon: ClockIcon,
    name: "Class Alarm",
    body: "A buzz before each of your classes, makeups and extra classes included.",
  },
  {
    icon: BellIcon,
    name: "Change Alerts",
    body: "Word on your phone the moment one of your classes moves or is cancelled.",
  },
  {
    icon: RepeatIcon,
    name: "Makeup Radar",
    body: "Every makeup and extra class for your section, with its room or join link.",
  },
  {
    icon: MegaphoneIcon,
    name: "Section Notices",
    body: "Notes from your teachers and the department, written to your section.",
  },
  {
    icon: DoorIcon,
    name: "Free Room Finder",
    body: "Empty rooms right now and later today, for group study.",
  },
  {
    icon: UserIcon,
    name: "Teacher Card",
    body: "Tap a class for its teacher's photo, designation and office room.",
  },
  {
    icon: FlagIcon,
    name: "Semester Calendar",
    body: "Holidays, and how many days are left until the mid-term and final exams.",
  },
];

type Feature = keyof typeof APP_FEATURES;

const TEACHER_FEATURES: Feature[] = [
  "alarm",
  "alerts",
  "timetable",
  "reschedule",
  "headsUp",
  "scorecard",
];

/**
 * The feature that fits the page, or null for no banner. Teachers see one on
 * every page; others who check classes only on Checking, so an admin's
 * dashboards stay quiet.
 */
function featureFor(user: User, pathname: string): Feature | null {
  if (pathname === "/staff" && mayCheck(user)) return "checking";
  if (!user.is_teacher) return null;
  if (pathname === "/teacher") return "timetable";
  if (pathname.startsWith("/teacher/")) return "reschedule";
  if (pathname === "/profile" || pathname === "/reports") return "scorecard";
  return "alarm";
}

/** Asked once per visit: the website offers the app only while there is one to get. */
let available: Promise<boolean> | null = null;
const appAvailable = () =>
  (available ??= api.androidApp().then(
    (a) => a.available,
    () => false,
  ));

/**
 * Whether to offer this user the app: they are someone it is for, their phone
 * does not have it yet, it can be downloaded, and this is not an iPhone, which
 * has no app.
 */
export function useAppOffer(user: User): boolean {
  const [offer, setOffer] = useState(false);
  const wanted = !user.has_app && (user.is_teacher || mayCheck(user));

  useEffect(() => {
    if (!wanted || /iPhone|iPad|iPod/i.test(navigator.userAgent)) return;
    let alive = true;
    void appAvailable().then((yes) => alive && setOffer(yes));
    return () => {
      alive = false;
    };
  }, [wanted]);

  return wanted && offer;
}

// A closed banner stays closed for a week, that feature only: the next page
// can still offer another.
const DISMISSED = "classtrack.app-promo";
const QUIET_MS = 7 * 24 * 60 * 60 * 1000;

function dismissedAt(): Partial<Record<Feature, number>> {
  try {
    return JSON.parse(localStorage.getItem(DISMISSED) ?? "{}");
  } catch {
    return {};
  }
}

function dismiss(feature: Feature) {
  try {
    localStorage.setItem(DISMISSED, JSON.stringify({ ...dismissedAt(), [feature]: Date.now() }));
  } catch {
    /* private window: it comes back on the next page, which is fine */
  }
}

/** Above each page: the one thing the app does best for what is on it. */
export function AppPromo({ user, pathname }: { user: User; pathname: string }) {
  const offer = useAppOffer(user);
  const feature = pathname === "/app" ? null : featureFor(user, pathname);
  const [closed, setClosed] = useState<Feature[] | null>(null);

  // Read after mounting: the server has no storage, and the first render must match it.
  useEffect(() => {
    const since = Date.now() - QUIET_MS;
    setClosed(
      Object.entries(dismissedAt())
        .filter(([, at]) => (at ?? 0) > since)
        .map(([f]) => f as Feature),
    );
  }, []);

  if (!offer || !feature || closed == null || closed.includes(feature)) return null;

  const f = APP_FEATURES[feature];
  const others = (user.is_teacher ? TEACHER_FEATURES : (["checking", "alerts"] as Feature[]))
    .filter((k) => k !== feature)
    .map((k) => APP_FEATURES[k].name);

  return (
    <aside className="relative mb-6 overflow-hidden rounded-xl border border-brand/20 bg-brand-soft">
      <div className="flex flex-col gap-4 p-4 pr-12 sm:flex-row sm:items-center sm:gap-5 sm:p-5 sm:pr-14">
        <div className="flex min-w-0 flex-1 gap-4">
          <span className="grid size-12 shrink-0 place-items-center rounded-xl bg-brand text-white shadow-sm">
            <f.icon className="size-6" />
          </span>
          <div className="min-w-0">
            <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-brand">
              <PhoneIcon className="size-3.5" />
              In the ClassTrack app
            </p>
            <p className="mt-0.5 text-lg font-bold leading-snug text-ink">{f.name}</p>
            <p className="mt-0.5 text-sm text-ink-soft">{f.body}</p>
            {others.length ? (
              <p className="mt-1.5 hidden text-xs text-ink-faint md:block">
                Plus {others.slice(0, -1).join(", ")}
                {others.length > 1 ? " and " : ""}
                {others.at(-1)}.
              </p>
            ) : null}
          </div>
        </div>
        <Link
          href="/app"
          className="inline-flex min-h-11 shrink-0 items-center justify-center gap-2 rounded-xl bg-brand px-5 py-2.5 text-base font-semibold text-white hover:bg-brand/90"
        >
          Get the app
          <ArrowRightIcon className="size-4" />
        </Link>
      </div>
      <button
        type="button"
        onClick={() => {
          dismiss(feature);
          setClosed((c) => [...(c ?? []), feature]);
        }}
        aria-label="Not now"
        className="absolute right-2 top-2 rounded-lg p-2 text-ink-faint hover:bg-surface hover:text-ink"
      >
        <CloseIcon className="size-5" />
      </button>
    </aside>
  );
}
