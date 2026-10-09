"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { RolePicker } from "@/components/RolePicker";
import { Button, Card, EmptyState, ErrorNote, Field, Spinner, inputClass } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { adminTab, useRequireAccess } from "@/lib/auth";
import type { Account, RoleInfo, User } from "@/lib/types";

export default function AccountsPage() {
  const { user, permitted, loading: authLoading } = useRequireAccess(adminTab("/admin/accounts"));
  const [rows, setRows] = useState<Account[]>([]);
  const [roles, setRoles] = useState<RoleInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // "": everyone but teachers, "all", or a role id.
  const [filter, setFilter] = useState("");

  const load = useCallback(async () => {
    try {
      const [users, allRoles] = await Promise.all([api.users(), api.roles()]);
      setRows(users);
      setRoles(allRoles);
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

  if (authLoading || !permitted || !user) return <Spinner />;

  const shown =
    filter === "all"
      ? rows
      : filter
        ? rows.filter((r) => r.roles.some((x) => String(x.id) === filter))
        : rows.filter((r) => !r.teacher_initial);

  return (
    <div className="space-y-4">
      <CreateAccount me={user} roles={roles} onCreated={load} />

      {error ? <ErrorNote message={error} /> : null}

      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
          <h2 className="text-sm font-semibold">Accounts</h2>
          <select
            className={`${inputClass} ml-auto w-auto`}
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            aria-label="Show"
          >
            <option value="">All but teachers</option>
            <option value="all">Everyone</option>
            {roles.map((r) => (
              <option key={r.id} value={String(r.id)}>
                {r.name}
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
              <AccountRow
                key={a.id}
                account={a}
                me={user}
                roles={roles}
                self={a.id === user.id}
                onChanged={load}
              />
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

function CreateAccount({
  me,
  roles,
  onCreated,
}: {
  me: User;
  roles: RoleInfo[];
  onCreated: () => void;
}) {
  const [form, setForm] = useState({ full_name: "", email: "", password: "" });
  const [roleIds, setRoleIds] = useState<number[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const created = await api.createUser({ ...form, role_ids: roleIds });
      setNotice(`${created.full_name} can now sign in as ${created.email}.`);
      setForm({ full_name: "", email: "", password: "" });
      setRoleIds([]);
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
        Teachers get their sign-in from the Teachers tab, which links their initial. Give a
        staff role here and assign floors in Staff coverage.{" "}
        <Link href="/admin/roles" className="font-medium text-brand hover:underline">
          What each role can do
        </Link>
      </p>
      <form onSubmit={submit} className="mt-3 space-y-3">
        <div className="grid gap-3 sm:grid-cols-3">
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
        </div>
        <div>
          <p className="mb-1.5 text-sm font-medium text-ink-soft">
            Roles <span className="font-normal text-ink-faint">— one or more</span>
          </p>
          <RolePicker
            me={me}
            roles={roles}
            selected={roleIds}
            onChange={setRoleIds}
            teacherAccount={false}
          />
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={busy || roleIds.length === 0}>
            {busy ? "Creating…" : "Create account"}
          </Button>
          {roleIds.length === 0 ? (
            <span className="text-sm text-ink-faint">Pick at least one role.</span>
          ) : null}
          {notice ? <span className="text-sm text-ok">{notice}</span> : null}
        </div>
        {error ? <ErrorNote message={error} /> : null}
      </form>
    </Card>
  );
}

function AccountRow({
  account: a,
  me,
  roles,
  self,
  onChanged,
}: {
  account: Account;
  me: User;
  roles: RoleInfo[];
  self: boolean;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);
  const [password, setPassword] = useState("");
  const [editing, setEditing] = useState(false);
  const [roleIds, setRoleIds] = useState<number[]>(a.roles.map((r) => r.id));

  const update = async (payload: Parameters<typeof api.updateUser>[1]) => {
    setBusy(true);
    setError(null);
    try {
      await api.updateUser(a.id, payload);
      setResetting(false);
      setEditing(false);
      setPassword("");
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  };

  const unchanged =
    roleIds.length === a.roles.length && a.roles.every((r) => roleIds.includes(r.id));

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
        <div className="flex flex-wrap gap-1.5">
          {a.roles.map((r) => (
            <span key={r.id} className="rounded-lg bg-canvas px-2.5 py-1 text-sm text-ink-soft">
              {r.name}
            </span>
          ))}
        </div>
        {!self ? (
          <Button
            variant="ghost"
            disabled={busy}
            onClick={() => {
              setRoleIds(a.roles.map((r) => r.id));
              setEditing((v) => !v);
            }}
          >
            Change roles
          </Button>
        ) : null}
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
      {editing ? (
        <div className="mt-3 space-y-2 rounded-xl bg-canvas p-3">
          <RolePicker
            me={me}
            roles={roles}
            selected={roleIds}
            onChange={setRoleIds}
            teacherAccount={!!a.teacher_initial}
          />
          <div className="flex flex-wrap items-center gap-2">
            <Button
              disabled={busy || unchanged || roleIds.length === 0}
              onClick={() => update({ role_ids: roleIds })}
            >
              Save roles
            </Button>
            <Button variant="ghost" onClick={() => setEditing(false)}>
              Cancel
            </Button>
            {roleIds.length === 0 ? (
              <span className="text-sm text-ink-faint">An account keeps at least one role.</span>
            ) : null}
          </div>
        </div>
      ) : null}
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
