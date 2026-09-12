"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Role } from "@/lib/types";
import { Button } from "./ui";

const NAV: { href: string; label: string; roles: Role[] }[] = [
  { href: "/staff", label: "Checking", roles: ["STAFF", "HOD", "SUPER_ADMIN"] },
  { href: "/dashboard", label: "Dashboard", roles: ["HOD", "SUPER_ADMIN"] },
  { href: "/teacher", label: "My classes", roles: ["TEACHER"] },
  { href: "/approvals", label: "Approvals", roles: ["HOD", "SUPER_ADMIN"] },
  { href: "/reports", label: "Reports", roles: ["TEACHER", "HOD", "SUPER_ADMIN"] },
  { href: "/admin", label: "Admin", roles: ["HOD", "SUPER_ADMIN"] },
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
        className="relative rounded-lg p-2 text-ink-soft hover:bg-canvas"
        aria-label={`Notifications (${count} unread)`}
      >
        <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
          <path d="M10 2a5 5 0 0 0-5 5v3.6l-1.4 2.3A1 1 0 0 0 4.5 14.5h11a1 1 0 0 0 .9-1.6L15 10.6V7a5 5 0 0 0-5-5Zm0 15a2.5 2.5 0 0 0 2.4-1.8H7.6A2.5 2.5 0 0 0 10 17Z" />
        </svg>
        {count > 0 ? (
          <span className="absolute -right-0.5 -top-0.5 flex size-4 items-center justify-center rounded-full bg-bad text-[10px] font-bold text-white">
            {count > 9 ? "9+" : count}
          </span>
        ) : null}
      </button>

      {open ? (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 z-20 mt-2 w-80 overflow-hidden rounded-xl border border-line bg-surface shadow-lg">
            <div className="flex items-center justify-between border-b border-line px-3 py-2">
              <span className="text-sm font-semibold">Notifications</span>
              {count > 0 ? (
                <button
                  className="text-xs text-brand hover:underline"
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
              <p className="px-3 py-6 text-center text-sm text-ink-faint">
                Nothing new.
              </p>
            ) : (
              <ul className="max-h-80 divide-y divide-line overflow-y-auto">
                {items.map((n) => (
                  <li key={n.id} className="px-3 py-2.5">
                    <Link
                      href={n.link ?? "#"}
                      onClick={() => setOpen(false)}
                      className="block"
                    >
                      <p className="text-sm font-medium text-ink">{n.title}</p>
                      <p className="mt-0.5 text-xs leading-relaxed text-ink-soft">
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

  if (!user) return <>{children}</>;

  const links = NAV.filter((n) => n.roles.includes(user.role));

  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-30 border-b border-line bg-surface/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-2.5">
          <Link href="/" className="flex items-center gap-2 font-semibold">
            <span className="grid size-7 place-items-center rounded-lg bg-brand text-sm text-white">
              C
            </span>
            <span className="hidden sm:inline">ClassTrack</span>
          </Link>

          <nav className="flex flex-1 items-center gap-0.5 overflow-x-auto">
            {links.map((link) => {
              const active =
                pathname === link.href || pathname.startsWith(`${link.href}/`);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
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

          <Bell />

          <div className="flex items-center gap-2">
            <div className="hidden text-right sm:block">
              <div className="text-sm font-medium leading-tight">{user.full_name}</div>
              <div className="text-xs leading-tight text-ink-faint">
                {user.role.replace("_", " ").toLowerCase()}
                {user.teacher_initial ? ` · ${user.teacher_initial}` : ""}
              </div>
            </div>
            <Button variant="ghost" onClick={signOut} aria-label="Sign out">
              Sign out
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
    </div>
  );
}
