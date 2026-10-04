"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, Card, EmptyState, ErrorNote, Spinner, inputClass } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { MANAGEMENT_ROLES, useRequireRole } from "@/lib/auth";
import type { TeacherAccount } from "@/lib/types";

type Filter = "all" | "without" | "with";

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "without", label: "No account" },
  { key: "with", label: "Has account" },
];

export default function TeachersPage() {
  const { permitted, loading: authLoading } = useRequireRole(MANAGEMENT_ROLES);
  const [rows, setRows] = useState<TeacherAccount[]>([]);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setRows(await api.teachers());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the faculty list.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (permitted) void load();
  }, [permitted, load]);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter(
      (t) =>
        (filter === "all" || (filter === "with") === t.has_account) &&
        (!q || t.initial.toLowerCase().includes(q) || t.name.toLowerCase().includes(q)),
    );
  }, [rows, query, filter]);

  if (authLoading || !permitted) return <Spinner />;
  if (loading) return <Spinner label="Loading faculty…" />;

  const withAccount = rows.filter((t) => t.has_account).length;

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <h2 className="text-sm font-semibold">Teacher accounts</h2>
        <p className="mt-1 text-sm text-ink-soft">
          Give a teacher a password and they sign in with their initial. Their
          account shows their own classes, alerts when staff report one, and lets
          them request a reschedule.
        </p>
        <p className="mt-2 text-xs text-ink-faint">
          {withAccount} of {rows.length} teachers have an account.
        </p>
        <CreateAllAccounts missing={rows.length - withAccount} onCreated={load} />
      </Card>

      {error ? <ErrorNote message={error} /> : null}

      <div className="flex flex-wrap items-center gap-2">
        <input
          className={`${inputClass} max-w-xs`}
          placeholder="Search by initial or name"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className="flex gap-1">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              onClick={() => setFilter(f.key)}
              className={`min-h-9 rounded-lg px-2.5 py-1.5 text-sm font-medium ring-1 ring-inset transition-colors ${
                filter === f.key
                  ? "bg-brand-soft text-brand ring-brand/30"
                  : "bg-surface text-ink-soft ring-line hover:bg-canvas"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <Card>
        {shown.length === 0 ? (
          <EmptyState title="No teachers match" />
        ) : (
          <ul className="divide-y divide-line">
            {shown.map((t) => (
              <TeacherRow key={t.initial} teacher={t} onChanged={load} />
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

/** One step for the whole faculty: every teacher without an account gets one,
 *  all on the same default password. Existing accounts are left alone. */
function CreateAllAccounts({
  missing,
  onCreated,
}: {
  missing: number;
  onCreated: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { created } = await api.createAllTeacherAccounts(password);
      setNotice(
        `${created} account${created === 1 ? "" : "s"} created. Each teacher signs in with their initial and the default password.`,
      );
      setPassword("");
      setOpen(false);
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the accounts.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-3">
      {open ? (
        <form onSubmit={submit} className="flex flex-wrap items-center gap-2 rounded-lg bg-canvas p-2.5">
          <span className="text-sm text-ink-soft">
            Default password for {missing} teacher{missing === 1 ? "" : "s"}
          </span>
          <input
            type="text"
            className={`${inputClass} max-w-52`}
            placeholder="Default password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={6}
            required
            autoFocus
          />
          <Button type="submit" disabled={busy || password.length < 6}>
            {busy ? "Creating…" : `Create ${missing} account${missing === 1 ? "" : "s"}`}
          </Button>
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              setOpen(false);
              setPassword("");
              setError(null);
            }}
          >
            Cancel
          </Button>
          <span className="w-full text-xs text-ink-faint">
            At least 6 characters. Teachers who already have an account keep their password.
          </span>
        </form>
      ) : missing > 0 ? (
        <Button
          variant="secondary"
          onClick={() => {
            setOpen(true);
            setNotice(null);
          }}
        >
          Create all {missing} missing account{missing === 1 ? "" : "s"}
        </Button>
      ) : null}
      {error ? <p className="mt-2 text-xs text-bad">{error}</p> : null}
      {notice ? <p className="mt-2 text-xs text-ok">{notice}</p> : null}
    </div>
  );
}

function TeacherRow({
  teacher,
  onChanged,
}: {
  teacher: TeacherAccount;
  onChanged: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (teacher.has_account) {
        await api.resetTeacherPassword(teacher.initial, password);
        setNotice("Password updated.");
      } else {
        await api.createTeacherAccount(teacher.initial, password);
        setNotice(`Account created — ${teacher.initial} can sign in now.`);
        onChanged();
      }
      setPassword("");
      setOpen(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className="px-4 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <code className="w-16 shrink-0 text-sm font-semibold text-ink">{teacher.initial}</code>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{teacher.name}</p>
          {teacher.designation ? (
            <p className="truncate text-xs text-ink-faint">{teacher.designation}</p>
          ) : null}
        </div>
        {teacher.has_account ? (
          <span className="rounded-full bg-ok-soft px-2.5 py-1 text-xs font-semibold text-ok ring-1 ring-inset ring-ok/20">
            {teacher.account_active === false ? "disabled" : "has account"}
          </span>
        ) : null}
        {!open ? (
          <Button
            variant={teacher.has_account ? "ghost" : "secondary"}
            onClick={() => {
              setOpen(true);
              setNotice(null);
            }}
          >
            {teacher.has_account ? "Reset password" : "Create account"}
          </Button>
        ) : null}
      </div>

      {open ? (
        <form onSubmit={submit} className="mt-2.5 flex flex-wrap items-center gap-2 rounded-lg bg-canvas p-2.5">
          <span className="text-sm text-ink-soft">
            Sign-in: <code className="font-semibold text-ink">{teacher.initial}</code>
          </span>
          <input
            type="text"
            className={`${inputClass} max-w-52`}
            placeholder={teacher.has_account ? "New password" : "Password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={6}
            required
            autoFocus
          />
          <Button type="submit" disabled={busy || password.length < 6}>
            {busy ? "Saving…" : teacher.has_account ? "Update" : "Create"}
          </Button>
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              setOpen(false);
              setPassword("");
              setError(null);
            }}
          >
            Cancel
          </Button>
          <span className="w-full text-xs text-ink-faint">At least 6 characters.</span>
        </form>
      ) : null}

      {error ? <p className="mt-2 text-xs text-bad">{error}</p> : null}
      {notice ? <p className="mt-2 text-xs text-ok">{notice}</p> : null}
    </li>
  );
}
