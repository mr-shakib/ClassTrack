"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { BadgeIcon, LockIcon, PlusIcon, UsersIcon } from "@/components/icons";
import { Button, ErrorNote, Spinner, inputClass } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { adminTab, useRequireAccess } from "@/lib/auth";
import type { Permission, PermissionInfo, RoleInfo, RoleKind, User } from "@/lib/types";

const KINDS: { kind: RoleKind; label: string; hint: string }[] = [
  {
    kind: "OFFICE",
    label: "Office",
    hint: "Neither a teacher nor floor staff, e.g. an exam controller.",
  },
  {
    kind: "TEACHER",
    label: "Teacher",
    hint: "Given only to teacher accounts, which keep their own classes and reports.",
  },
  {
    kind: "STAFF",
    label: "Floor staff",
    hint: "The holder is assigned floors in Staff coverage and checks them.",
  },
];

const KIND_LABEL: Record<RoleKind, string> = {
  OFFICE: "Office",
  TEACHER: "Teacher",
  STAFF: "Floor staff",
};

/** Only a teacher's own classes can be rescheduled or booked for. */
const TEACHING_GROUP = "Teaching";

type Draft = {
  id: number | null;
  name: string;
  description: string;
  kind: RoleKind;
  permissions: Permission[];
};

const blank = (): Draft => ({
  id: null,
  name: "",
  description: "",
  kind: "OFFICE",
  permissions: [],
});

const draftOf = (r: RoleInfo): Draft => ({
  id: r.id,
  name: r.name,
  description: r.description,
  kind: r.kind,
  permissions: [...r.permissions],
});

