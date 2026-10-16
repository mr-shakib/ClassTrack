"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, Card, EmptyState, ErrorNote, Field, Spinner, inputClass } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { ago } from "@/lib/student";
import type { StudentDirectory, StudentNotice } from "@/lib/types";

type Reach = "everyone" | "batches" | "sections";

const TITLE_MAX = 120;
const BODY_MAX = 1000;

const chip = (on: boolean) =>
  `rounded-lg px-3 py-1.5 text-sm font-medium ring-1 ring-inset transition-colors ${
    on ? "bg-brand text-white ring-brand" : "bg-surface text-ink-soft ring-line hover:bg-canvas"
  }`;

/** "*" -> "All students"; "63" -> "Batch 63"; a section as it is. */
const targetLabel = (t: string) => (t === "*" ? "All students" : /^\d+$/.test(t) ? `Batch ${t}` : t);

/**
 * Section Notices, from the department: to every student, to whole batches, or
 * to chosen sections. Students read them without an account; those with the
 * app get them on their phone.
 */
export default function StudentNoticeForm() {
  const [dir, setDir] = useState<StudentDirectory | null>(null);
  const [sent, setSent] = useState<StudentNotice[] | null>(null);
  const [reach, setReach] = useState<Reach>("everyone");
  const [batches, setBatches] = useState<Set<string>>(new Set());
  const [sections, setSections] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [d, s] = await Promise.all([api.studentDirectory(), api.sentToStudents()]);
      setDir(d);
      setSent(s);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const intakes = useMemo(
    () => [...new Set((dir?.sections ?? []).map((s) => s.intake).filter(Boolean))],
    [dir],
  );
  const shown = (dir?.sections ?? []).filter((s) => !filter || s.intake === filter);

  const targets =
    reach === "everyone" ? ["*"] : reach === "batches" ? [...batches] : [...sections];
  const ready = title.trim() !== "" && body.trim() !== "" && targets.length > 0;

  const toggle = (set: Set<string>, value: string, update: (s: Set<string>) => void) => {
    const next = new Set(set);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    update(next);
  };

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ready) return;
    const to = targets.map(targetLabel).join(", ");
    if (!window.confirm(`Send “${title.trim()}” to ${to}? It cannot be taken back.`)) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await api.writeToStudents({ title: title.trim(), body: body.trim(), targets });
      setNotice(`Sent to ${to}. Students see it under Updates, and on their phone if they have the app.`);
      setTitle("");
      setBody("");
      setBatches(new Set());
      setSections(new Set());
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not send.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid max-w-5xl gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
      <Card className="p-4">
        <h2 className="text-sm font-semibold">Write to students</h2>
        <p className="mt-1 text-sm text-ink-soft">
          Students read it under Updates on the student page and in the app, with no account.
        </p>
        <form onSubmit={send} className="mt-4 space-y-4">
          <div>
            <span className="mb-1 block text-sm font-medium text-ink-soft">To</span>
            <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="To">
              {(
                [
                  ["everyone", "All students"],
                  ["batches", "Batches"],
                  ["sections", "Sections"],
                ] as const
              ).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  role="radio"
                  aria-checked={reach === key}
                  className={chip(reach === key)}
                  onClick={() => setReach(key)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {dir == null ? (
            reach !== "everyone" ? <Spinner /> : null
          ) : reach === "batches" ? (
            <div className="flex flex-wrap gap-1.5">
              {intakes.map((i) => (
                <button key={i} type="button" className={chip(batches.has(i))} onClick={() => toggle(batches, i, setBatches)}>
                  Batch {i}
                </button>
              ))}
            </div>
          ) : reach === "sections" ? (
            <div className="space-y-2 rounded-lg border border-line p-2">
              <div className="flex flex-wrap gap-1">
                <button type="button" className={chip(filter === null)} onClick={() => setFilter(null)}>
                  All batches
                </button>
                {intakes.map((i) => (
                  <button key={i} type="button" className={chip(filter === i)} onClick={() => setFilter(i)}>
                    {i}
                  </button>
                ))}
              </div>
              <div className="flex max-h-56 flex-wrap gap-1.5 overflow-y-auto border-t border-line pt-2">
                {shown.map((s) => (
                  <button
                    key={s.section}
                    type="button"
                    className={chip(sections.has(s.section))}
                    onClick={() => toggle(sections, s.section, setSections)}
                  >
                    {s.section}
                  </button>
                ))}
              </div>
              {sections.size > 0 ? (
                <p className="text-xs text-ink-soft">{sections.size} chosen</p>
              ) : null}
            </div>
          ) : null}

          <Field label="Title" hint={`${title.length}/${TITLE_MAX}`}>
            <input
              className={inputClass}
              maxLength={TITLE_MAX}
              placeholder="e.g. Classes resume on Sunday"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </Field>
          <Field label="Message" hint={`${body.length}/${BODY_MAX}`}>
            <textarea
              className={`${inputClass} min-h-28`}
              maxLength={BODY_MAX}
              rows={5}
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
          </Field>

          {error ? <ErrorNote message={error} /> : null}
          {notice ? (
            <div className="rounded-lg border border-ok/20 bg-ok-soft px-3 py-2 text-sm text-ok">{notice}</div>
          ) : null}
          <Button type="submit" disabled={busy || !ready}>
            {busy ? "Sending…" : "Send to students"}
          </Button>
        </form>
      </Card>

      <Card className="p-4">
        <h2 className="text-sm font-semibold">Sent to students</h2>
        {sent == null ? (
          <Spinner />
        ) : sent.length === 0 ? (
          <EmptyState title="Nothing sent yet" />
        ) : (
          <ul className="mt-2 divide-y divide-line">
            {sent.map((n) => (
              <li key={n.id} className="py-2.5">
                <p className="break-words text-sm font-medium">{n.title}</p>
                <p className="mt-0.5 line-clamp-2 whitespace-pre-line break-words text-sm text-ink-soft">{n.body}</p>
                <p className="mt-1 text-xs text-ink-faint">
                  {n.targets.map(targetLabel).join(", ")} · {ago(n.created_at)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
