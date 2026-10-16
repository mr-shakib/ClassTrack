"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Avatar } from "@/components/Avatar";
import { Card, EmptyState, ErrorNote, Spinner } from "@/components/ui";
import {
  BellIcon,
  BuildingIcon,
  CalendarIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ClockIcon,
  CloseIcon,
  DoorIcon,
  MegaphoneIcon,
  MessageIcon,
  RepeatIcon,
  VideoIcon,
} from "@/components/icons";
import { api, todayISO } from "@/lib/api";
import {
  addDays,
  ago,
  dayOfMonth,
  dhakaMinutes,
  longDay,
  nowOrNext,
  period,
  relativeDay,
  shortDay,
  slot24,
  slotMinutes,
  weekStart,
  weekday,
} from "@/lib/student";
import type { FreeSlot, StudentCalendar, StudentClass, StudentNotice } from "@/lib/types";

// --- one class ---------------------------------------------------------------------

function Where({ c, className = "" }: { c: StudentClass; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 ${className}`}>
      {c.online ? <VideoIcon className="size-4" /> : <DoorIcon className="size-4" />}
      {c.online ? "Online" : c.room}
    </span>
  );
}

/** What is unusual about a class, if anything: the badge beside it. */
function Badge({ c }: { c: StudentClass }) {
  if (c.state === "CANCELLED")
    return <span className="rounded-md bg-bad-soft px-2 py-0.5 text-xs font-bold text-bad">Cancelled</span>;
  if (c.state === "MOVED")
    return (
      <span className="rounded-md bg-info-soft px-2 py-0.5 text-xs font-bold text-info">
        Moved{c.moved_to ? ` to ${shortDay(c.moved_to.date)}` : ""}
      </span>
    );
  if (c.kind === "MAKEUP")
    return (
      <span className="rounded-md border border-dashed border-info/60 bg-info-soft px-2 py-0.5 text-xs font-bold text-info">
        {c.online ? "Online makeup" : "Makeup"}
      </span>
    );
  if (c.kind === "EXTRA")
    return <span className="rounded-md bg-brand-soft px-2 py-0.5 text-xs font-bold text-brand">Extra class</span>;
  return null;
}

export function ClassRow({
  c,
  onOpen,
  showDay = false,
}: {
  c: StudentClass;
  onOpen: (c: StudentClass) => void;
  showDay?: boolean;
}) {
  const off = c.state !== "SCHEDULED";
  return (
    <li>
      <button
        type="button"
        onClick={() => onOpen(c)}
        className="flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-canvas"
      >
        <div className="w-16 shrink-0 tabular-nums">
          {showDay ? <p className="text-xs font-semibold uppercase text-ink-faint">{shortDay(c.date)}</p> : null}
          <p className={`text-base font-bold ${off ? "text-ink-faint line-through" : ""}`}>
            {period(c).split("–")[0]}
          </p>
          <p className="text-xs text-ink-faint">{period(c).split("–")[1]}</p>
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <p className={`font-semibold ${off ? "text-ink-soft" : ""}`}>{c.course_code}</p>
            <Badge c={c} />
            {c.note ? (
              <span title="Your teacher left a note" className="text-brand">
                <MessageIcon className="size-4" />
              </span>
            ) : null}
          </div>
          {c.course_title ? <p className="truncate text-sm text-ink-soft">{c.course_title}</p> : null}
          <p className="mt-0.5 flex flex-wrap gap-x-3 text-sm text-ink-soft">
            <Where c={c} />
            <span>{c.teacher.name ?? c.teacher.initial}</span>
            <span className="text-ink-faint">{c.section}</span>
          </p>
        </div>
      </button>
    </li>
  );
}

/** One class in full: the teacher's card, a note from them, where it moved, how to join. */
export function ClassDialog({ c, onClose }: { c: StudentClass; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const t = c.teacher;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/40 p-0 sm:items-center sm:p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={c.course_code}
        className="max-h-[92dvh] w-full max-w-lg overflow-y-auto rounded-t-2xl bg-surface shadow-xl sm:rounded-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-2xl font-bold tracking-tight">{c.course_code}</h2>
              <Badge c={c} />
            </div>
            {c.course_title ? <p className="text-base text-ink-soft">{c.course_title}</p> : null}
            <p className="text-sm text-ink-faint">Section {c.section}</p>
          </div>
          <button type="button" aria-label="Close" onClick={onClose} className="rounded-lg p-2 text-ink-faint hover:bg-canvas">
            <CloseIcon className="size-5" />
          </button>
        </div>

        <div className="space-y-4 px-5 py-4">
          <ul className="space-y-2 text-base">
            <li className="flex items-center gap-3">
              <CalendarIcon className="size-5 text-ink-faint" />
              {longDay(c.date)}
            </li>
            <li className="flex items-center gap-3 tabular-nums">
              <ClockIcon className="size-5 text-ink-faint" />
              {period(c)}
            </li>
            <li className="flex items-center gap-3">
              {c.online ? <VideoIcon className="size-5 text-ink-faint" /> : <DoorIcon className="size-5 text-ink-faint" />}
              {c.online ? "Online" : `Room ${c.room}`}
              {!c.online && c.room_type ? <span className="text-sm text-ink-faint">· {c.room_type}</span> : null}
            </li>
          </ul>

          {c.state === "MOVED" && c.moved_to ? (
            <p className="rounded-xl bg-info-soft px-4 py-3 text-base text-info">
              <RepeatIcon className="mr-1.5 inline size-4" />
              Moved to <strong>{longDay(c.moved_to.date)}</strong>, {slot24(c.moved_to.time_slot)}
              {c.moved_to.online ? ", online" : c.moved_to.room ? `, room ${c.moved_to.room}` : ""}.
            </p>
          ) : null}
          {c.state === "CANCELLED" ? (
            <p className="rounded-xl bg-bad-soft px-4 py-3 text-base font-semibold text-bad">This class will not be held.</p>
          ) : null}
          {c.kind === "MAKEUP" && c.makeup_for ? (
            <p className="rounded-xl border border-dashed border-info/50 bg-info-soft px-4 py-3 text-base text-info">
              Makes up the class of {longDay(c.makeup_for.date)}, {slot24(c.makeup_for.time_slot)}.
            </p>
          ) : null}
          {c.online && c.join_link ? (
            <a
              href={c.join_link}
              target="_blank"
              rel="noopener noreferrer"
              className="flex min-h-12 items-center justify-center gap-2 rounded-xl bg-brand px-4 py-3 text-base font-semibold text-white hover:bg-brand/90"
            >
              <VideoIcon className="size-5" />
              Join the class
            </a>
          ) : c.online ? (
            <p className="rounded-xl bg-canvas px-4 py-3 text-sm text-ink-soft">
              Your teacher has not added a join link yet. It appears here when they do.
            </p>
          ) : null}
          {c.note ? (
            <div className="rounded-xl border border-brand/20 bg-brand-soft px-4 py-3">
              <p className="flex items-center gap-1.5 text-sm font-semibold text-brand">
                <MessageIcon className="size-4" />
                Note from your teacher · {ago(c.note.created_at)}
              </p>
              <p className="mt-1 whitespace-pre-line text-base">{c.note.body}</p>
            </div>
          ) : null}

          <section className="rounded-2xl border border-line p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-faint">Teacher card</p>
            <div className="mt-3 flex items-center gap-4">
              <Avatar name={t.name ?? t.initial} initial={t.initial} photo={t.photo_url} size="md" />
              <div className="min-w-0">
                <p className="text-lg font-bold leading-snug">{t.name ?? t.initial}</p>
                <p className="text-sm text-ink-soft">
                  {[t.designation, t.initial].filter(Boolean).join(" · ")}
                </p>
              </div>
            </div>
            {t.office_room ? (
              <p className="mt-3 flex items-center gap-2 text-sm text-ink-soft">
                <BuildingIcon className="size-4 text-ink-faint" />
                Office: <span className="font-semibold text-ink">{t.office_room}</span>
              </p>
            ) : null}
          </section>
        </div>
      </div>
    </div>
  );
}

/** Classes from today, shared by the routine's "up next" card and the radar. */
function useUpcoming(groups: string[]) {
  const [rows, setRows] = useState<StudentClass[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const key = groups.join(",");

  const load = useCallback(async () => {
    const today = todayISO();
    try {
      setRows(await api.studentClasses(key.split(","), today, addDays(today, 27)));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load your classes.");
    }
  }, [key]);

  useEffect(() => {
    void load();
    const timer = setInterval(() => void load(), 120_000);
    return () => clearInterval(timer);
  }, [load]);

  return { rows, error };
}

// --- My Routine ---------------------------------------------------------------------

function UpNext({ c, now, today }: { c: StudentClass; now: boolean; today: string }) {
  const minutes = dhakaMinutes();
  return (
    <div className="rounded-2xl bg-gradient-to-br from-brand to-[#1563b0] p-5 text-white shadow-sm">
      <p className="inline-flex items-center gap-2 rounded-full bg-white/15 px-3 py-1 text-xs font-bold uppercase tracking-wider">
        {now ? <span className="size-2 rounded-full bg-emerald-300" /> : null}
        {now ? "In class now" : c.date === today ? "Next class" : `Next class · ${relativeDay(c.date, today)}`}
      </p>
      <p className="mt-3 text-3xl font-extrabold tracking-tight">{c.course_code}</p>
      {c.course_title ? <p className="text-base text-white/80">{c.course_title}</p> : null}
      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-base font-semibold">
        <Where c={c} />
        <span className="inline-flex items-center gap-1.5 tabular-nums">
          <ClockIcon className="size-4" />
          {period(c)}
        </span>
        <span>{c.teacher.name ?? c.teacher.initial}</span>
      </div>
      {!now && c.date === today ? (
        <p className="mt-4 rounded-xl bg-white/15 px-4 py-2.5 text-base font-bold">
          Starts in {spanLabel(c.start_min - minutes)}
        </p>
      ) : now ? (
        <p className="mt-4 rounded-xl bg-white/15 px-4 py-2.5 text-base font-bold">
          Ends in {spanLabel(c.end_min - minutes)}
        </p>
      ) : null}
      {c.online && c.join_link ? (
        <a
          href={c.join_link}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 inline-flex min-h-11 items-center gap-2 rounded-xl bg-white px-4 py-2 text-base font-bold text-brand"
        >
          <VideoIcon className="size-5" />
          Join the class
        </a>
      ) : null}
    </div>
  );
}

const spanLabel = (m: number) => (m < 60 ? `${m} min` : `${Math.floor(m / 60)} h${m % 60 ? ` ${m % 60} min` : ""}`);

export function RoutineView({
  groups,
  focusDate,
  onOpen,
}: {
  groups: string[];
  focusDate: string | null;
  onOpen: (c: StudentClass) => void;
}) {
  const today = todayISO();
  // On the Friday weekend this week is over, so "this week" is the next one.
  const thisWeek = addDays(weekStart(today), new Date(`${today}T00:00:00`).getDay() === 5 ? 7 : 0);
  const [week, setWeek] = useState(() => (focusDate ? weekStart(focusDate) : thisWeek));
  const [rows, setRows] = useState<StudentClass[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const upcoming = useUpcoming(groups);
  const key = groups.join(",");

  useEffect(() => {
    let alive = true;
    setRows(null);
    api.studentClasses(key.split(","), week, addDays(week, 6)).then(
      (r) => alive && (setRows(r), setError(null)),
      (err) => alive && setError(err instanceof Error ? err.message : "Could not load the week."),
    );
    return () => {
      alive = false;
    };
  }, [key, week]);

  const days = useMemo(() => {
    const list = Array.from({ length: 6 }, (_, i) => addDays(week, i));
    // Friday only when something is on it.
    if (rows?.some((r) => r.date === addDays(week, 6))) list.push(addDays(week, 6));
    return list;
  }, [week, rows]);

  const next = upcoming.rows ? nowOrNext(upcoming.rows, today, dhakaMinutes()) : null;
  const end = addDays(week, 5);

  return (
    <div className="space-y-5">
      {next ? <UpNext c={next.c} now={next.now} today={today} /> : null}

      <Card>
        <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
          <button type="button" aria-label="Previous week" onClick={() => setWeek(addDays(week, -7))} className="rounded-lg p-2 hover:bg-canvas">
            <ChevronLeftIcon className="size-5" />
          </button>
          <div className="text-center">
            <p className="text-base font-bold">
              {shortDay(week)} – {shortDay(end)}
            </p>
            {week === thisWeek ? (
              <p className="text-xs font-semibold text-brand">
                {thisWeek === weekStart(today) ? "This week" : "Next week"}
              </p>
            ) : (
              <button type="button" className="text-xs font-semibold text-brand hover:underline" onClick={() => setWeek(thisWeek)}>
                Back to this week
              </button>
            )}
          </div>
          <button type="button" aria-label="Next week" onClick={() => setWeek(addDays(week, 7))} className="rounded-lg p-2 hover:bg-canvas">
            <ChevronRightIcon className="size-5" />
          </button>
        </div>
        {error ? (
          <div className="p-4">
            <ErrorNote message={error} />
          </div>
        ) : rows == null ? (
          <Spinner />
        ) : (
          <div className="grid divide-y divide-line lg:grid-cols-3 lg:divide-y-0">
            {days.map((d) => {
              const list = rows.filter((r) => r.date === d);
              return (
                <section key={d} className={`lg:border-line ${d === today ? "bg-brand-soft/40" : ""} lg:border-b lg:[&:nth-child(3n+1)]:border-r lg:[&:nth-child(3n+2)]:border-r`}>
                  <div className="flex items-baseline gap-2 px-4 pt-3">
                    <span className={`text-2xl font-extrabold tabular-nums ${d === today ? "text-brand" : ""}`}>{dayOfMonth(d)}</span>
                    <span className="text-sm font-semibold uppercase text-ink-soft">{weekday(d)}</span>
                    {d === today ? <span className="text-xs font-bold text-brand">Today</span> : null}
                  </div>
                  {list.length === 0 ? (
                    <p className="px-4 pb-4 pt-1 text-sm text-ink-faint">No classes</p>
                  ) : (
                    <ul className="divide-y divide-line">
                      {list.map((c) => (
                        <ClassRow key={c.id} c={c} onOpen={onOpen} />
                      ))}
                    </ul>
                  )}
                </section>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}

// --- Makeup Radar --------------------------------------------------------------------

export function RadarView({ groups, onOpen }: { groups: string[]; onOpen: (c: StudentClass) => void }) {
  const { rows, error } = useUpcoming(groups);
  const today = todayISO();
  const now = dhakaMinutes();
  const radar = (rows ?? []).filter(
    (c) => (c.kind !== "CLASS" || c.state !== "SCHEDULED") && (c.date > today || c.end_min > now),
  );

  return (
    <Card>
      <div className="border-b border-line px-4 py-4">
        <h2 className="text-xl font-bold">Makeup Radar</h2>
        <p className="text-sm text-ink-soft">
          Makeups, extra classes and cancellations for your groups, the next four weeks.
        </p>
      </div>
      {error ? (
        <div className="p-4">
          <ErrorNote message={error} />
        </div>
      ) : rows == null ? (
        <Spinner />
      ) : radar.length === 0 ? (
        <EmptyState title="Nothing off the routine" body="No makeup, extra or cancelled class coming up." />
      ) : (
        <ul className="divide-y divide-line">
          {radar.map((c) => (
            <ClassRow key={c.id} c={c} onOpen={onOpen} showDay />
          ))}
        </ul>
      )}
    </Card>
  );
}

// --- Updates -------------------------------------------------------------------------

const SEEN_KEY = "classtrack.student-seen";

export function readSeen(): number {
  try {
    return Number(localStorage.getItem(SEEN_KEY) ?? 0) || 0;
  } catch {
    return 0;
  }
}

function markSeen(id: number) {
  try {
    localStorage.setItem(SEEN_KEY, String(id));
  } catch {
    /* unread dots come back next time: harmless */
  }
}

export function UpdatesView({
  groups,
  onOpen,
  onSeen,
}: {
  groups: string[];
  onOpen: (c: StudentClass) => void;
  onSeen: () => void;
}) {
  const [rows, setRows] = useState<StudentNotice[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [seen] = useState(readSeen);
  const key = groups.join(",");

  useEffect(() => {
    api.studentNotices(key.split(",")).then(
      (r) => {
        setRows(r);
        if (r[0]) markSeen(r[0].id);
        onSeen();
      },
      (err) => setError(err instanceof Error ? err.message : "Could not load updates."),
    );
  }, [key, onSeen]);

  return (
    <Card>
      <div className="border-b border-line px-4 py-4">
        <h2 className="text-xl font-bold">Updates</h2>
        <p className="text-sm text-ink-soft">
          Change Alerts when one of your classes moves, and notices from your teachers and the
          department.
        </p>
      </div>
      {error ? (
        <div className="p-4">
          <ErrorNote message={error} />
        </div>
      ) : rows == null ? (
        <Spinner />
      ) : rows.length === 0 ? (
        <EmptyState title="Nothing yet" body="When a class of yours moves, or someone writes to your section, it shows here." />
      ) : (
        <ul className="divide-y divide-line">
          {rows.map((n) => {
            const look =
              n.kind === "CHANGE"
                ? { icon: RepeatIcon, tone: "bg-info-soft text-info" }
                : n.kind === "TEACHER"
                  ? { icon: MessageIcon, tone: "bg-brand-soft text-brand" }
                  : { icon: MegaphoneIcon, tone: "bg-warn-soft text-warn" };
            return (
              <li key={n.id} className="flex gap-3 px-4 py-4">
                <span className={`grid size-10 shrink-0 place-items-center rounded-xl ${look.tone}`}>
                  <look.icon className="size-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-semibold">
                      {n.title}
                      {n.id > seen ? <span className="ml-2 inline-block size-2 rounded-full bg-brand align-middle" /> : null}
                    </p>
                    <span className="shrink-0 text-xs text-ink-faint">{ago(n.created_at)}</span>
                  </div>
                  <p className="mt-0.5 whitespace-pre-line text-sm text-ink-soft">{n.body}</p>
                  <p className="mt-1 text-xs text-ink-faint">{n.author}</p>
                  {n.about ? (
                    <button
                      type="button"
                      onClick={() => onOpen(n.about!)}
                      className="mt-2 inline-flex items-center gap-1 rounded-lg bg-canvas px-2.5 py-1 text-xs font-semibold text-brand hover:bg-brand-soft"
                    >
                      Open the class <ChevronRightIcon className="size-3.5" />
                    </button>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

// --- Free Room Finder ---------------------------------------------------------------

export function RoomsView() {
  const today = todayISO();
  const [day, setDay] = useState(today);
  const [slots, setSlots] = useState<FreeSlot[] | null>(null);
  const [slot, setSlot] = useState<string | null>(null);
  const [kind, setKind] = useState<"all" | "Theory" | "Lab">("all");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setSlots(null);
    api.studentFreeRooms(day).then(
      (s) => {
        if (!alive) return;
        setSlots(s);
        setError(null);
        // The slot on now, or the next one; on another day, the first.
        const now = dhakaMinutes();
        const pick =
          day === today
            ? s.find((x) => (slotMinutes(x.time_slot)?.[1] ?? 0) > now)
            : s[0];
        setSlot(pick?.time_slot ?? s[0]?.time_slot ?? null);
      },
      (err) => alive && setError(err instanceof Error ? err.message : "Could not load rooms."),
    );
    return () => {
      alive = false;
    };
  }, [day, today]);

  const current = slots?.find((s) => s.time_slot === slot);
  // The routine types a lab "Lab", "Computer Lab" and the like.
  const isLab = (type: string) => /lab/i.test(type);
  const rooms = (current?.rooms ?? []).filter(
    (r) => kind === "all" || (kind === "Lab") === isLab(r.room_type),
  );
  const byZone = rooms.reduce<Record<string, typeof rooms>>((acc, r) => {
    (acc[r.zone] ??= []).push(r);
    return acc;
  }, {});

  const pill = (on: boolean) =>
    `rounded-lg px-3 py-1.5 text-sm font-semibold ring-1 ring-inset ${on ? "bg-brand text-white ring-brand" : "bg-surface text-ink-soft ring-line hover:bg-canvas"}`;

  return (
    <Card>
      <div className="space-y-3 border-b border-line px-4 py-4">
        <div>
          <h2 className="text-xl font-bold">Free Room Finder</h2>
          <p className="text-sm text-ink-soft">Rooms with no class in them, for group study.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {[today, addDays(today, 1)].map((d) => (
            <button key={d} type="button" className={pill(day === d)} onClick={() => setDay(d)}>
              {relativeDay(d, today)}
            </button>
          ))}
        </div>
        {slots && slots.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {slots.map((s) => (
              <button key={s.time_slot} type="button" className={`${pill(slot === s.time_slot)} tabular-nums`} onClick={() => setSlot(s.time_slot)}>
                {slot24(s.time_slot)}
              </button>
            ))}
          </div>
        ) : null}
        {current ? (
          <div className="flex flex-wrap gap-2">
            {(["all", "Theory", "Lab"] as const).map((k) => (
              <button key={k} type="button" className={pill(kind === k)} onClick={() => setKind(k)}>
                {k === "all" ? "All rooms" : k === "Theory" ? "Classrooms" : "Labs"}
              </button>
            ))}
          </div>
        ) : null}
      </div>
      {error ? (
        <div className="p-4">
          <ErrorNote message={error} />
        </div>
      ) : slots == null ? (
        <Spinner />
      ) : slots.length === 0 ? (
        <EmptyState title="No classes that day" body="On a weekend or a holiday nothing is listed, since rooms may be locked." />
      ) : rooms.length === 0 ? (
        <EmptyState title="No free room then" body="Every room is taken in that slot. Try another." />
      ) : (
        <div className="space-y-4 p-4">
          <p className="text-sm font-semibold text-ok">{rooms.length} free in {slot ? slot24(slot) : ""}</p>
          {Object.entries(byZone).map(([zone, list]) => (
            <section key={zone}>
              <h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-ink-faint">{zone}</h3>
              <ul className="flex flex-wrap gap-2">
                {list.map((r) => (
                  <li key={r.room} className="rounded-lg border border-ok/25 bg-ok-soft px-3 py-1.5 text-sm font-semibold text-ok">
                    {r.room}
                    {isLab(r.room_type) ? <span className="ml-1 font-normal text-ok/80">· Lab</span> : null}
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </Card>
  );
}

// --- Semester Calendar ----------------------------------------------------------------

export function CalendarView() {
  const [cal, setCal] = useState<StudentCalendar | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const today = todayISO();

  useEffect(() => {
    api.studentCalendar().then(setCal, () => setError("Could not load the calendar."));
  }, []);

  if (error) return <ErrorNote message={error} />;
  if (cal === undefined) return <Spinner />;
  if (cal === null) return <Card><EmptyState title="No semester running" /></Card>;

  const upcoming = cal.holidays.filter((h) => h.date >= today);
  const past = cal.holidays.filter((h) => h.date < today);
  const kindLabel = (k: string) =>
    k === "SPECIAL" ? "Extra teaching day" : k === "EXAM" ? "Exam day" : k === "CLOSED" ? "Closed" : "Holiday";

  return (
    <div className="space-y-4">
      <Card className="p-5">
        <p className="text-sm font-semibold text-brand">Semester Calendar</p>
        <h2 className="mt-1 text-2xl font-bold">{cal.name}</h2>
        <p className="text-base text-ink-soft">
          {longDay(cal.start_date)} – {longDay(cal.end_date)}
        </p>
        {cal.exams.length > 0 ? (
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {cal.exams.map((e) => {
              const days = Math.ceil((new Date(`${e.start}T00:00:00`).getTime() - new Date(`${today}T00:00:00`).getTime()) / 86_400_000);
              return (
                <div key={e.name} className="rounded-xl border border-warn/25 bg-warn-soft px-4 py-3">
                  <p className="font-bold text-warn">{e.name}</p>
                  <p className="text-sm text-ink">
                    {shortDay(e.start)} – {shortDay(e.end)}
                  </p>
                  <p className="mt-1 text-xs font-semibold text-warn">
                    {days > 0 ? `In ${days} day${days === 1 ? "" : "s"}` : e.end >= today ? "Under way" : "Over"}
                  </p>
                </div>
              );
            })}
          </div>
        ) : null}
      </Card>

      <Card>
        <div className="border-b border-line px-4 py-3">
          <h3 className="text-lg font-bold">Days with no classes</h3>
        </div>
        {cal.holidays.length === 0 ? (
          <EmptyState title="None announced" />
        ) : (
          <ul className="divide-y divide-line">
            {[...upcoming, ...past].map((h) => (
              <li key={h.date} className={`flex items-center gap-4 px-4 py-3 ${h.date < today ? "opacity-50" : ""}`}>
                <div className="w-14 text-center">
                  <p className="text-xl font-extrabold tabular-nums">{dayOfMonth(h.date)}</p>
                  <p className="text-xs font-semibold uppercase text-ink-faint">
                    {new Date(`${h.date}T00:00:00`).toLocaleDateString([], { month: "short" })}
                  </p>
                </div>
                <div>
                  <p className="font-semibold">{h.title}</p>
                  <p className="text-sm text-ink-soft">
                    {weekday(h.date)} · {kindLabel(h.kind)}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

// --- the app --------------------------------------------------------------------------

/** For students: the app is where Class Alarm and Change Alerts live. */
export function StudentAppBanner() {
  const [show, setShow] = useState(false);
  useEffect(() => {
    let closed = 0;
    try {
      closed = Number(localStorage.getItem("classtrack.student-app-banner") ?? 0);
    } catch {
      /* show it */
    }
    const ios = /iPhone|iPad|iPod/i.test(navigator.userAgent);
    let alive = true;
    if (!ios && Date.now() - closed > 7 * 86_400_000) {
      api.androidApp().then((a) => alive && setShow(a.available), () => {});
    }
    return () => {
      alive = false;
    };
  }, []);
  if (!show) return null;
  return (
    <aside className="relative flex flex-col gap-3 overflow-hidden rounded-xl border border-brand/20 bg-brand-soft p-4 pr-12 sm:flex-row sm:items-center">
      <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-brand text-white">
        <BellIcon className="size-6" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="font-bold">Class Alarm &amp; Change Alerts on your phone</p>
        <p className="text-sm text-ink-soft">
          A buzz before every class, and word the moment one moves. Free for Android, no sign-in.
        </p>
      </div>
      <a href="/app" className="inline-flex min-h-11 shrink-0 items-center justify-center rounded-xl bg-brand px-4 py-2 text-base font-semibold text-white hover:bg-brand/90">
        Get the app
      </a>
      <button
        type="button"
        aria-label="Not now"
        className="absolute right-2 top-2 rounded-lg p-2 text-ink-faint hover:bg-surface"
        onClick={() => {
          setShow(false);
          try {
            localStorage.setItem("classtrack.student-app-banner", String(Date.now()));
          } catch {
            /* it comes back next time */
          }
        }}
      >
        <CloseIcon className="size-5" />
      </button>
    </aside>
  );
}
