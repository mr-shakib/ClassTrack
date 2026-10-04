"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ADMIN_TABS, useAuth } from "@/lib/auth";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user } = useAuth();
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Administration</h1>
      <div className="flex gap-1 overflow-x-auto border-b border-line">
        {ADMIN_TABS.filter((t) => user != null && t.may(user)).map((t) => (
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
