"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { RolePicker } from "@/components/RolePicker";
import { Button, Card, EmptyState, ErrorNote, Field, Spinner, inputClass } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { adminTab, can, useRequireAccess } from "@/lib/auth";
import type { RoleInfo, TeacherAccount, TeacherDetails, User } from "@/lib/types";

type Filter = "all" | "without" | "with";

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "without", label: "No account" },
  { key: "with", label: "Has account" },
];

/** A teacher's details as the form holds them: every field a string, blank for none. */
type Draft = Record<keyof TeacherDetails, string>;

const BLANK: Draft = {
  initial: "",
  name: "",
  designation: "",
  email: "",
  office_room: "",
  photo_url: "",
};

const toDraft = (t: TeacherDetails): Draft => ({
  initial: t.initial,
  name: t.name,
  designation: t.designation ?? "",
  email: t.email ?? "",
  office_room: t.office_room ?? "",
  photo_url: t.photo_url ?? "",
});

const fromDraft = (d: Draft): TeacherDetails => ({
  initial: d.initial.trim().toUpperCase(),
  name: d.name.trim(),
  designation: d.designation.trim() || null,
  email: d.email.trim() || null,
  office_room: d.office_room.trim() || null,
  photo_url: d.photo_url.trim() || null,
});

/** What a new teacher account starts with: the built-in Teacher role. */
const startingRoles = (roles: RoleInfo[]) =>
  roles.filter((r) => r.key === "TEACHER").map((r) => r.id);

/** The API refuses a teacher account without a teacher role. */
const keepsTeacherRole = (roles: RoleInfo[], ids: number[]) =>
  roles.some((r) => r.kind === "TEACHER" && ids.includes(r.id));

export default function TeachersPage() {
  const { user, permitted, loading: authLoading } = useRequireAccess(adminTab("/admin/teachers"));
  const [rows, setRows] = useState<TeacherAccount[]>([]);
  const [roles, setRoles] = useState<RoleInfo[]>([]);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [adding, setAdding] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Giving roles is managing accounts; without that, a new account gets the Teacher role.
  const givesRoles = can(user, "accounts.manage");

  const load = useCallback(async () => {
    try {
      const [teachers, allRoles] = await Promise.all([
        api.teachers(),
        givesRoles ? api.roles() : Promise.resolve([]),
      ]);
      setRows(teachers);
      setRoles(allRoles);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the faculty list.");
    } finally {
      setLoading(false);
    }
  }, [givesRoles]);

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

  if (authLoading || !permitted || !user) return <Spinner />;
  if (loading) return <Spinner label="Loading faculty…" />;

  const withAccount = rows.filter((t) => t.has_account).length;

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="flex flex-wrap items-start gap-3">
          <div className="min-w-0 flex-1">
            <h2 className="text-sm font-semibold">Teachers</h2>
            <p className="mt-1 text-sm text-ink-soft">
              Add a teacher the faculty list does not have yet, or correct one who is on it.
              Give a teacher a password and they sign in with their initial. Their account
              shows their own classes, alerts when staff report one, and lets them request a
              reschedule.
            </p>
            <p className="mt-2 text-xs text-ink-faint">
              {withAccount} of {rows.length} teachers have an account.
            </p>
          </div>
          {!adding ? (
            <Button
              onClick={() => {
                setAdding(true);
                setNotice(null);
              }}
            >
              Add teacher
            </Button>
          ) : null}
        </div>
        <CreateAllAccounts missing={rows.length - withAccount} onCreated={load} />
        {notice ? <p className="mt-2 text-sm text-ok">{notice}</p> : null}
      </Card>

      {adding ? (
        <AddTeacher
          me={user}
          roles={roles}
          givesRoles={givesRoles}
          onCancel={() => setAdding(false)}
          onAdded={(message) => {
            setAdding(false);
            setNotice(message);
            void load();
          }}
        />
      ) : null}

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
              <TeacherRow
                key={t.id}
                teacher={t}
                me={user}
                roles={roles}
                givesRoles={givesRoles}
                onChanged={load}
              />
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

/** The details an admin keeps on a teacher, for adding one or correcting one. */
function DetailFields({
  draft,
  onChange,
  initialHint,
}: {
  draft: Draft;
  onChange: (draft: Draft) => void;
  initialHint: string;
}) {
  const bind = (key: keyof Draft) => ({
    value: draft[key],
    onChange: (e: React.ChangeEvent<HTMLInputElement>) =>
      onChange({ ...draft, [key]: e.target.value }),
  });
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <Field label="Initial" hint={initialHint}>
        <input
          required
          maxLength={9}
          autoCapitalize="characters"
          spellCheck={false}
          className={`${inputClass} font-mono uppercase`}
          placeholder="e.g. SRH"
          {...bind("initial")}
        />
      </Field>
      <Field label="Full name">
        <input required minLength={2} className={inputClass} {...bind("name")} />
      </Field>
      <Field label="Designation">
        <input className={inputClass} placeholder="e.g. Lecturer" {...bind("designation")} />
      </Field>
      <Field label="Email" hint="Where absence reports are mailed.">
        <input type="email" className={inputClass} {...bind("email")} />
      </Field>
      <Field label="Office room">
        <input className={inputClass} placeholder="e.g. KT-702B" {...bind("office_room")} />
      </Field>
      <Field label="Photo URL">
        <input type="url" className={inputClass} placeholder="https://…" {...bind("photo_url")} />
      </Field>
    </div>
  );
}

