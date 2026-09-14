"use client";

import { useCallback, useEffect, useState } from "react";
import { Button, Card, ErrorNote, Field, Spinner, inputClass } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { ADMIN_ROLES, useRequireRole } from "@/lib/auth";

export default function SettingsPage() {
  const { permitted, loading: authLoading } = useRequireRole(ADMIN_ROLES);
  const [values, setValues] = useState<Record<string, string>>({});
  const [missed, setMissed] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const v = await api.settings();
      setValues(v);
      setMissed(v.missed_threshold_minutes ?? "30");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the rules.");
    }
  }, []);

  useEffect(() => {
    if (permitted) void load();
  }, [permitted, load]);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await api.updateSettings({ missed_threshold_minutes: Number(missed) });
      setNotice("Saved. The next sweep uses the new value.");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  };

  if (authLoading || !permitted) return <Spinner />;

  return (
    <div className="max-w-2xl space-y-4">
      <Card className="p-4">
        <h2 className="text-sm font-semibold">Monitoring rules</h2>
        <p className="mt-1 text-sm text-ink-soft">
          This rule decides when a reported absence becomes Missed, so change it with
          care.
        </p>

        <form onSubmit={save} className="mt-4 space-y-4">
          <Field
            label="Missed threshold (minutes)"
            hint="How long after the scheduled start a confirmed absence becomes Missed."
          >
            <input
              type="number"
              min={1}
              max={180}
              className={inputClass}
              value={missed}
              onChange={(e) => setMissed(e.target.value)}
            />
          </Field>

          {error ? <ErrorNote message={error} /> : null}
          {notice ? (
            <div className="rounded-lg border border-ok/20 bg-ok-soft px-3 py-2 text-sm text-ok">
              {notice}
            </div>
          ) : null}

          <Button type="submit" disabled={busy}>
            {busy ? "Saving…" : "Save rule"}
          </Button>
        </form>
      </Card>

      <Card className="p-4">
        <h2 className="text-sm font-semibold">Missed and Not Checked are kept apart</h2>
        <p className="mt-1.5 text-sm text-ink-soft">
          The <strong className="text-bad">missed threshold</strong> applies only
          when a staff member has recorded that the teacher was not present — it
          needs positive evidence.
        </p>
        <p className="mt-1.5 text-sm text-ink-soft">
          A class <strong className="text-gap">nobody reported</strong> becomes Not
          Checked at the end of its day. Staff can report any time from the class&apos;s
          start until then. That is a monitoring gap on the staff side, and it is
          never reported as a teacher absence.
        </p>
      </Card>

      <Card className="p-4">
        <h2 className="text-sm font-semibold">Other settings</h2>
        <dl className="mt-2 grid grid-cols-2 gap-2 text-sm">
          {Object.entries(values)
            .filter(([k]) => !k.endsWith("_minutes"))
            .map(([k, v]) => (
              <div key={k} className="rounded-lg bg-canvas px-3 py-2">
                <dt className="text-xs text-ink-faint">{k.replace(/_/g, " ")}</dt>
                <dd className="font-medium">{v}</dd>
              </div>
            ))}
        </dl>
      </Card>
    </div>
  );
}
