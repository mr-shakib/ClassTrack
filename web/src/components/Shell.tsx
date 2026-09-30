"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ADMIN_ROLES, CHECKING_ROLES, MANAGEMENT_ROLES, ROLE_LABELS, useAuth } from "@/lib/auth";
import type { Role } from "@/lib/types";
import { Button } from "./ui";

const NAV: { href: string; label: string; roles: Role[] }[] = [
  { href: "/staff", label: "Checking", roles: CHECKING_ROLES },
  { href: "/dashboard", label: "Dashboard", roles: MANAGEMENT_ROLES },
  { href: "/today", label: "Day status", roles: MANAGEMENT_ROLES },
  { href: "/unreported", label: "Unreported", roles: ADMIN_ROLES },
  { href: "/teacher", label: "My classes", roles: ["TEACHER"] },
  { href: "/approvals", label: "Approvals", roles: ADMIN_ROLES },
  { href: "/reports", label: "Reports", roles: ["TEACHER", ...ADMIN_ROLES] },
  { href: "/admin", label: "Admin", roles: MANAGEMENT_ROLES },
];

function Bell() {
  const [count, setCount] = useState(0);
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<
    { id: number; title: string; body: string; link: string | null }[]
  >([]);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const rows = await api.notifications(true);
        if (alive) {
          setCount(rows.length);
          setItems(rows.slice(0, 8));
        }
      } catch {
        /* not signed in yet, or offline -- the bell is not worth an error */
      }
    };
    void load();
    const timer = setInterval(load, 60_000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="relative rounded-lg p-2.5 text-ink-soft hover:bg-canvas"
        aria-label={`Notifications (${count} unread)`}
      >
        <svg width="24" height="24" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
          <path d="M10 2a5 5 0 0 0-5 5v3.6l-1.4 2.3A1 1 0 0 0 4.5 14.5h11a1 1 0 0 0 .9-1.6L15 10.6V7a5 5 0 0 0-5-5Zm0 15a2.5 2.5 0 0 0 2.4-1.8H7.6A2.5 2.5 0 0 0 10 17Z" />
        </svg>
        {count > 0 ? (
          <span className="absolute -right-0.5 -top-0.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-bad px-1 text-xs font-bold text-white">
            {count > 9 ? "9+" : count}
          </span>
        ) : null}
      </button>

      {open ? (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          {/* Pinned to the viewport on a phone, where a dropdown anchored to the
              bell would run off the left edge. */}
          <div className="fixed inset-x-3 top-16 z-20 overflow-hidden rounded-2xl border border-line bg-surface shadow-xl sm:absolute sm:inset-x-auto sm:right-0 sm:top-full sm:mt-2 sm:w-[28rem]">
            <div className="flex items-center justify-between border-b border-line px-4 py-3">
              <span className="text-lg font-bold">Notifications</span>
              {count > 0 ? (
                <button
                  className="rounded-lg px-2 py-1 text-base font-semibold text-brand hover:bg-brand-soft"
                  onClick={async () => {
                    await api.markAllRead();
                    setCount(0);
                    setItems([]);
                  }}
                >
                  Mark all read
                </button>
              ) : null}
            </div>
            {items.length === 0 ? (
              <p className="px-4 py-8 text-center text-base text-ink-faint">
                Nothing new.
              </p>
            ) : (
              <ul className="max-h-[70vh] divide-y divide-line overflow-y-auto">
                {items.map((n) => (
                  <li key={n.id}>
                    <Link
                      href={n.link ?? "#"}
                      onClick={() => setOpen(false)}
                      className="block px-4 py-3.5 hover:bg-canvas"
                    >
                      <p className="text-base font-semibold text-ink">{n.title}</p>
                      <p className="mt-1 text-sm leading-relaxed text-ink-soft">
                        {n.body}
                      </p>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}

export default function Shell({ children }: { children: React.ReactNode }) {
  const { user, signOut } = useAuth();
  const pathname = usePathname();

  // On a phone the menu scrolls sideways; keep the current page's tab in view.
  useEffect(() => {
    document
      .querySelector('header nav [aria-current="page"]')
      ?.scrollIntoView({ block: "nearest", inline: "center" });
  }, [pathname, user]);

  if (!user) return <>{children}</>;

  const links = NAV.filter((n) => n.roles.includes(user.role));

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-30 border-b border-line bg-surface/95 backdrop-blur">
        {/* On a phone the menu gets its own full-width row: squeezed between the
            logo and the bell, its labels were cut off mid-word. */}
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-3 gap-y-2 px-4 py-2.5">
          <Link href="/" className="flex shrink-0 items-center gap-2.5 font-semibold">
            <Image
              src="/diu-logo.png"
              alt="Daffodil International University"
              width={756}
              height={289}
              className="h-8 w-auto"
              preload
            />
            <span className="hidden border-l border-line pl-2.5 sm:inline">ClassTrack</span>
          </Link>

          <nav className="order-last -mx-1 flex w-full items-center gap-1 overflow-x-auto md:order-none md:mx-0 md:w-auto md:flex-1 md:gap-0.5">
            {links.map((link) => {
              const active =
                pathname === link.href || pathname.startsWith(`${link.href}/`);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  aria-current={active ? "page" : undefined}
                  className={`whitespace-nowrap rounded-lg px-3 py-2 text-base font-medium transition-colors md:py-1.5 md:text-sm ${
                    active
                      ? "bg-brand-soft text-brand"
                      : "text-ink-soft hover:bg-canvas hover:text-ink"
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
          </nav>

          <div className="ml-auto md:ml-0">
            <Bell />
          </div>

          <div className="flex items-center gap-2">
            <div className="hidden text-right sm:block">
              <div className="text-sm font-medium leading-tight">{user.full_name}</div>
              <div className="text-xs leading-tight text-ink-faint">
                {ROLE_LABELS[user.role]}
                {user.teacher_initial ? ` · ${user.teacher_initial}` : ""}
              </div>
            </div>
            <Button variant="ghost" onClick={signOut} aria-label="Sign out">
              Sign out
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">{children}</main>

      <footer className="border-t border-line">
        <p className="mx-auto max-w-7xl px-4 py-4 text-center text-xs text-ink-faint">
          Developed by Shakib Howlader ·{" "}
          <a
            href="https://shakibhowlader.online"
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-ink-soft hover:text-brand hover:underline"
          >
            shakibhowlader.online
          </a>
        </p>
      </footer>
    </div>
  );
}