/** The roles a new teacher account gets. Choosing them takes managing
 *  accounts; without that, they get the Teacher role. */
function RoleChoice({
  me,
  roles,
  givesRoles,
  selected,
  onChange,
}: {
  me: User;
  roles: RoleInfo[];
  givesRoles: boolean;
  selected: number[];
  onChange: (ids: number[]) => void;
}) {
  if (!givesRoles) {
    return (
      <p className="text-xs text-ink-faint">
        They get the Teacher role. Giving any other takes the Manage accounts permission.
      </p>
    );
  }
  return (
    <div>
      <p className="mb-1.5 text-sm font-medium text-ink-soft">
        Roles{" "}
        <span className="font-normal text-ink-faint">— a teacher role, and any other they hold</span>
      </p>
      <RolePicker me={me} roles={roles} selected={selected} onChange={onChange} teacherAccount />
      {!keepsTeacherRole(roles, selected) ? (
        <p className="mt-1.5 text-xs text-bad">A teacher&apos;s account keeps at least one teacher role.</p>
      ) : null}
    </div>
  );
}

function AddTeacher({
  me,
  roles,
  givesRoles,
  onAdded,
  onCancel,
}: {
  me: User;
  roles: RoleInfo[];
  givesRoles: boolean;
  onAdded: (message: string) => void;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState<Draft>(BLANK);
  const [withAccount, setWithAccount] = useState(true);
  const [password, setPassword] = useState("");
  const [roleIds, setRoleIds] = useState(() => startingRoles(roles));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ready =
    !withAccount ||
    (password.length >= 6 && (!givesRoles || keepsTeacherRole(roles, roleIds)));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const added = await api.addTeacher({
        ...fromDraft(draft),
        ...(withAccount ? { password, role_ids: givesRoles ? roleIds : undefined } : {}),
      });
      onAdded(
        added.has_account
          ? `${added.name} added. They sign in with ${added.initial}.`
          : `${added.name} added to the faculty list.`,
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not add the teacher.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="p-4">
      <h2 className="text-sm font-semibold">Add a teacher</h2>
      <form onSubmit={submit} className="mt-3 space-y-4">
        <DetailFields
          draft={draft}
          onChange={setDraft}
          initialHint="As the routine writes it. They sign in with it."
        />
        <div className="space-y-3 rounded-xl bg-canvas p-3">
          <label className="flex items-center gap-2 text-sm font-medium">
            <input
              type="checkbox"
              className="size-4 accent-brand"
              checked={withAccount}
              onChange={(e) => setWithAccount(e.target.checked)}
            />
            Give them an account now
          </label>
          {withAccount ? (
            <>
              <Field label="Password" hint="At least 6 characters.">
                <input
                  type="text"
                  required
                  minLength={6}
                  className={`${inputClass} max-w-xs`}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </Field>
              <RoleChoice
                me={me}
                roles={roles}
                givesRoles={givesRoles}
                selected={roleIds}
                onChange={setRoleIds}
              />
            </>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button type="submit" disabled={busy || !ready}>
            {busy ? "Adding…" : "Add teacher"}
          </Button>
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        </div>
        {error ? <ErrorNote message={error} /> : null}
      </form>
    </Card>
  );
}

type Panel = "edit" | "roles" | "account" | "password";

function TeacherRow({
  teacher: t,
  me,
  roles,
  givesRoles,
  onChanged,
}: {
  teacher: TeacherAccount;
  me: User;
  roles: RoleInfo[];
  givesRoles: boolean;
  onChanged: () => void;
}) {
  const [panel, setPanel] = useState<Panel | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const open = (p: Panel) => {
    setPanel(p);
    setNotice(null);
  };
  const close = () => setPanel(null);
  const saved = (message: string) => {
    setPanel(null);
    setNotice(message);
    onChanged();
  };

  // Nobody changes their own roles; the API refuses it too.
  const mayChangeRoles = givesRoles && t.account_id !== null && t.account_id !== me.id;
  const details = [t.designation, t.office_room].filter(Boolean).join(" · ");

  return (
    <li className="px-4 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <code className="w-16 shrink-0 text-sm font-semibold text-ink">{t.initial}</code>
        <div className="min-w-40 flex-1">
          <p className="truncate text-sm font-medium">{t.name}</p>
          {details ? <p className="truncate text-xs text-ink-faint">{details}</p> : null}
        </div>
        {t.has_account ? (
          <div className="flex flex-wrap gap-1.5">
            {t.account_active === false ? (
              <span className="rounded-full bg-canvas px-2.5 py-1 text-xs font-semibold text-ink-faint ring-1 ring-inset ring-line">
                disabled
              </span>
            ) : null}
            {t.roles.map((r) => (
              <span
                key={r.id}
                className="rounded-full bg-ok-soft px-2.5 py-1 text-xs font-semibold text-ok ring-1 ring-inset ring-ok/20"
              >
                {r.name}
              </span>
            ))}
          </div>
        ) : null}
        {panel === null ? (
          <div className="flex flex-wrap gap-1">
            <Button variant="ghost" onClick={() => open("edit")}>
              Edit
            </Button>
            {mayChangeRoles ? (
              <Button variant="ghost" onClick={() => open("roles")}>
                Roles
              </Button>
            ) : null}
            {t.has_account ? (
              <Button variant="ghost" onClick={() => open("password")}>
                Reset password
              </Button>
            ) : (
              <Button variant="secondary" onClick={() => open("account")}>
                Create account
              </Button>
            )}
          </div>
        ) : null}
      </div>

      {panel === "edit" ? <EditDetails teacher={t} onSaved={saved} onCancel={close} /> : null}
      {panel === "roles" ? (
        <ChangeRoles teacher={t} me={me} roles={roles} onSaved={saved} onCancel={close} />
      ) : null}
      {panel === "account" || panel === "password" ? (
        <SignIn
          teacher={t}
          me={me}
          roles={roles}
          givesRoles={givesRoles}
          onSaved={saved}
          onCancel={close}
        />
      ) : null}

      {notice ? <p className="mt-2 text-xs text-ok">{notice}</p> : null}
    </li>
  );
}

function EditDetails({
  teacher,
  onSaved,
  onCancel,
}: {
  teacher: TeacherAccount;
  onSaved: (message: string) => void;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState(() => toDraft(teacher));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const saved = await api.updateTeacher(teacher.initial, fromDraft(draft));
      onSaved(
        saved.initial === teacher.initial
          ? "Saved."
          : `Saved. Their initial is now ${saved.initial}${saved.has_account ? ", and they sign in with it" : ""}.`,
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="mt-2.5 space-y-3 rounded-lg bg-canvas p-3">
      <DetailFields
        draft={draft}
        onChange={setDraft}
        initialHint="Can change only while the routine has no classes under it."
      />
      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" disabled={busy}>
          {busy ? "Saving…" : "Save"}
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
      {error ? <ErrorNote message={error} /> : null}
    </form>
  );
}

function ChangeRoles({
  teacher,
  me,
  roles,
  onSaved,
  onCancel,
}: {
  teacher: TeacherAccount;
  me: User;
  roles: RoleInfo[];
  onSaved: (message: string) => void;
  onCancel: () => void;
}) {
  const [roleIds, setRoleIds] = useState(() => teacher.roles.map((r) => r.id));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const unchanged =
    roleIds.length === teacher.roles.length && teacher.roles.every((r) => roleIds.includes(r.id));
  const keeps = keepsTeacherRole(roles, roleIds);

  const save = async () => {
    if (teacher.account_id === null) return;
    setBusy(true);
    setError(null);
    try {
      await api.updateUser(teacher.account_id, { role_ids: roleIds });
      onSaved("Roles saved.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save the roles.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-2.5 space-y-2 rounded-lg bg-canvas p-3">
      <RolePicker me={me} roles={roles} selected={roleIds} onChange={setRoleIds} teacherAccount />
      <div className="flex flex-wrap items-center gap-2">
        <Button disabled={busy || unchanged || !keeps} onClick={() => void save()}>
          {busy ? "Saving…" : "Save roles"}
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        {!keeps ? (
          <span className="text-xs text-bad">A teacher&apos;s account keeps at least one teacher role.</span>
        ) : null}
      </div>
      {error ? <ErrorNote message={error} /> : null}
    </div>
  );
}

/** Create a teacher's sign-in, or set a new password on the one they have. */
function SignIn({
  teacher,
  me,
  roles,
  givesRoles,
  onSaved,
  onCancel,
}: {
  teacher: TeacherAccount;
  me: User;
  roles: RoleInfo[];
  givesRoles: boolean;
  onSaved: (message: string) => void;
  onCancel: () => void;
}) {
  const creating = !teacher.has_account;
  const [password, setPassword] = useState("");
  const [roleIds, setRoleIds] = useState(() => startingRoles(roles));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ready =
    password.length >= 6 && (!creating || !givesRoles || keepsTeacherRole(roles, roleIds));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (creating) {
        await api.createTeacherAccount(
          teacher.initial,
          password,
          givesRoles ? roleIds : undefined,
        );
        onSaved(`Account created. ${teacher.initial} can sign in now.`);
      } else {
        await api.resetTeacherPassword(teacher.initial, password);
        onSaved("Password updated.");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="mt-2.5 space-y-3 rounded-lg bg-canvas p-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-ink-soft">
          Sign-in: <code className="font-semibold text-ink">{teacher.initial}</code>
        </span>
        <input
          type="text"
          className={`${inputClass} max-w-52`}
          placeholder={creating ? "Password" : "New password"}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          minLength={6}
          required
          autoFocus
        />
        <Button type="submit" disabled={busy || !ready}>
          {busy ? "Saving…" : creating ? "Create" : "Update"}
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <span className="w-full text-xs text-ink-faint">At least 6 characters.</span>
      </div>
      {creating ? (
        <RoleChoice
          me={me}
          roles={roles}
          givesRoles={givesRoles}
          selected={roleIds}
          onChange={setRoleIds}
        />
      ) : null}
      {error ? <p className="text-xs text-bad">{error}</p> : null}
    </form>
  );
}
