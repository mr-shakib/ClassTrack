"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ADMIN_ROLES, useAuth } from "@/lib/auth";

const TABS = [
  { href: "/admin", label: "Routine", adminOnly: false },
  { href: "/admin/staff", label: "Staff coverage", adminOnly: false },
  { href: "/admin/teachers", label: "Teachers", adminOnly: false },
  { href: "/admin/accounts", label: "Accounts", adminOnly: true },
  { href: "/admin/semesters", label: "Semesters", adminOnly: false },
  { href: "/admin/calendar", label: "Calendar", adminOnly: false },
  { href: "/admin/settings", label: "Rules", adminOnly: false },
  { href: "/admin/audit", label: "Audit log", adminOnly: false },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user } = useAuth();
  const isAdmin = user != null && ADMIN_ROLES.includes(user.role);
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Administration</h1>
      <div className="flex gap-1 overflow-x-auto border-b border-line">
        {TABS.filter((t) => isAdmin || !t.adminOnly).map((t) => (
          <Link
            key={t.href}
            href={t.href}
            className={`-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
              pathname === t.href
                ? "border-brand text-brand"
                : "border-transparent text-ink-soft hover:text-ink"
            }`}
          >
            {t.label}
          </Link>
        ))}
      </div>
      {children}
    </div>
  );
}
