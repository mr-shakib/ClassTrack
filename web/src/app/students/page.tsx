"use client";

import Image from "next/image";
import Link from "next/link";
import { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import SectionPicker from "@/components/student/SectionPicker";
import {
  CalendarView,
  ClassDialog,
  RadarView,
  RoomsView,
  RoutineView,
  StudentAppBanner,
  UpdatesView,
  readSeen,
} from "@/components/student/StudentViews";
import { CloudOffIcon, LinkIcon } from "@/components/icons";
import { Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { groupLabel, loadGroups, parseGroups, saveGroups } from "@/lib/student";
import type { StudentClass } from "@/lib/types";

const TABS = [
  { key: "routine", label: "My Routine" },
  { key: "radar", label: "Makeup Radar" },
  { key: "updates", label: "Updates" },
  { key: "rooms", label: "Free rooms" },
  { key: "calendar", label: "Calendar" },
] as const;

type Tab = (typeof TABS)[number]["key"];

/** Public: a student's routine by section. No sign-in. */
export default function StudentsPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <Students />
    </Suspense>
  );
}

function Students() {
  const params = useSearchParams();
  const router = useRouter();
  const { user, loading } = useAuth();
  // Null until the browser has said what it remembers.
  const [groups, setGroups] = useState<string[] | null>(null);
  const [picking, setPicking] = useState(false);
  const [tab, setTab] = useState<Tab>(() => {
    const t = params.get("tab");
    return TABS.some((x) => x.key === t) ? (t as Tab) : "routine";
  });
  const [open, setOpen] = useState<StudentClass | null>(null);
  const [unread, setUnread] = useState(0);
  const [copied, setCopied] = useState(false);

  const fromLink = params.get("g");
  const focusDate = params.get("date");

  useEffect(() => {
    const linked = parseGroups(fromLink);
    if (linked.length > 0) {
      setGroups(linked);
      // A shared link is someone else's choice until it is saved: only keep it
      // when this browser has none of its own.
      if (loadGroups().length === 0) saveGroups(linked);
    } else {
      setGroups(loadGroups());
    }
  }, [fromLink]);

  const choose = (picked: string[]) => {
    saveGroups(picked);
    setGroups(picked);
    setPicking(false);
    router.replace(`/students?g=${picked.join(",")}`);
  };

  const key = groups?.join(",") ?? "";
  const countUnread = useCallback(async () => {
    if (!key) return;
    try {
      const seen = readSeen();
      setUnread((await api.studentNotices(key.split(","))).filter((n) => n.id > seen).length);
    } catch {
      /* the badge is not worth an error */
    }
  }, [key]);

  useEffect(() => {
    void countUnread();
  }, [countUnread]);

  const offline = useOffline();

  const signedOut = !loading && !user;

  const share = async () => {
    const url = `${window.location.origin}/students?g=${groups!.join(",")}`;
    try {
      if (navigator.share) await navigator.share({ title: "Our class routine", url });
      else {
        await navigator.clipboard.writeText(url);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }
    } catch {
      /* dismissed */
    }
  };

  const body =
    groups == null ? (
      <Spinner />
    ) : groups.length === 0 || picking ? (
      <SectionPicker
        initial={groups}
        onDone={choose}
        onCancel={groups.length > 0 ? () => setPicking(false) : undefined}
      />
    ) : (
      <div className="space-y-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Your classes</h1>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {groups.map((g) => (
                <span key={g} className="rounded-lg bg-surface px-2.5 py-1 text-sm font-semibold ring-1 ring-inset ring-line">
                  {groupLabel(g)}
                </span>
              ))}
            </div>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={share}
              className="inline-flex min-h-10 items-center gap-1.5 rounded-lg px-3 text-sm font-semibold text-ink-soft ring-1 ring-inset ring-line hover:bg-surface"
            >
              <LinkIcon className="size-4" />
              {copied ? "Link copied" : "Share"}
            </button>
            <button
              type="button"
              onClick={() => setPicking(true)}
              className="inline-flex min-h-10 items-center rounded-lg px-3 text-sm font-semibold text-brand ring-1 ring-inset ring-brand/30 hover:bg-brand-soft"
            >
              Change section
            </button>
          </div>
        </div>

        {offline ? (
          <p className="flex items-center gap-2 rounded-xl bg-surface px-4 py-3 text-sm font-medium text-ink-soft ring-1 ring-inset ring-line">
            <CloudOffIcon className="size-5 shrink-0 text-ink-faint" />
            You are offline. This is what was saved the last time you opened it; it updates when you are back online.
          </p>
        ) : null}

        <StudentAppBanner />

        <nav className="-mx-4 flex gap-1 overflow-x-auto px-4 sm:mx-0 sm:px-0" aria-label="Student views">
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              aria-current={tab === t.key ? "page" : undefined}
              onClick={() => setTab(t.key)}
              className={`relative whitespace-nowrap rounded-lg px-3.5 py-2 text-base font-semibold transition-colors ${
                tab === t.key ? "bg-brand text-white" : "text-ink-soft hover:bg-surface"
              }`}
            >
              {t.label}
              {t.key === "updates" && unread > 0 ? (
                <span className="ml-1.5 rounded-full bg-bad px-1.5 py-0.5 text-xs font-bold text-white">
                  {unread > 9 ? "9+" : unread}
                </span>
              ) : null}
            </button>
          ))}
        </nav>

        {tab === "routine" ? (
          <RoutineView groups={groups} focusDate={focusDate} onOpen={setOpen} />
        ) : tab === "radar" ? (
          <RadarView groups={groups} onOpen={setOpen} />
        ) : tab === "updates" ? (
          <UpdatesView groups={groups} onOpen={setOpen} onSeen={() => setUnread(0)} />
        ) : tab === "rooms" ? (
          <RoomsView />
        ) : (
          <CalendarView />
        )}

        {open ? <ClassDialog c={open} onClose={() => setOpen(null)} /> : null}
      </div>
    );

  if (!signedOut) return <div className="mx-auto max-w-5xl">{body}</div>;

  // Signed out, the page stands alone, like sign-in.
  return (
    <div className="min-h-dvh bg-canvas">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-2.5">
          <Link href="/students" className="flex items-center gap-2.5 font-semibold">
            <Image src="/diu-logo.png" alt="Daffodil International University" width={756} height={289} className="h-8 w-auto" preload />
            <span className="hidden border-l border-line pl-2.5 sm:inline">ClassTrack for students</span>
          </Link>
          <div className="flex items-center gap-3 text-sm font-medium">
            <Link href="/app" className="text-brand hover:underline">
              Get the app
            </Link>
            <Link href="/login" className="text-ink-soft hover:underline">
              Staff sign in
            </Link>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">{body}</main>
      <footer className="pb-6 text-center text-xs text-ink-faint">
        <Link href="/privacy" className="hover:text-brand hover:underline">
          Privacy policy
        </Link>
      </footer>
    </div>
  );
}

/**
 * Whether the browser has no network, and the offline worker set up on the
 * way: once this page has been opened with a signal, it opens without one.
 */
function useOffline(): boolean {
  const [offline, setOffline] = useState(false);
  useEffect(() => {
    const update = () => setOffline(!navigator.onLine);
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);

    if ("serviceWorker" in navigator) {
      navigator.serviceWorker
        .register("/sw.js", { scope: "/" })
        .then(() => navigator.serviceWorker.ready)
        .then((registration) => {
          // The files this page loaded before the worker was in charge of it.
          const urls = [
            ...Array.from(document.scripts, (s) => s.src),
            ...Array.from(document.querySelectorAll<HTMLLinkElement>('link[rel="stylesheet"]'), (l) => l.href),
            ...performance.getEntriesByType("resource").map((e) => e.name),
          ].filter(Boolean);
          registration.active?.postMessage({ type: "keep", urls });
        })
        .catch(() => {
          /* without the worker the page still works, only not offline */
        });
    }
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);
  return offline;
}