export default function RolesPage() {
  const { user, permitted, loading: authLoading } = useRequireAccess(adminTab("/admin/roles"));
  const [roles, setRoles] = useState<RoleInfo[]>([]);
  const [catalog, setCatalog] = useState<PermissionInfo[]>([]);
  const [draft, setDraft] = useState<Draft | null>(null);
  // Survives the editor remounting under a new role's id once it is created.
  const [savedId, setSavedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (select?: number) => {
    try {
      const [r, c] = await Promise.all([api.roles(), api.permissions()]);
      setRoles(r);
      setCatalog(c);
      setError(null);
      setDraft((d) => {
        const keep = select ?? d?.id;
        const found = r.find((x) => x.id === keep) ?? r[0];
        return found ? draftOf(found) : blank();
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load roles.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (permitted) void load();
  }, [permitted, load]);

  if (authLoading || !permitted || !user) return <Spinner />;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold">Roles</h2>
          <p className="text-sm text-ink-soft">
            A role is a set of permissions. Give people one or more in Accounts; they may do
            whatever any of their roles allows.
          </p>
        </div>
        <Button
          onClick={() => {
            setSavedId(null);
            setDraft(blank());
          }}
        >
          <PlusIcon className="size-4" />
          New role
        </Button>
      </div>

      {error ? <ErrorNote message={error} /> : null}

      {loading ? (
        <Spinner />
      ) : (
        <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
          <ul className="space-y-2">
            {roles.map((r) => {
              const on = draft?.id === r.id;
              return (
                <li key={r.id}>
                  <button
                    type="button"
                    onClick={() => {
                      setSavedId(null);
                      setDraft(draftOf(r));
                    }}
                    aria-pressed={on}
                    className={`w-full rounded-xl border px-4 py-3 text-left transition-colors ${
                      on
                        ? "border-brand bg-brand-soft"
                        : "border-line bg-surface hover:bg-canvas"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className="flex-1 truncate font-semibold">{r.name}</span>
                      {r.is_locked ? <LockIcon className="size-4 text-ink-faint" /> : null}
                      {r.kind !== "OFFICE" ? (
                        <span className="rounded bg-canvas px-1.5 py-0.5 text-xs font-medium text-ink-soft">
                          {KIND_LABEL[r.kind]}
                        </span>
                      ) : null}
                    </div>
                    <div className="mt-1 flex items-center gap-3 text-sm text-ink-faint">
                      <span className="inline-flex items-center gap-1">
                        <UsersIcon className="size-4" />
                        {r.holders}
                      </span>
                      <span>
                        {r.is_locked
                          ? "all permissions"
                          : `${r.permissions.length} permission${r.permissions.length === 1 ? "" : "s"}`}
                      </span>
                      {r.is_builtin ? <span>built-in</span> : null}
                    </div>
                  </button>
                </li>
              );
            })}
            {draft && draft.id === null ? (
              <li className="rounded-xl border border-dashed border-brand bg-brand-soft px-4 py-3 font-semibold text-brand">
                New role
              </li>
            ) : null}
          </ul>

          {draft ? (
            <Editor
              key={draft.id ?? "new"}
              me={user}
              draft={draft}
              role={roles.find((r) => r.id === draft.id) ?? null}
              catalog={catalog}
              justSaved={savedId !== null && savedId === draft.id}
              onSaved={(id) => {
                setSavedId(id);
                void load(id);
              }}
              onDeleted={() => {
                setDraft(null);
                void load();
              }}
            />
          ) : null}
        </div>
      )}
    </div>
  );
}

function Editor({
  me,
  draft: initial,
  role,
  catalog,
  justSaved,
  onSaved,
  onDeleted,
}: {
  me: User;
  draft: Draft;
  role: RoleInfo | null;
  catalog: PermissionInfo[];
  justSaved: boolean;
  onSaved: (id: number) => void;
  onDeleted: () => void;
}) {
  const [draft, setDraft] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(justSaved);
  const isNew = draft.id === null;
  const locked = role?.is_locked ?? false;

  const groups = useMemo(() => {
    const out = new Map<string, PermissionInfo[]>();
    for (const p of catalog) {
      // Teaching permissions mean nothing on a role that is not a teacher's.
      if (p.group === TEACHING_GROUP && draft.kind !== "TEACHER") continue;
      out.set(p.group, [...(out.get(p.group) ?? []), p]);
    }
    return [...out.entries()];
  }, [catalog, draft.kind]);

  const toggle = (p: Permission) => {
    setSaved(false);
    setDraft((d) => ({
      ...d,
      permissions: d.permissions.includes(p)
        ? d.permissions.filter((x) => x !== p)
        : [...d.permissions, p],
    }));
  };

  const save = async () => {
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const out = isNew
        ? await api.createRole({
            name: draft.name,
            description: draft.description,
            kind: draft.kind,
            permissions: draft.permissions,
          })
        : await api.updateRole(draft.id!, {
            name: draft.name,
            description: draft.description,
            ...(locked ? {} : { permissions: draft.permissions }),
          });
      setSaved(true);
      onSaved(out.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save the role.");
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!role || !window.confirm(`Delete the role ${role.name}?`)) return;
    setBusy(true);
    setError(null);
    try {
      await api.deleteRole(role.id);
      onDeleted();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete the role.");
      setBusy(false);
    }
  };

  const held = (p: Permission) => me.permissions.includes(p);

  return (
    <section className="rounded-2xl border border-line bg-surface p-5 shadow-[0_1px_2px_rgba(15,23,42,0.04)] sm:p-6">
      <div className="flex items-start gap-4">
        <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-brand-soft text-brand">
          <BadgeIcon />
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="text-lg font-bold">{isNew ? "New role" : role?.name}</h3>
          <p className="text-sm text-ink-soft">
            {isNew
              ? "Name it, choose who it is for, and tick what it may do."
              : `${role?.holders ?? 0} account${role?.holders === 1 ? " holds" : "s hold"} this role${
                  role?.is_builtin ? " · built-in" : ""
                }.`}
          </p>
        </div>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <label className="block">
          <span className="mb-1 block text-sm font-medium text-ink-soft">Name</span>
          <input
            className={inputClass}
            value={draft.name}
            maxLength={64}
            onChange={(e) => {
              setSaved(false);
              setDraft({ ...draft, name: e.target.value });
            }}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-sm font-medium text-ink-soft">Description</span>
          <input
            className={inputClass}
            value={draft.description}
            maxLength={500}
            placeholder="What it is for"
            onChange={(e) => {
              setSaved(false);
              setDraft({ ...draft, description: e.target.value });
            }}
          />
        </label>
      </div>

      <div className="mt-4">
        <p className="mb-1.5 text-sm font-medium text-ink-soft">
          Who it is for{" "}
          {!isNew ? <span className="font-normal text-ink-faint">— fixed once made</span> : null}
        </p>
        <div className="grid gap-2 sm:grid-cols-3">
          {KINDS.map((k) => {
            const on = draft.kind === k.kind;
            return (
              <button
                key={k.kind}
                type="button"
                disabled={!isNew}
                aria-pressed={on}
                onClick={() =>
                  setDraft((d) => ({
                    ...d,
                    kind: k.kind,
                    // Teaching permissions do not carry over to another kind.
                    permissions:
                      k.kind === "TEACHER"
                        ? d.permissions
                        : d.permissions.filter(
                            (p) => catalog.find((c) => c.key === p)?.group !== TEACHING_GROUP,
                          ),
                  }))
                }
                className={`rounded-xl px-3 py-2.5 text-left ring-1 ring-inset transition-colors disabled:cursor-default ${
                  on
                    ? "bg-brand-soft ring-brand"
                    : "bg-surface ring-line enabled:hover:bg-canvas disabled:opacity-50"
                }`}
              >
                <span className={`block text-sm font-semibold ${on ? "text-brand" : "text-ink"}`}>
                  {k.label}
                </span>
                <span className="mt-0.5 block text-xs text-ink-soft">{k.hint}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="mt-5 space-y-4">
        <div className="flex items-baseline justify-between gap-2">
          <p className="text-sm font-medium text-ink-soft">Permissions</p>
          <p className="text-xs text-ink-faint">
            {locked
              ? "Super admin always has every permission."
              : "You can only give or take permissions you have yourself."}
          </p>
        </div>
        {groups.map(([group, items]) => (
          <fieldset key={group} className="rounded-xl border border-line">
            <legend className="ml-3 px-1 text-xs font-semibold uppercase tracking-wide text-ink-faint">
              {group}
            </legend>
            <ul className="divide-y divide-line">
              {items.map((p) => {
                const on = locked || draft.permissions.includes(p.key);
                const mine = held(p.key);
                return (
                  <li key={p.key}>
                    <label
                      className={`flex items-start gap-3 px-3 py-2.5 ${
                        locked || !mine ? "cursor-not-allowed" : "cursor-pointer hover:bg-canvas"
                      }`}
                    >
                      <input
                        type="checkbox"
                        className="mt-0.5 size-5 shrink-0 accent-brand"
                        checked={on}
                        disabled={locked || !mine}
                        onChange={() => toggle(p.key)}
                      />
                      <span className="min-w-0">
                        <span className={`block text-sm font-semibold ${mine ? "text-ink" : "text-ink-faint"}`}>
                          {p.label}
                          {!mine && !locked ? (
                            <span className="ml-1.5 text-xs font-normal">— you do not have it</span>
                          ) : null}
                        </span>
                        <span className="block text-sm text-ink-soft">{p.description}</span>
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
          </fieldset>
        ))}
      </div>

      {error ? (
        <div className="mt-4">
          <ErrorNote message={error} />
        </div>
      ) : null}

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <Button size="lg" onClick={save} disabled={busy || draft.name.trim().length < 2}>
          {busy ? "Saving…" : isNew ? "Create role" : "Save changes"}
        </Button>
        {saved ? <span className="text-sm font-medium text-ok">Saved.</span> : null}
        {role && !role.is_builtin ? (
          <Button
            variant="ghost"
            className="ml-auto text-bad hover:bg-bad-soft"
            disabled={busy || role.holders > 0}
            title={role.holders > 0 ? "Give its holders another role first." : undefined}
            onClick={remove}
          >
            Delete role
          </Button>
        ) : null}
      </div>
    </section>
  );
}
