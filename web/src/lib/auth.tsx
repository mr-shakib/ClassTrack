"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "./api";
import type { Role, User } from "./types";

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

/** Full administration: reports, approvals, accounts. Mirrors ADMIN_ROLES in the API. */
export const ADMIN_ROLES: Role[] = ["HOD", "ASSOCIATE_HEAD", "SUPER_ADMIN"];
/** The live views and admin screens: admins plus the Coordination Officer. */
export const MANAGEMENT_ROLES: Role[] = [...ADMIN_ROLES, "COORDINATION_OFFICER"];
/** Roles that may correct a check after its day is over. */
export const OVERRIDE_ROLES: Role[] = [...MANAGEMENT_ROLES, "COMMITTEE"];
/** How each role is named on screen. */
export const ROLE_LABELS: Record<Role, string> = {
  SUPER_ADMIN: "Super admin",
  HOD: "Head of Department",
  ASSOCIATE_HEAD: "Associate Head",
  COORDINATION_OFFICER: "Coordination Officer",
  COMMITTEE: "Committee member",
  STAFF: "Office staff",
  TEACHER: "Teacher",
};

/** Roles that may open the checking screen. */
export const CHECKING_ROLES: Role[] = ["STAFF", ...OVERRIDE_ROLES];

/** Where each role lands after signing in. */
export const HOME_FOR: Record<Role, string> = {
  STAFF: "/staff",
  TEACHER: "/teacher",
  COMMITTEE: "/staff",
  COORDINATION_OFFICER: "/dashboard",
  HOD: "/dashboard",
  ASSOCIATE_HEAD: "/dashboard",
  SUPER_ADMIN: "/dashboard",
};

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
 * Client-side role gate. Cosmetic only -- it hides what a user cannot use, and
 * redirects them somewhere sensible. Every endpoint enforces its own roles
 * server-side, which is the actual security boundary.
 */
export function useRequireRole(allowed: Role[]) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
    } else if (!allowed.includes(user.role)) {
      router.replace(HOME_FOR[user.role]);
    }
  }, [user, loading, allowed, router]);

  return { user, loading, permitted: !!user && allowed.includes(user.role) };
}
