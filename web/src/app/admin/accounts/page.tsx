"use client";

import { useCallback, useEffect, useState } from "react";
import { Button, Card, EmptyState, ErrorNote, Field, Spinner, inputClass } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { ADMIN_ROLES, ROLE_LABELS, useRequireRole } from "@/lib/auth";
import type { Account, Role } from "@/lib/types";

/** Roles created here. Teachers and office staff have their own tabs, which
 *  also bind the initial or the floors their account needs. */
const CREATABLE: Role[] = ["HOD", "ASSOCIATE_HEAD", "COORDINATION_OFFICER", "COMMITTEE"];

const ACCESS: Partial<Record<Role, string>> = {
  HOD: "Everything: reports, approvals, accounts, routine.",
  ASSOCIATE_HEAD: "Everything, the same as the Head.",
  COORDINATION_OFFICER:
    "Dashboard, day status, checking and correcting past classes, routine and calendar. No reports; cannot decide reschedule requests.",
  COMMITTEE: "Reports classes and corrects past ones. Nothing else.",
  STAFF: "Checks classes on the checking screen.",
  TEACHER: "Their own classes, reports and reschedules.",
  SUPER_ADMIN: "Everything. Kept as a fallback login.",
};

export default function AccountsPage() {
  const { user, permitted, loading: authLoading } = useRequireRole(ADMIN_ROLES);
  const [rows, setRows] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Role | "">("");

  const load = useCallback(async () => {
    try {
      setRows(await api.users());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load accounts.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (permitted) void load();
  }, [permitted, load]);

  if (authLoading || !permitted) return <Spinner />;

  const shown = filter ? rows.filter((r) => r.role === filter) : rows.filter((r) => r.role !== "TEACHER");

  return (
    <div className="space-y-4">
      <CreateAccount onCreated={load} />

      {error ? <ErrorNote message={error} /> : null}

      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
          <h2 className="text-sm font-semibold">Accounts</h2>
          <select
            className={`${inputClass} ml-auto w-auto`}
            value={filter}
            onChange={(e) => setFilter(e.target.value as Role | "")}
          >
            <option value="">All but teachers</option>
            {(Object.keys(ROLE_LABELS) as Role[]).map((r) => (
              <option key={r} value={r}>
                {ROLE_LABELS[r]}
              </option>
            ))}
          </select>
        </div>
        {loading ? (
          <Spinner />
        ) : shown.length === 0 ? (
          <EmptyState title="No accounts" />
        ) : (
          <ul className="divide-y divide-line">
            {shown.map((a) => (
              <AccountRow key={a.id} account={a} self={a.id === user?.id} onChanged={load} />
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

function CreateAccount({ onCreated }: { onCreated: () => void }) {
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    role: "COORDINATION_OFFICER" as Role,
    password: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const created = await api.createUser(form);
      setNotice(`${created.full_name} can now sign in as ${created.email}.`);
      setForm({ ...form, full_name: "", email: "", password: "" });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the account.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="p-4">
      <h2 className="text-sm font-semibold">New account</h2>
      <p className="mt-1 text-sm text-ink-soft">
        Teachers get their sign-in from the Teachers tab, office staff from Staff coverage.
      </p>
      <form onSubmit={submit} className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Full name">
          <input
            required
            className={inputClass}
            value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
          />
        </Field>
        <Field label="Email">
          <input
            required
            type="email"
            className={inputClass}
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
          />
        </Field>
        <Field label="Role" hint={ACCESS[form.role]}>
          <select
            className={inputClass}
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value as Role })}
          >
            {CREATABLE.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABELS[r]}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Password" hint="At least 6 characters.">
          <input
            required
            minLength={6}
            type="password"
            autoComplete="new-password"
            className={inputClass}
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
        </Field>
        <div className="flex items-center gap-3 sm:col-span-2 lg:col-span-4">
          <Button type="submit" disabled={busy}>
            {busy ? "Creating…" : "Create account"}
          </Button>
          {notice ? <span className="text-sm text-ok">{notice}</span> : null}
        </div>
        {error ? (
          <div className="sm:col-span-2 lg:col-span-4">
            <ErrorNote message={error} />
          </div>
        ) : null}
      </form>
    </Card>
  );
}

function AccountRow({
  account: a,
  self,
  onChanged,
}: {
  account: Account;
  self: boolean;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);
  const [password, setPassword] = useState("");

  const update = async (payload: Parameters<typeof api.updateUser>[1]) => {
    setBusy(true);
    setError(null);
    try {
      await api.updateUser(a.id, payload);
      setResetting(false);
      setPassword("");
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  };

  // Teachers and staff keep their role: each is bound to an initial or floors.
  const fixedRole = a.role === "TEACHER" || a.role === "STAFF";

  return (
    <li className={`px-4 py-3 ${a.is_active ? "" : "opacity-60"}`}>
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-48 flex-1">
          <p className="font-medium">
            {a.full_name}
            {self ? <span className="ml-1.5 text-xs text-ink-faint">(you)</span> : null}
            {!a.is_active ? (
              <span className="ml-1.5 rounded bg-canvas px-1.5 py-0.5 text-xs text-ink-faint">
                deactivated
              </span>
            ) : null}
          </p>
          <p className="text-sm text-ink-faint">
            {a.email}
            {a.teacher_initial ? ` · ${a.teacher_initial}` : ""}
          </p>
        </div>
        {fixedRole || self ? (
          <span className="rounded-lg bg-canvas px-2.5 py-1 text-sm text-ink-soft">
            {ROLE_LABELS[a.role]}
          </span>
        ) : (
          <select
            className={`${inputClass} w-auto`}
            value={a.role}
            disabled={busy}
            onChange={(e) => update({ role: e.target.value as Role })}
          >
            {[...CREATABLE, ...(CREATABLE.includes(a.role) ? [] : [a.role])].map((r) => (
              <option key={r} value={r}>
                {ROLE_LABELS[r]}
              </option>
            ))}
          </select>
        )}
        <Button variant="ghost" disabled={busy} onClick={() => setResetting((v) => !v)}>
          Reset password
        </Button>
        {!self ? (
          <Button
            variant={a.is_active ? "secondary" : "primary"}
            disabled={busy}
            onClick={() => update({ is_active: !a.is_active })}
          >
            {a.is_active ? "Deactivate" : "Reactivate"}
          </Button>
        ) : null}
      </div>
      {resetting ? (
        <form
          className="mt-2 flex flex-wrap gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            void update({ password });
          }}
        >
          <input
            type="password"
            minLength={6}
            required
            autoComplete="new-password"
            placeholder="New password"
            className={`${inputClass} w-56`}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <Button type="submit" disabled={busy}>
            Save password
          </Button>
        </form>
      ) : null}
      {error ? <p className="mt-2 text-sm text-bad">{error}</p> : null}
    </li>
  );
}
