"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Button,
  Card,
  EmptyState,
  ErrorNote,
  Field,
  Spinner,
  inputClass,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useRequireRole } from "@/lib/auth";
import type { StaffMember, Zone } from "@/lib/types";

export default function StaffPage() {
  const { permitted, loading: authLoading } = useRequireRole(["HOD", "SUPER_ADMIN"]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [staff, setStaff] = useState<StaffMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [z, s] = await Promise.all([api.zones(), api.staff()]);
      setZones(z);
      setStaff(s);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load staff.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (permitted) void load();
  }, [permitted, load]);

  if (authLoading || !permitted) return <Spinner />;
  if (loading) return <Spinner label="Loading staff…" />;

  const covered = new Set(staff.flatMap((m) => m.zones));
  const uncovered = zones.filter((z) => !covered.has(z.key));

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <h2 className="text-sm font-semibold">Office staff</h2>
        <p className="mt-1 text-sm text-ink-soft">
          Assign each staff member a floor. Every class on that floor becomes
          theirs to check and report.
        </p>
      </Card>

      {error ? <ErrorNote message={error} /> : null}

      <AddStaff zones={zones} onAdded={load} />

      {uncovered.length > 0 ? (
        <div className="rounded-lg border border-warn/20 bg-warn-soft px-3 py-2.5">
          <p className="text-sm font-semibold text-warn">
            {uncovered.length} floor{uncovered.length === 1 ? "" : "s"} with nobody
            assigned
          </p>
          <p className="mt-0.5 text-xs text-warn">
            {uncovered.map((z) => z.label).join(" · ")} — classes there will be
            recorded as Not Checked.
          </p>
        </div>
      ) : null}

      {staff.length === 0 ? (
        <Card>
          <EmptyState title="No staff yet" body="Add one above to get started." />
        </Card>
      ) : (
        <div className="space-y-3">
          {staff.map((m) => (
            <StaffRow key={m.id} member={m} zones={zones} onSaved={load} />
          ))}
        </div>
      )}
    </div>
  );
}

function AddStaff({ zones, onAdded }: { zones: Zone[]; onAdded: () => void }) {
  const [open, setOpen] = useState(false);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setFullName("");
    setEmail("");
    setPassword("");
    setSelected([]);
    setError(null);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.createStaff({
        full_name: fullName,
        email,
        password,
        zones: selected,
      });
      reset();
      setOpen(false);
      onAdded();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the account.");
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <Button onClick={() => setOpen(true)}>+ Add staff member</Button>
    );
  }

  return (
    <Card className="p-4">
      <h2 className="text-sm font-semibold">New staff member</h2>
      <form onSubmit={submit} className="mt-3 space-y-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Name">
            <input
              className={inputClass}
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Office Staff Three"
              required
            />
          </Field>
          <Field label="Email">
            <input
              type="email"
              className={inputClass}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="staff3@diu.edu"
              required
            />
          </Field>
          <Field label="Password" hint="At least 6 characters.">
            <input
              type="text"
              className={inputClass}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </Field>
        </div>

        <Field label="Floors" hint="Pick at least one. These become their classes.">
          <div className="flex flex-wrap gap-1.5">
            {zones.map((z) => {
              const on = selected.includes(z.key);
              return (
                <button
                  key={z.key}
                  type="button"
                  onClick={() =>
                    setSelected((p) =>
                      p.includes(z.key)
                        ? p.filter((k) => k !== z.key)
                        : [...p, z.key],
                    )
                  }
                  className={`min-h-9 rounded-lg px-2.5 py-1.5 text-sm font-medium ring-1 ring-inset transition-colors ${
                    on
                      ? "bg-brand-soft text-brand ring-brand/30"
                      : "bg-surface text-ink-soft ring-line hover:bg-canvas"
                  }`}
                >
                  {z.label}
                  <span className="ml-1 text-xs opacity-60">{z.room_count}</span>
                </button>
              );
            })}
          </div>
        </Field>

        {error ? <ErrorNote message={error} /> : null}

        <div className="flex gap-2">
          <Button type="submit" disabled={busy || selected.length === 0}>
            {busy ? "Creating…" : "Create staff member"}
          </Button>
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              reset();
              setOpen(false);
            }}
          >
            Cancel
          </Button>
        </div>
      </form>
    </Card>
  );
}

function StaffRow({
  member,
  zones,
  onSaved,
}: {
  member: StaffMember;
  zones: Zone[];
  onSaved: () => void;
}) {
  const [selected, setSelected] = useState<string[]>(member.zones);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSelected(member.zones);
  }, [member.zones]);

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.assignZones(member.id, selected);
      setEditing(false);
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  };

  const mine = zones.filter((z) => member.zones.includes(z.key));
  const roomCount = mine.reduce((n, z) => n + z.room_count, 0);

  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold">{member.full_name}</p>
          <p className="text-xs text-ink-faint">{member.email}</p>
          <p className="mt-1.5 text-sm">
            {mine.length === 0 ? (
              <span className="font-medium text-warn">
                No floor assigned — sees no classes
              </span>
            ) : (
              <>
                <span className="text-ink-soft">
                  {mine.map((z) => z.label).join(" · ")}
                </span>
                <span className="ml-1.5 text-xs text-ink-faint">
                  {roomCount} rooms
                </span>
              </>
            )}
          </p>
        </div>
        {!editing ? (
          <Button variant="secondary" onClick={() => setEditing(true)}>
            Change floors
          </Button>
        ) : null}
      </div>

      {editing ? (
        <>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {zones.map((z) => {
              const on = selected.includes(z.key);
              return (
                <button
                  key={z.key}
                  onClick={() =>
                    setSelected((p) =>
                      p.includes(z.key)
                        ? p.filter((k) => k !== z.key)
                        : [...p, z.key],
                    )
                  }
                  className={`min-h-9 rounded-lg px-2.5 py-1.5 text-sm font-medium ring-1 ring-inset transition-colors ${
                    on
                      ? "bg-brand-soft text-brand ring-brand/30"
                      : "bg-surface text-ink-soft ring-line hover:bg-canvas"
                  }`}
                >
                  {z.label}
                  <span className="ml-1 text-xs opacity-60">{z.room_count}</span>
                </button>
              );
            })}
          </div>
          {error ? <p className="mt-2 text-xs text-bad">{error}</p> : null}
          <div className="mt-3 flex gap-2">
            <Button onClick={save} disabled={busy}>
              {busy ? "Saving…" : "Save"}
            </Button>
            <Button
              variant="ghost"
              onClick={() => {
                setSelected(member.zones);
                setEditing(false);
              }}
            >
              Cancel
            </Button>
          </div>
        </>
      ) : null}
    </Card>
  );
}
