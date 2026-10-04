"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "./api";
import type { Permission, User } from "./types";

interface AuthState {
  user: User | null;
  loading: boolean;
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  user: null,
  loading: true,
  refresh: async () => {},
  signOut: async () => {},
});

/** Whether the user holds any of these permissions. The screens hide what a
 *  user cannot use; the API checks again on every request. */
export function can(user: User | null | undefined, ...permissions: Permission[]): boolean {
  return !!user && permissions.some((p) => user.permissions.includes(p));
}

/** The names of the user's roles, as the header and menus show them. */
export const roleNames = (user: User) => user.roles.map((r) => r.name).join(" · ");

// --- who may open which screen ------------------------------------------------
// Module-level so the gate hooks get the same function on every render.

export const mayCheck = (u: User) => can(u, "checking.submit", "checking.correct");
export const mayWatch = (u: User) => can(u, "dashboard.view");
export const mayReport = (u: User) => can(u, "reports.department");
export const mayDecide = (u: User) => can(u, "reschedules.decide");
export const mayReadReports = (u: User) => u.is_teacher || mayReport(u);
/** My classes: a teacher's own, or any teacher's for someone who reschedules for them. */
export const mayTeach = (u: User) => u.is_teacher || can(u, "reschedules.any_teacher");
export const mayReschedule = (u: User) =>
  (u.is_teacher && can(u, "reschedules.request")) || can(u, "reschedules.any_teacher");
export const mayBookExtra = (u: User) => u.is_teacher && can(u, "extra_classes.book");
export const everyone = () => true;

/** The admin area's tabs, each with what opens it. */
export const ADMIN_TABS: { href: string; label: string; may: (u: User) => boolean }[] = [
  { href: "/admin", label: "Routine", may: (u) => can(u, "routine.manage") },
  { href: "/admin/staff", label: "Staff coverage", may: (u) => can(u, "staff.manage") },
  { href: "/admin/teachers", label: "Teachers", may: (u) => can(u, "teachers.manage") },
  { href: "/admin/accounts", label: "Accounts", may: (u) => can(u, "accounts.manage") },
  { href: "/admin/roles", label: "Roles", may: (u) => can(u, "roles.manage") },
  {
    href: "/admin/semesters",
    label: "Semesters",
    may: (u) => can(u, "semesters.manage", "routine.manage", "calendar.manage"),
  },
  { href: "/admin/calendar", label: "Calendar", may: (u) => can(u, "calendar.manage") },
  { href: "/admin/settings", label: "Rules", may: (u) => can(u, "settings.manage") },
  { href: "/admin/audit", label: "Audit log", may: (u) => can(u, "audit.view") },
];

export const adminTab = (href: string) => ADMIN_TABS.find((t) => t.href === href)!.may;

/** Where a user lands after signing in: the first screen their work starts on. */
export function homeFor(user: User): string {
  if (user.is_teacher) return "/teacher";
  if (mayWatch(user)) return "/dashboard";
  if (mayCheck(user)) return "/staff";
  if (mayReport(user)) return "/reports";
  if (mayDecide(user)) return "/approvals";
  return ADMIN_TABS.find((t) => t.may(user))?.href ?? "/profile";
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const refresh = useCallback(async () => {
    try {
      setUser(await api.me());
    } catch {
      // A 401 here is the normal "not signed in" case, not an error worth showing.
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const signOut = useCallback(async () => {
    await api.logout().catch(() => {});
    setUser(null);
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider value={{ user, loading, refresh, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);

/**
 * Client-side gate. Cosmetic only -- it hides what a user cannot use, and
 * redirects them somewhere sensible. Every endpoint enforces its own
 * permissions server-side, which is the actual security boundary.
 *
 * Pass a module-level function, so it is the same one on every render.
 */
export function useRequireAccess(may: (user: User) => boolean) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
    } else if (!may(user)) {
      router.replace(homeFor(user));
    }
  }, [user, loading, may, router]);

  return { user, loading, permitted: !!user && may(user) };
}
