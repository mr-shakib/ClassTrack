"use client";

import { useCallback, useEffect, useState } from "react";
import { Button, Card, EmptyState, ErrorNote, Spinner } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useRequireRole } from "@/lib/auth";
import type { StaffMember, Zone } from "@/lib/types";

export default function StaffCoveragePage() {
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
      setError(err instanceof Error ? err.message : "Could not load staff coverage.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (permitted) void load();
  }, [permitted, load]);

  if (authLoading || !permitted) return <Spinner />;
  if (loading) return <Spinner label="Loading staff…" />;

  // Which floors nobody is covering. A gap here becomes NOT_CHECKED classes
  // tomorrow, so it is worth saying out loud.
  const covered = new Set(staff.flatMap((m) => m.zones));
  const unrestricted = staff.filter((m) => m.zones.length === 0);
  const uncovered =
    unrestricted.length > 0 ? [] : zones.filter((z) => !covered.has(z.key));

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <h2 className="text-sm font-semibold">Floor coverage</h2>
        <p className="mt-1 text-sm text-ink-soft">
          Office staff walk a floor, not a department. Assign each person the
          floors they cover and their checking screen shows only those rooms.
        </p>
        <p className="mt-1.5 text-sm text-ink-soft">
          Someone with no floors assigned sees <strong>every</strong> room — an
          unassigned account can still work rather than being locked out.
        </p>
      </Card>

      {error ? <ErrorNote message={error} /> : null}

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
          <EmptyState
            title="No office staff accounts"
            body="Create staff accounts before assigning floors."
          />
        </Card>
      ) : (
        <div className="space-y-3">
          {staff.map((member) => (
            <StaffRow
              key={member.id}
              member={member}
              zones={zones}
              onSaved={load}
            />
          ))}
        </div>
      )}

      <Card className="p-4">
        <h2 className="text-sm font-semibold">
          Floors in the active routine ({zones.length})
        </h2>
        <p className="mt-1 text-xs text-ink-faint">
          Derived from room names, so a new building appears as soon as a routine
          using it is activated.
        </p>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {zones.map((z) => {
            const who = staff.filter(
              (m) => m.zones.includes(z.key) || m.zones.length === 0,
            );
            return (
              <div key={z.key} className="rounded-lg bg-canvas px-3 py-2">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-sm font-medium">{z.label}</span>
                  <span className="text-xs text-ink-faint">{z.room_count} rooms</span>
                </div>
                <p className="mt-0.5 truncate text-xs text-ink-faint">
                  {z.rooms.slice(0, 4).join(", ")}
                  {z.rooms.length > 4 ? ` +${z.rooms.length - 4}` : ""}
                </p>
                <p
                  className={`mt-1 text-xs font-medium ${
                    who.length === 0 ? "text-warn" : "text-ok"
                  }`}
                >
                  {who.length === 0
                    ? "nobody assigned"
                    : who.map((m) => m.full_name).join(", ")}
                </p>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
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
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setSelected(member.zones);
  }, [member.zones]);

  const dirty =
    JSON.stringify([...selected].sort()) !== JSON.stringify([...member.zones].sort());

  const toggle = (key: string) => {
    setSaved(false);
    setSelected((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key],
    );
  };

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.assignZones(member.id, selected);
      setSaved(true);
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  };

  const roomTotal = zones
    .filter((z) => selected.includes(z.key))
    .reduce((n, z) => n + z.room_count, 0);

  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold">{member.full_name}</p>
          <p className="text-xs text-ink-faint">{member.email}</p>
        </div>
        <span
          className={`rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${
            selected.length === 0
              ? "bg-warn-soft text-warn ring-warn/20"
              : "bg-ok-soft text-ok ring-ok/20"
          }`}
        >
          {selected.length === 0
            ? "all rooms"
            : `${selected.length} floor${selected.length === 1 ? "" : "s"} · ${roomTotal} rooms`}
        </span>
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {zones.map((z) => {
          const on = selected.includes(z.key);
          return (
            <button
              key={z.key}
              onClick={() => toggle(z.key)}
              className={`min-h-9 rounded-lg px-2.5 py-1.5 text-sm font-medium ring-1 ring-inset transition-colors ${
                on
                  ? "bg-brand-soft text-brand ring-brand/30"
                  : "bg-surface text-ink-soft ring-line hover:bg-canvas"
              }`}
              title={`${z.room_count} rooms`}
            >
              {z.label}
            </button>
          );
        })}
      </div>

      {error ? <p className="mt-2 text-xs text-bad">{error}</p> : null}

      <div className="mt-3 flex items-center gap-2">
        <Button onClick={save} disabled={busy || !dirty}>
          {busy ? "Saving…" : "Save"}
        </Button>
        {selected.length > 0 ? (
          <Button variant="ghost" onClick={() => setSelected([])} disabled={busy}>
            Clear (see all rooms)
          </Button>
        ) : null}
        {saved && !dirty ? (
          <span className="text-xs font-medium text-ok">Saved</span>
        ) : null}
      </div>
    </Card>
  );
}
