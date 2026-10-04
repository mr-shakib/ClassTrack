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
import { adminTab, can, useAuth, useRequireAccess } from "@/lib/auth";
import type { Routine, Semester, SemesterDates } from "@/lib/types";

const BLANK: SemesterDates = {
  name: "",
  start_date: "",
  end_date: "",
  mid_exam_start: null,
  mid_exam_end: null,
  final_exam_start: null,
};

const day = (iso: string, year = false) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString([], {
    day: "numeric",
    month: "short",
    ...(year ? { year: "numeric" } : {}),
  });

const datesOf = (s: Semester): SemesterDates => ({
  name: s.name,
  start_date: s.start_date,
  end_date: s.end_date,
  mid_exam_start: s.mid_exam_start,
  mid_exam_end: s.mid_exam_end,
  final_exam_start: s.final_exam_start,
});

/**
 * The semester cycle: set the next semester up ahead of time, attach its
 * routine, and make it current when it begins. The exam dates decide when
 * classes stop, and split the semester into the two terms reported on apart.
 */
export default function SemestersPage() {
  const { permitted, loading: authLoading } = useRequireAccess(adminTab("/admin/semesters"));
  const { user } = useAuth();
  // Others may read the list; creating and starting semesters is this.
  const isAdmin = can(user, "semesters.manage");

  const [rows, setRows] = useState<Semester[]>([]);
  const [routines, setRoutines] = useState<Routine[]>([]);
  /** null: no form open. 0: a new semester. Otherwise the one being changed. */
  const [editing, setEditing] = useState<number | null>(null);
  const [form, setForm] = useState<SemesterDates>(BLANK);
  const [makeCurrent, setMakeCurrent] = useState(false);
  const [confirming, setConfirming] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [ss, rs] = await Promise.all([api.semesters(), api.routines()]);
      setRows(ss);
      setRoutines(rs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the semesters.");
    }
  }, []);

  useEffect(() => {
    if (permitted) void load();
  }, [permitted, load]);

  const open = (s: Semester | null) => {
    setEditing(s ? s.id : 0);
    setForm(s ? datesOf(s) : BLANK);
    setMakeCurrent(false);
    setError(null);
    setNotice(null);
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    // An empty date means "not announced yet".
    const payload: SemesterDates = {
      ...form,
      mid_exam_start: form.mid_exam_start || null,
      mid_exam_end: form.mid_exam_end || null,
      final_exam_start: form.final_exam_start || null,
    };
    try {
      if (editing) {
        const { generation: g } = await api.updateSemester(editing, payload);
        setNotice(
          g
            ? `Saved. ${Number(g.instances_retired_days_off ?? 0)} upcoming classes removed ` +
                `from exam days and holidays; ${Number(g.instances_created ?? 0)} added.`
            : "Saved.",
        );
      } else {
        const created = await api.createSemester({ ...payload, make_current: makeCurrent });
        setNotice(
          created.is_active
            ? `${created.name} is the current semester. Upload its routine on the Routine tab.`
            : `${created.name} is set up. Attach its routine on the Routine tab, ` +
                "and make it current when it begins.",
        );
      }
      setEditing(null);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save the semester.");
    } finally {
      setBusy(false);
    }
  };

  const activate = async (s: Semester) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await api.activateSemester(s.id);
      setNotice(
        `${s.name} is now the current semester.` +
          (s.routine_id ? " Its routine is live." : " Upload its routine on the Routine tab."),
      );
      setConfirming(null);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not switch semesters.");
    } finally {
      setBusy(false);
    }
  };

  if (authLoading || !permitted) return <Spinner />;

  const set = (key: keyof SemesterDates) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [key]: e.target.value });

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="max-w-2xl">
            <h2 className="text-sm font-semibold">Semesters</h2>
            <p className="mt-1 text-sm text-ink-soft">
              The department runs one semester at a time. Set the next one up ahead,
              attach its routine on the Routine tab, and make it current when it begins.
              No class is held during the mid-term or the final exams, and reports can
              be filtered till the mid-term and from the mid-term to the final.
            </p>
          </div>
          {isAdmin && editing === null ? (
            <Button onClick={() => open(null)}>New semester</Button>
          ) : null}
        </div>
      </Card>

      {error ? <ErrorNote message={error} /> : null}
      {notice ? (
        <div className="rounded-lg border border-ok/20 bg-ok-soft px-3 py-2 text-sm text-ok">
          {notice}
        </div>
      ) : null}

      {editing !== null ? (
        <Card className="p-4">
          <h2 className="text-sm font-semibold">
            {editing ? `Change ${rows.find((s) => s.id === editing)?.name ?? "semester"}` : "New semester"}
          </h2>
          <form onSubmit={save} className="mt-3 space-y-4">
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="Name">
                <input
                  className={inputClass}
                  placeholder="e.g. Spring 2027"
                  value={form.name}
                  onChange={set("name")}
                  required
                />
              </Field>
              <Field label="Classes begin">
                <input
                  type="date"
                  className={inputClass}
                  value={form.start_date}
                  onChange={set("start_date")}
                  required
                />
              </Field>
              <Field label="Semester ends" hint="The last day of the final exams.">
                <input
                  type="date"
                  className={inputClass}
                  value={form.end_date}
                  onChange={set("end_date")}
                  required
                />
              </Field>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="Mid-term exams from">
                <input
                  type="date"
                  className={inputClass}
                  value={form.mid_exam_start ?? ""}
                  onChange={set("mid_exam_start")}
                />
              </Field>
              <Field label="Mid-term exams to">
                <input
                  type="date"
                  className={inputClass}
                  value={form.mid_exam_end ?? ""}
                  onChange={set("mid_exam_end")}
                />
              </Field>
              <Field label="Final exams begin" hint="Teaching ends the day before.">
                <input
                  type="date"
                  className={inputClass}
                  value={form.final_exam_start ?? ""}
                  onChange={set("final_exam_start")}
                />
              </Field>
            </div>
            <p className="text-xs text-ink-faint">
              Leave an exam date empty until it is announced. Saving removes upcoming
              classes from exam days at once; classes already checked are never touched.
            </p>
            {!editing ? (
              <label className="flex items-center gap-2 text-sm text-ink-soft">
                <input
                  type="checkbox"
                  checked={makeCurrent}
                  onChange={(e) => setMakeCurrent(e.target.checked)}
                />
                Make it the current semester now
              </label>
            ) : null}
            <div className="flex gap-2">
              <Button type="submit" disabled={busy}>
                {busy ? "Saving…" : editing ? "Save changes" : "Create semester"}
              </Button>
              <Button type="button" variant="ghost" onClick={() => setEditing(null)}>
                Cancel
              </Button>
            </div>
          </form>
        </Card>
      ) : null}

      <Card>
        {rows.length === 0 ? (
          <EmptyState title="No semesters yet" body="Create one to start monitoring classes." />
        ) : (
          <ul className="divide-y divide-line">
            {rows.map((s) => {
              const routine = routines.find((r) => r.id === s.routine_id);
              return (
                <li key={s.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold">
                      {s.name}
                      {s.is_active ? (
                        <span className="ml-2 rounded-full bg-ok-soft px-2 py-0.5 text-xs font-semibold text-ok">
                          current
                        </span>
                      ) : null}
                    </p>
                    <p className="text-xs text-ink-faint">
                      {day(s.start_date)} – {day(s.end_date, true)} ·{" "}
                      {routine ? `routine ${routine.version}` : "no routine yet"}
                    </p>
                    <p className="mt-0.5 text-xs text-ink-soft">
                      Mid-term:{" "}
                      {s.mid_exam_start && s.mid_exam_end
                        ? `${day(s.mid_exam_start)} – ${day(s.mid_exam_end)}`
                        : <span className="text-warn">not set</span>}
                      {" · "}Finals from:{" "}
                      {s.final_exam_start ? day(s.final_exam_start) : <span className="text-warn">not set</span>}
                    </p>
                  </div>
                  {isAdmin ? (
                    confirming === s.id ? (
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm text-ink-soft">Switch the department to {s.name}?</span>
                        <Button onClick={() => activate(s)} disabled={busy}>
                          Make current
                        </Button>
                        <Button variant="ghost" onClick={() => setConfirming(null)}>
                          Cancel
                        </Button>
                      </div>
                    ) : (
                      <div className="flex gap-2">
                        {!s.is_active ? (
                          <Button variant="secondary" onClick={() => setConfirming(s.id)} disabled={busy}>
                            Make current
                          </Button>
                        ) : null}
                        <Button variant="secondary" onClick={() => open(s)} disabled={busy}>
                          Edit dates
                        </Button>
                      </div>
                    )
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </Card>
    </div>
  );
}
